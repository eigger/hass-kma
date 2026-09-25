"""DataUpdateCoordinator for KMA integration."""
from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import (
    KmaActivationRequiredError,
    KmaApiClient,
    KmaApiError,
    KmaTransientError,
    VillageForecast,
)
from .const import (
    API_STATUS_HUB_KEYS,
    API_STATUS_IMAGE_KEYS,
    API_STATUS_ZONE_KEYS,
    DOMAIN,
    LAND_ZONE_TO_AREA_NO,
    LAND_ZONE_TO_OFFICE_STN,
    LAND_ZONE_TO_PM10_STN,
    PROVINCE_WARNING_KEYWORDS,
)
from .helpers import parse_pcp, parse_sno

_LOGGER = logging.getLogger(__name__)

API_COOLDOWN = timedelta(minutes=5)
MAX_TRANSIENT_RETRIES = 3


@dataclass(frozen=True)
class CurrentWeather:
    """현재 날씨(실황 우선, 없으면 단기예보 폴백)를 표현하는 통합 값."""

    tmp: float | None     # 기온 (℃)
    reh: float | None     # 습도 (%)
    wsd: float | None     # 풍속 (m/s)
    vec: float | None     # 풍향 (deg)
    pty: str | None       # 강수형태
    sky: str | None       # 하늘상태
    pcp: float | None     # 1시간 강수량 (mm)
    sno: float | None     # 1시간 신적설 (cm, 예보값 — 실황엔 없음)
    pop: float | None     # 강수확률 (%, 예보값)
    source: str           # "ncst"(실황) | "village"(단기예보) | "none"


@dataclass(frozen=True)
class ForecastPoint:
    """시간별 예보 1포인트 (초단기예보 6시간 + 단기예보 병합)."""

    dt: datetime.datetime  # 예보 시각 (KST naive)
    tmp: float | None
    sky: str | None
    pty: str | None
    reh: float | None
    wsd: float | None
    vec: float | None
    pop: float | None        # 강수확률 (%)
    pcp: float | None        # 1시간 강수량 (mm)
    sno: float | None        # 1시간 신적설 (cm)


class _ApiStatusMixin:
    """API별 활용신청 상태/누적 에러 카운트를 추적하는 공통 로직.

    binary_sensor.KmaApiStatusBinarySensor / sensor.KmaApiErrorCountSensor가
    이 믹스인의 api_status/api_error_counts/api_last_error_times를 그대로 읽으므로,
    이 로직을 쓰는 코디네이터는 어떤 종류든 자동으로 활용신청 상태/에러 카운트
    진단 센서 대상이 될 수 있다(binary_sensor.py/sensor.py의 API_STATUS_*_KEYS
    목록에 key를 추가하기만 하면 됨).
    """

    def _init_api_status(self, keys: list[str]) -> None:
        self._api_error_counts: dict[str, int] = {k: 0 for k in keys}
        self._api_last_error_time: dict[str, datetime.datetime | None] = {k: None for k in keys}
        self._api_cooldown_until: dict[str, datetime.datetime] = {}
        self._transient_retries: dict[str, int] = {}
        self._cooldown_unsub: Callable[[], None] | None = None
        self._cooldown_refresh = False

    def _bind_cooldown(self, config_entry: ConfigEntry) -> None:
        """엔트리 언로드 시 예약된 재시도를 취소한다."""
        config_entry.async_on_unload(self._cancel_cooldown_refresh)

    def _in_cooldown(self, api_key: str) -> bool:
        until = self._api_cooldown_until.get(api_key)
        return until is not None and datetime.datetime.now(datetime.timezone.utc) < until

    def _begin_update(self) -> None:
        """수집 주기·재시작 조회는 재시도 횟수를 새로 센다. 5분 재시도 갱신은 이어서 센다."""
        if self._cooldown_refresh:
            self._cooldown_refresh = False
            return
        self._transient_retries.clear()

    def _arm_transient_cooldown(self, api_key: str, label: str, err: Exception) -> None:
        """일시 오류 API를 5분간 건너뛴다. 추가 재시도는 MAX_TRANSIENT_RETRIES회까지."""
        minutes = int(API_COOLDOWN.total_seconds() // 60)
        self._api_cooldown_until[api_key] = (
            datetime.datetime.now(datetime.timezone.utc) + API_COOLDOWN
        )
        count = self._transient_retries.get(api_key, 0) + 1
        self._transient_retries[api_key] = count
        if count > MAX_TRANSIENT_RETRIES:
            _LOGGER.warning(
                "%s 일시 오류 재시도가 %d회에 도달해 다음 수집 주기까지 기다립니다: %s",
                label,
                MAX_TRANSIENT_RETRIES,
                err,
            )
            return
        _LOGGER.warning(
            "%s 일시 오류로 %d분 뒤 재시도합니다 (%d/%d): %s",
            label,
            minutes,
            count,
            MAX_TRANSIENT_RETRIES,
            err,
        )
        if self._cooldown_unsub is not None:
            return
        from homeassistant.helpers.event import async_call_later

        self._cooldown_unsub = async_call_later(
            self.hass, API_COOLDOWN.total_seconds(), self._handle_cooldown_refresh
        )

    def _handle_cooldown_refresh(self, _now: datetime.datetime) -> None:
        self._cooldown_unsub = None
        self._cooldown_refresh = True
        self.hass.async_create_task(self.async_request_refresh())

    def _cancel_cooldown_refresh(self) -> None:
        if self._cooldown_unsub is not None:
            self._cooldown_unsub()
            self._cooldown_unsub = None

    async def _fetch_optional(
        self,
        api_key: str,
        label: str,
        factory: Callable[[], Awaitable[Any]],
        *,
        default: Any = None,
    ) -> tuple[Any, str]:
        """선택적 API 호출. 상태: ok | not_applied | cooldown | error: 메시지."""
        if self._in_cooldown(api_key):
            _LOGGER.debug("%s 쿨다운 중이라 호출을 건너뜁니다.", label)
            return default, "cooldown"
        try:
            result = await factory()
        except KmaActivationRequiredError:
            _LOGGER.warning("%s API 미신청(403). 활용신청이 필요합니다.", label)
            return default, "not_applied"
        except KmaTransientError as err:
            self._arm_transient_cooldown(api_key, label, err)
            return default, f"error: {err}"
        except KmaApiError as err:
            _LOGGER.warning("%s 업데이트 경고: %s", label, err)
            return default, f"error: {err}"
        self._transient_retries.pop(api_key, None)
        return result, "ok"

    def _record_api_status(self, status: dict[str, str]) -> None:
        """status 딕셔너리("ok"/"not_applied"/"error: ...")를 보고 에러 카운트를 갱신."""
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for api_key, api_stat in status.items():
            if isinstance(api_stat, str) and api_stat.startswith("error"):
                self._api_error_counts[api_key] = self._api_error_counts.get(api_key, 0) + 1
                self._api_last_error_time[api_key] = now_utc

    @property
    def api_status(self) -> dict[str, str]:
        """현재 기록된 API별 접근 상태."""
        return (self.data or {}).get("api_status", {})

    @property
    def api_error_counts(self) -> dict[str, int]:
        """API별 누적 에러 카운트 (세션 기준)."""
        return dict(self._api_error_counts)

    @property
    def api_last_error_times(self) -> dict[str, datetime.datetime | None]:
        """API별 마지막 에러 발생 시각 (UTC aware). 에러 없으면 None."""
        return dict(self._api_last_error_time)


class KmaForecastCoordinator(_ApiStatusMixin, DataUpdateCoordinator[dict[str, Any]]):
    """KMA 예·특보 데이터 코디네이터 (Zone 서브엔트리 단위)."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: KmaApiClient,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """코디네이터 초기화."""
        self.client = client
        self.subentry = subentry
        self.nx = subentry.data["nx"]
        self.ny = subentry.data["ny"]
        self.land_reg = subentry.data["land_reg"]
        self.marine_reg = subentry.data["marine_reg"]
        self.stn = LAND_ZONE_TO_PM10_STN.get(self.land_reg, 108)  # PM10/적설/미세먼지 시간통계 관측지점(기본값 서울)
        self.area_no = LAND_ZONE_TO_AREA_NO.get(self.land_reg, "1100000000")  # 생활/보건기상지수 지역코드
        self.office_stn = LAND_ZONE_TO_OFFICE_STN.get(self.land_reg, 109)  # 지방기상청 관서코드(기본값 서울)
        self.lat = subentry.data["latitude"]
        self.lon = subentry.data["longitude"]

        # API별 누적 에러 카운트 / 마지막 에러 시각 (HA 재시작 전까지 유지)
        self._init_api_status(API_STATUS_ZONE_KEYS)
        self._refresh_meta: dict[str, bool] = {
            "village_stale": False,
            "land_stale": False,
            "marine_stale": False,
            "warnings_stale": False,
            "ncst_stale": False,
            "ultra_stale": False,
            "pm10_stale": False,
            "uv_index_stale": False,
            "air_stagnation_stale": False,
            "oak_pollen_stale": False,
            "pine_pollen_stale": False,
            "weed_pollen_stale": False,
            "radar_precipitation_stale": False,
            "sfc_observation_stale": False,
            "snow_depth_stale": False,
            "pm10_hourly_stale": False,
        }

        scan_interval = config_entry.options.get("scan_interval", 10)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{subentry.subentry_id}",
            update_interval=timedelta(minutes=scan_interval),
        )
        self._bind_cooldown(config_entry)

    async def _fetch_village(
        self, now: datetime.datetime
    ) -> tuple[list, str, str | None]:
        """동네예보. 빈 응답(NODATA)만 이전 발표시각으로 재시도한다.

        504·타임아웃 같은 일시 오류는 바로 멈추고 쿨다운한다.
        """
        if self._in_cooldown("village_forecast"):
            _LOGGER.debug("동네예보 쿨다운 중이라 호출을 건너뜁니다.")
            return [], "cooldown", None

        village_forecasts: list = []
        village_status = "error"
        last_error = None
        for base_date, base_time in self._iter_forecast_base_times(now):
            try:
                village_forecasts = await self.client.async_get_village_forecast(
                    self.nx, self.ny, base_date=base_date, base_time=base_time
                )
            except KmaActivationRequiredError as err:
                village_status = "not_applied"
                last_error = str(err)
                _LOGGER.warning("동네예보 API 미신청(403). 활용신청이 필요합니다.")
                break
            except KmaTransientError as err:
                last_error = str(err)
                self._arm_transient_cooldown("village_forecast", "동네예보", err)
                break
            except KmaApiError as err:
                last_error = str(err)
                _LOGGER.debug("동네예보 base_time=%s%s 호출 실패: %s", base_date, base_time, err)
                break
            village_status = "ok"
            last_error = None
            self._transient_retries.pop("village_forecast", None)
            if village_forecasts:
                break
        status = (
            f"error: {last_error}" if village_status == "error" and last_error else village_status
        )
        return village_forecasts, status, last_error

    async def _async_update_data(self) -> dict[str, Any]:
        """기상청 API로부터 실시간 예보 및 특보 데이터를 가져옵니다.

        각 API의 응답 결과(정상/미신청/오류)를 data["api_status"]에 기록하여
        허브 단위 진단 센서가 활용신청 상태를 표시할 수 있도록 한다.
        활용신청 미완료(403)는 통합 실패로 처리하지 않고 해당 데이터만 비운다.
        """
        self._begin_update()
        data: dict[str, Any] = {}
        status: dict[str, str] = {}
        refresh_meta = {key: False for key in self._refresh_meta}

        # 서로 독립인 API는 한 번에 요청한다. 동시 실행 수는 클라이언트가 제한한다.
        # 동네예보는 빈 응답(NODATA)일 때만 이전 발표시각으로 재시도한다.
        now = datetime.datetime.now()  # noqa: DTZ005
        (
            (village_forecasts, status["village_forecast"], last_error),
            ncst,
            ultra,
            (land, status["land_forecast"]),
            (marine, status["marine_forecast"]),
            (pm10_obs, status["pm10"]),
            (uv_obs, status["uv_index"]),
            (air_obs, status["air_stagnation"]),
            (oak_obs, status["oak_pollen"]),
            (pine_obs, status["pine_pollen"]),
            (weed_obs, status["weed_pollen"]),
            (radar_obs, status["radar_precipitation"]),
            (sfc_obs, status["sfc_observation"]),
            (heat_obs, status["heat_wave_risk"]),
            (cold_obs, status["cold_wave_risk"]),
            (hazard_obs, status["hazard_info"]),
            (commentary_obs, status["weather_commentary"]),
            (snow_obs, status["snow_depth"]),
            (pm10_hourly_obs, status["pm10_hourly"]),
            (warnings, status["warning_now"]),
        ) = await asyncio.gather(
            self._fetch_village(now),
            self._fetch_optional(
                "ncst", "초단기실황", lambda: self.client.async_get_ultra_ncst(self.nx, self.ny)
            ),
            self._fetch_optional(
                "ultra", "초단기예보",
                lambda: self.client.async_get_ultra_fcst(self.nx, self.ny),
                default=[],
            ),
            self._fetch_optional(
                "land_forecast", "육상예보",
                lambda: self.client.async_get_land_forecast(self.land_reg),
                default=[],
            ),
            self._fetch_optional(
                "marine_forecast", "해상예보",
                lambda: self.client.async_get_marine_forecast(self.marine_reg),
                default=[],
            ),
            self._fetch_optional(
                "pm10", "미세먼지(PM10)",
                lambda: self.client.async_get_pm10_now(stn=self.stn),
            ),
            self._fetch_optional(
                "uv_index", "자외선지수",
                lambda: self.client.async_get_uv_index(area_no=self.area_no),
            ),
            self._fetch_optional(
                "air_stagnation", "대기정체지수",
                lambda: self.client.async_get_air_stagnation_index(area_no=self.area_no),
            ),
            self._fetch_optional(
                "oak_pollen", "꽃가루(참나무)",
                lambda: self.client.async_get_oak_pollen_risk(area_no=self.area_no),
            ),
            self._fetch_optional(
                "pine_pollen", "꽃가루(소나무)",
                lambda: self.client.async_get_pine_pollen_risk(area_no=self.area_no),
            ),
            self._fetch_optional(
                "weed_pollen", "꽃가루(잡초류)",
                lambda: self.client.async_get_weed_pollen_risk(area_no=self.area_no),
            ),
            self._fetch_optional(
                "radar_precipitation", "레이더 강수강도",
                lambda: self.client.async_get_radar_precipitation(dong_code=self.area_no),
            ),
            self._fetch_optional(
                "sfc_observation", "고해상도 지상관측",
                lambda: self.client.async_get_sfc_observation(lat=self.lat, lon=self.lon),
            ),
            self._fetch_optional(
                "heat_wave_risk", "영향예보(폭염)",
                lambda: self.client.async_get_heat_wave_risk(stn=self.office_stn),
            ),
            self._fetch_optional(
                "cold_wave_risk", "영향예보(한파)",
                lambda: self.client.async_get_cold_wave_risk(stn=self.office_stn),
            ),
            self._fetch_optional(
                "hazard_info", "기상정보",
                lambda: self.client.async_get_hazard_info(stn=self.office_stn),
            ),
            self._fetch_optional(
                "weather_commentary", "날씨해설",
                lambda: self.client.async_get_weather_commentary(stn=self.office_stn),
            ),
            self._fetch_optional(
                "snow_depth", "적설관측",
                lambda: self.client.async_get_snow_depth(stn=self.stn),
            ),
            self._fetch_optional(
                "pm10_hourly", "미세먼지 시간통계",
                lambda: self.client.async_get_pm10_hourly_stats(stn=self.stn),
            ),
            self._fetch_optional(
                "warning_now", "기상특보",
                lambda: self.client.async_get_warning_now(),
                default=[],
            ),
        )
        ncst = ncst[0]
        ultra = ultra[0] or []
        if not village_forecasts and self.data and "village" in self.data:
            data["village"] = self.data["village"]
            refresh_meta["village_stale"] = True
            _LOGGER.debug("동네예보 데이터가 비어 있어 이전 값을 유지합니다.")
        else:
            data["village"] = village_forecasts

        # 1-2. 초단기실황/초단기예보 — 실패하면 이전 값을 유지하고, 없어도 단기예보로 폴백한다.
        if ncst is None and (self.data or {}).get("ncst") is not None:
            refresh_meta["ncst_stale"] = True
        data["ncst"] = ncst or (self.data or {}).get("ncst")

        if not ultra and (self.data or {}).get("ultra"):
            refresh_meta["ultra_stale"] = True
        data["ultra"] = ultra or (self.data or {}).get("ultra", [])

        if not land and self.data and "land" in self.data:
            data["land"] = self.data["land"]
            refresh_meta["land_stale"] = True
            _LOGGER.debug("육상예보 데이터가 비어 있어 이전 값을 유지합니다.")
        else:
            data["land"] = land

        if not marine and self.data and "marine" in self.data:
            data["marine"] = self.data["marine"]
            refresh_meta["marine_stale"] = True
            _LOGGER.debug("해상예보 데이터가 비어 있어 이전 값을 유지합니다.")
        else:
            data["marine"] = marine

        if pm10_obs is None and self.data and "pm10" in self.data:
            data["pm10"] = self.data["pm10"]
            refresh_meta["pm10_stale"] = True
            _LOGGER.debug("PM10 데이터가 없어 이전 값을 유지합니다.")
        else:
            data["pm10"] = pm10_obs

        if uv_obs is None and self.data and "uv_index" in self.data:
            data["uv_index"] = self.data["uv_index"]
            refresh_meta["uv_index_stale"] = True
        else:
            data["uv_index"] = uv_obs

        if air_obs is None and self.data and "air_stagnation" in self.data:
            data["air_stagnation"] = self.data["air_stagnation"]
            refresh_meta["air_stagnation_stale"] = True
        else:
            data["air_stagnation"] = air_obs

        # 3-4. 꽃가루농도위험지수 3종 (계절 서비스 — 비시즌 None은 정상 상태이므로
        # 이전 값을 이어붙이지 않는다. 이어붙이면 시즌 종료 후에도 옛 값이 남아 오해를 준다).
        data["oak_pollen"] = oak_obs
        data["pine_pollen"] = pine_obs
        data["weed_pollen"] = weed_obs

        # 3-5. 행정구역별 레이더 강수강도 (WthrRadarInfoService/getCompCappiQcdArea)
        # 실측 결과 특정 지역(광주, 구코드 2900000000 — 통합특별시 개편으로 대체된
        # 레거시 코드)에서 간헐적으로 오류가 발생함이 확인되어(2026-07-01), 실패 시
        # 이전 값을 유지한다.
        if radar_obs is None and self.data and "radar_precipitation" in self.data:
            data["radar_precipitation"] = self.data["radar_precipitation"]
            refresh_meta["radar_precipitation_stale"] = True
        else:
            data["radar_precipitation"] = radar_obs

        # 3-6. 고해상도 지상관측 (sfc_nc_var.php) [실측 검증 2026-07-02]
        if sfc_obs is None and self.data and "sfc_observation" in self.data:
            data["sfc_observation"] = self.data["sfc_observation"]
            refresh_meta["sfc_observation_stale"] = True
        else:
            data["sfc_observation"] = sfc_obs

        # 3-7. 영향예보 폭염/한파 (ifs_fct_pstt.php) [실측 검증 2026-07-02]
        # 비시즌에는 위험구역이 없어 level=None이 정상 상태이므로 이전 값을 이어붙이지 않는다.
        data["heat_wave_risk"] = heat_obs
        data["cold_wave_risk"] = cold_obs

        # 3-8. 기상정보/날씨해설 (관서별 텍스트 속보) [실측 검증 2026-07-02]
        # 최근 24시간 내 발표분이 없으면 None이 정상 상태이므로 이전 값을 이어붙이지 않는다.
        data["hazard_info"] = hazard_obs
        data["weather_commentary"] = commentary_obs

        # 3-9. 적설관측 (kma_snow1.php) [실측 검증 2026-07-02]
        if snow_obs is None and self.data and "snow_depth" in self.data:
            data["snow_depth"] = self.data["snow_depth"]
            refresh_meta["snow_depth_stale"] = True
        else:
            data["snow_depth"] = snow_obs

        # 3-10. 미세먼지(PM10) 시간통계 (dst_pm10_hr.php) [실측 검증 2026-07-02]
        if pm10_hourly_obs is None and self.data and "pm10_hourly" in self.data:
            data["pm10_hourly"] = self.data["pm10_hourly"]
            refresh_meta["pm10_hourly_stale"] = True
        else:
            data["pm10_hourly"] = pm10_hourly_obs

        # 특보 호출 실패·쿨다운 시에는 이전 특보를 유지하고, 성공했으나 내용이 없으면 빈 목록으로 갱신한다.
        warning_failed = status["warning_now"] == "cooldown" or status["warning_now"].startswith("error")
        if warning_failed and self.data and "warnings" in self.data:
            data["warnings"] = self.data["warnings"]
            refresh_meta["warnings_stale"] = True
            _LOGGER.debug("기상특보 호출이 실패하여 이전 특보 데이터를 유지합니다.")
        else:
            keywords = PROVINCE_WARNING_KEYWORDS.get(self.land_reg, [])
            data["warnings"] = [
                w
                for w in warnings
                if any(
                    kw in w.get("REG_UP_KO", "") or kw in w.get("REG_KO", "")
                    for kw in keywords
                )
            ]

        data["api_status"] = status
        self._record_api_status(status)

        # 일시 오류로 셋업 전체를 실패시키지 않는다. 받은 값(또는 이전 값)을 올리고
        # 쿨다운이 끝나면 해당 API만 다시 조회한다.
        if str(status.get("village_forecast", "")).startswith("error"):
            if self.data is not None:
                _LOGGER.warning(
                    "동네예보 API 호출이 일시적으로 실패하여 이전 값을 유지합니다: %s",
                    last_error,
                )
            else:
                _LOGGER.warning(
                    "동네예보 API 호출이 실패했습니다. 받은 데이터만 반영하고 나중에 재시도합니다: %s",
                    last_error,
                )

        self._refresh_meta = refresh_meta
        return data

    @property
    def refresh_meta(self) -> dict[str, bool]:
        """마지막 갱신에서 이전 값을 유지한 데이터 항목 여부."""
        return dict(self._refresh_meta)

    def _nearest_village(self) -> VillageForecast | None:
        """현재 시각에 가장 가까운 동네예보 레코드(폴백/POP용)."""
        village: list[VillageForecast] = (self.data or {}).get("village", [])
        if not village:
            return None
        now = datetime.datetime.now()  # noqa: DTZ005
        best, best_diff = None, None
        for vf in village:
            try:
                vdt = datetime.datetime.strptime(f"{vf.fcst_date}{vf.fcst_time}", "%Y%m%d%H%M")  # noqa: DTZ007
            except ValueError:
                continue
            diff = abs((vdt - now).total_seconds())
            if best_diff is None or diff < best_diff:
                best, best_diff = vf, diff
        return best or village[0]

    def get_current(self) -> CurrentWeather:
        """현재 날씨를 실황(getUltraSrtNcst) 우선으로 반환.

        실황에 없는 하늘상태(SKY)는 초단기예보(getUltraSrtFcst)로 보완하고,
        강수확률(POP)은 단기예보에서 가져온다. 실황이 없으면 단기예보로 폴백.
        """
        data = self.data or {}
        ncst = data.get("ncst")
        ultra: list = data.get("ultra") or []
        vf = self._nearest_village()
        pop = vf.pop if vf else None

        # 적설(SNO)은 실황에 없으므로 단기예보(가장 가까운 시각)에서 가져온다.
        sno = parse_sno(vf.sno) if vf else None

        if ncst is not None:
            sky = ultra[0].sky if ultra else (vf.sky if vf else None)
            pty = ncst.pty if ncst.pty is not None else (ultra[0].pty if ultra else None)
            return CurrentWeather(
                tmp=ncst.t1h, reh=ncst.reh, wsd=ncst.wsd, vec=ncst.vec,
                pty=pty, sky=sky, pcp=ncst.rn1, sno=sno, pop=pop, source="ncst",
            )
        if vf is not None:
            return CurrentWeather(
                tmp=vf.tmp, reh=vf.reh, wsd=vf.wsd, vec=vf.vec,
                pty=vf.pty, sky=vf.sky, pcp=parse_pcp(vf.pcp), sno=sno,
                pop=vf.pop, source="village",
            )
        return CurrentWeather(None, None, None, None, None, None, None, None, None, "none")

    def forecast_points(self) -> list[ForecastPoint]:
        """시간별 예보를 초단기예보(앞 6시간) + 단기예보로 병합해 시간순 반환.

        근시간은 더 정확한 초단기예보로 덮고, 그 이후는 단기예보로 채운다.
        강수확률(POP)은 초단기예보에 없으므로 같은 시각의 단기예보에서 보완.
        """
        data = self.data or {}
        ultra = data.get("ultra") or []
        village = data.get("village") or []
        vmap = {f"{v.fcst_date}{v.fcst_time}": v for v in village}

        points: list[ForecastPoint] = []
        seen: set[str] = set()

        for u in ultra:
            key = f"{u.fcst_date}{u.fcst_time}"
            try:
                dt = datetime.datetime.strptime(key, "%Y%m%d%H%M")  # noqa: DTZ007
            except ValueError:
                continue
            seen.add(key)
            v = vmap.get(key)
            points.append(
                ForecastPoint(
                    dt=dt, tmp=u.t1h, sky=u.sky, pty=u.pty, reh=u.reh,
                    wsd=u.wsd, vec=u.vec,
                    pop=(v.pop if v else None), pcp=parse_pcp(u.rn1),
                    sno=(parse_sno(v.sno) if v else None),
                )
            )

        last_ultra_key = max(seen) if seen else ""
        for v in village:
            key = f"{v.fcst_date}{v.fcst_time}"
            if key <= last_ultra_key:
                continue
            try:
                dt = datetime.datetime.strptime(key, "%Y%m%d%H%M")  # noqa: DTZ007
            except ValueError:
                continue
            points.append(
                ForecastPoint(
                    dt=dt, tmp=v.tmp, sky=v.sky, pty=v.pty, reh=v.reh,
                    wsd=v.wsd, vec=v.vec, pop=v.pop, pcp=parse_pcp(v.pcp),
                    sno=parse_sno(v.sno),
                )
            )

        points.sort(key=lambda p: p.dt)
        return points

    def next_precipitation(self) -> ForecastPoint | None:
        """앞으로 강수가 시작되는 가장 가까운 예보 포인트. 없으면 None."""
        now = datetime.datetime.now()  # noqa: DTZ005
        for p in self.forecast_points():
            if p.dt < now - datetime.timedelta(hours=1):
                continue
            if p.pty and p.pty != "0":
                return p
        return None

    def _iter_forecast_base_times(
        self, now: datetime.datetime, count: int = 4
    ) -> list[tuple[str, str]]:
        """최근 발표시각부터 과거로 count개의 (base_date, base_time) 후보를 반환.

        가장 최근 발표분이 아직 게시되지 않았을 때 이전 발표시각으로
        backoff 재시도하기 위한 후보 목록.
        """
        candidates: list[tuple[str, str]] = []
        cursor = now
        for _ in range(count):
            base_date, base_time = self._get_latest_forecast_time(cursor)
            candidates.append((base_date, base_time))
            # 직전 발표시각으로 커서 이동(해당 발표시각 16분 전)
            dt = datetime.datetime.strptime(base_date + base_time, "%Y%m%d%H%M")  # noqa: DTZ007
            cursor = dt - datetime.timedelta(minutes=16)
        return candidates

    def _get_latest_forecast_time(self, now: datetime.datetime) -> tuple[str, str]:
        """기상청 단기예보의 가장 최신 발표 시각을 계산하여 (base_date, base_time)으로 반환."""
        # 예보는 발표 시간 15분 후에 정식 제공되므로 15분 차감하여 계산
        check_time = now - datetime.timedelta(minutes=15)
        hour = check_time.hour
        
        forecast_hours = [2, 5, 8, 11, 14, 17, 20, 23]
        target_hour = 23
        target_date = check_time
        
        for h in reversed(forecast_hours):
            if hour >= h:
                target_hour = h
                break
        else:
            target_hour = 23
            target_date = check_time - datetime.timedelta(days=1)
            
        base_date = target_date.strftime("%Y%m%d")
        base_time = f"{target_hour:02d}00"
        return base_date, base_time


class KmaImageCoordinator(_ApiStatusMixin, DataUpdateCoordinator[dict[str, Any]]):
    """레이더/위성/강수예측 이미지 코디네이터 (허브 단위, Zone과 무관한 전국 이미지 세트).

    ImageEntity는 `image_last_updated`를 코디네이터 갱신 시점에만 바꿔야 하므로
    (async_image 내부에서 바꾸면 순환 트리거가 됨), 바이트 페칭은 여기서 수행하고
    엔티티는 캐시된 바이트만 반환한다.

    이미지들 모두 게시 지연이 있어(레이더/강수예측 ~20분, 위성 거의 없음) 아직
    게시되지 않은 경우 async_get_*_image()가 None을 반환한다 — 이때는 이전 값을
    유지한다(에러는 아니므로 상태는 "ok"로 기록).
    """

    def __init__(self, hass: HomeAssistant, client: KmaApiClient, config_entry: ConfigEntry) -> None:
        self.client = client
        self._init_api_status(API_STATUS_IMAGE_KEYS)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_image",
            update_interval=timedelta(minutes=10),
        )
        self._bind_cooldown(config_entry)

    async def _fetch_image(
        self,
        data: dict[str, Any],
        key: str,
        label: str,
        factory: Callable[[], Awaitable[Any]],
    ) -> str:
        """이미지를 조회해 data[key]에 저장하고, 활용신청 상태 문자열을 반환한다."""
        if self._in_cooldown(key):
            _LOGGER.debug("%s 쿨다운 중이라 호출을 건너뜁니다.", label)
            return "cooldown"
        try:
            image = await factory()
            if image is not None:
                data[key] = image
            self._transient_retries.pop(key, None)
            return "ok"
        except KmaActivationRequiredError:
            _LOGGER.warning("%s API 미신청(403). 활용신청이 필요합니다.", label)
            return "not_applied"
        except KmaTransientError as err:
            self._arm_transient_cooldown(key, label, err)
            return f"error: {err}"
        except KmaApiError as err:
            _LOGGER.debug("%s 갱신 실패: %s", label, err)
            return f"error: {err}"

    async def _async_update_data(self) -> dict[str, Any]:
        """레이더/위성/강수예측 최신 이미지를 조회. 실패/미게시 시 이전 값을 유지."""
        self._begin_update()
        data: dict[str, Any] = dict(self.data or dict.fromkeys(API_STATUS_IMAGE_KEYS))
        status: dict[str, str] = {}

        (
            status["radar"],
            status["satellite"],
            status["precipitation_forecast"],
            status["satellite_visible"],
            status["satellite_shortwave_ir"],
            status["satellite_water_vapor"],
            status["dust_satellite"],
        ) = await asyncio.gather(
            self._fetch_image(data, "radar", "레이더 이미지", self.client.async_get_radar_image),
            self._fetch_image(data, "satellite", "위성 이미지", self.client.async_get_satellite_image),
            self._fetch_image(
                data, "precipitation_forecast", "강수예측 이미지",
                self.client.async_get_precipitation_forecast_image,
            ),
            self._fetch_image(
                data, "satellite_visible", "위성 가시광선 이미지",
                lambda: self.client.async_get_satellite_image(obs="vi006"),
            ),
            self._fetch_image(
                data, "satellite_shortwave_ir", "위성 단파적외 이미지",
                lambda: self.client.async_get_satellite_image(obs="sw038"),
            ),
            self._fetch_image(
                data, "satellite_water_vapor", "위성 수증기 이미지",
                lambda: self.client.async_get_satellite_image(obs="wv069"),
            ),
            self._fetch_image(
                data, "dust_satellite", "황사위성영상",
                self.client.async_get_dust_satellite_image,
            ),
        )

        data["api_status"] = status
        self._record_api_status(status)
        return data


class KmaHubCoordinator(_ApiStatusMixin, DataUpdateCoordinator[dict[str, Any]]):
    """지진/태풍 코디네이터 (허브 단위, Zone과 무관한 전국 데이터).

    이미지가 아니라 구조화된 데이터라 KmaImageCoordinator와는 별도로 둔다.
    지진은 발생 즉시성이 중요하지만 apihub 자체가 실시간 푸시가 아니라 폴링
    API이므로, 다른 허브 데이터와 같은 10분 주기로 통일한다.
    """

    def __init__(self, hass: HomeAssistant, client: KmaApiClient, config_entry: ConfigEntry) -> None:
        self.client = client
        self._init_api_status(API_STATUS_HUB_KEYS)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_hub",
            update_interval=timedelta(minutes=10),
        )
        self._bind_cooldown(config_entry)

    async def _async_update_data(self) -> dict[str, Any]:
        """최근 지진정보/태풍정보를 조회. 실패 시 이전 값을 유지."""
        self._begin_update()
        data: dict[str, Any] = dict(self.data or dict.fromkeys(API_STATUS_HUB_KEYS))
        status: dict[str, str] = {}

        (eq_obs, status["earthquake"]), (typhoon_obs, status["typhoon"]) = await asyncio.gather(
            self._fetch_optional(
                "earthquake", "지진정보", self.client.async_get_earthquake_recent
            ),
            self._fetch_optional(
                "typhoon", "태풍정보", self.client.async_get_typhoon_now
            ),
        )
        if eq_obs is not None:
            data["earthquake"] = eq_obs
        # 활성 태풍이 없는 것은 정상 상태이므로, API 호출 자체가 성공(ok)했다면
        # 이전 값을 이어붙이지 않고 그대로 None(없음)으로 갱신한다.
        if status["typhoon"] == "ok":
            data["typhoon"] = typhoon_obs

        data["api_status"] = status
        self._record_api_status(status)
        return data
