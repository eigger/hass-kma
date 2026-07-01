"""DataUpdateCoordinator for KMA integration."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging
from typing import Any

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LAND_ZONE_TO_AREA_NO,
    LAND_ZONE_TO_PM10_STN,
    PROVINCE_WARNING_KEYWORDS,
)
from .api import (
    KmaApiClient,
    KmaApiError,
    KmaActivationRequiredError,
    VillageForecast,
)
from .helpers import parse_pcp, parse_sno

_LOGGER = logging.getLogger(__name__)


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

    dt: "datetime.datetime"  # 예보 시각 (KST naive)
    tmp: float | None
    sky: str | None
    pty: str | None
    reh: float | None
    wsd: float | None
    vec: float | None
    pop: float | None        # 강수확률 (%)
    pcp: float | None        # 1시간 강수량 (mm)
    sno: float | None        # 1시간 신적설 (cm)


_API_STATUS_KEYS = [
    "village_forecast", "land_forecast", "marine_forecast", "warning_now", "pm10",
    "uv_index", "air_stagnation", "oak_pollen", "pine_pollen", "weed_pollen",
    "radar_precipitation",
]


class KmaForecastCoordinator(DataUpdateCoordinator[dict[str, Any]]):
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
        self.stn = LAND_ZONE_TO_PM10_STN.get(self.land_reg, 108)  # PM10 관측지점(기본값 서울)
        self.area_no = LAND_ZONE_TO_AREA_NO.get(self.land_reg, "1100000000")  # 생활/보건기상지수 지역코드

        # API별 누적 에러 카운트 / 마지막 에러 시각 (HA 재시작 전까지 유지)
        self._api_error_counts: dict[str, int] = {k: 0 for k in _API_STATUS_KEYS}
        self._api_last_error_time: dict[str, datetime.datetime | None] = {
            k: None for k in _API_STATUS_KEYS
        }
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
        }

        scan_interval = config_entry.options.get("scan_interval", 10)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{subentry.subentry_id}",
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """기상청 API로부터 실시간 예보 및 특보 데이터를 가져옵니다.

        각 API의 응답 결과(정상/미신청/오류)를 data["api_status"]에 기록하여
        허브 단위 진단 센서가 활용신청 상태를 표시할 수 있도록 한다.
        활용신청 미완료(403)는 통합 실패로 처리하지 않고 해당 데이터만 비운다.
        """
        data: dict[str, Any] = {}
        status: dict[str, str] = {}
        refresh_meta = {key: False for key in self._refresh_meta}

        # 1. 동네예보 (getVilageFcst)
        # 발표 시각은 0200,0500,0800,1100,1400,1700,2000,2300. 최근 발표분이 아직
        # 게시 전(NODATA)일 수 있으므로 이전 발표시각으로 backoff 재시도한다.
        now = datetime.datetime.now()
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
            except KmaApiError as err:
                last_error = str(err)
                _LOGGER.debug("동네예보 base_time=%s%s 호출 실패: %s", base_date, base_time, err)
                continue
            # 호출 자체는 성공 (데이터가 비어도 NODATA일 뿐 활성 상태)
            village_status = "ok"
            last_error = None
            if village_forecasts:
                break
        status["village_forecast"] = (
            f"error: {last_error}" if village_status == "error" and last_error else village_status
        )
        if not village_forecasts and self.data and "village" in self.data:
            data["village"] = self.data["village"]
            refresh_meta["village_stale"] = True
            _LOGGER.debug("동네예보 데이터가 비어 있어 이전 값을 유지합니다.")
        else:
            data["village"] = village_forecasts

        # 1-2. 초단기실황/초단기예보 — 현재 날씨를 실측 기반으로 표시.
        # 실패하면 이전 값을 유지하고, 그래도 없으면 단기예보로 폴백한다(get_current).
        try:
            ncst = await self.client.async_get_ultra_ncst(self.nx, self.ny)
        except KmaApiError as err:
            _LOGGER.debug("초단기실황(getUltraSrtNcst) 실패: %s", err)
            ncst = None
        if ncst is None and (self.data or {}).get("ncst") is not None:
            refresh_meta["ncst_stale"] = True
        data["ncst"] = ncst or (self.data or {}).get("ncst")

        try:
            ultra = await self.client.async_get_ultra_fcst(self.nx, self.ny)
        except KmaApiError as err:
            _LOGGER.debug("초단기예보(getUltraSrtFcst) 실패: %s", err)
            ultra = []
        if not ultra and (self.data or {}).get("ultra"):
            refresh_meta["ultra_stale"] = True
        data["ultra"] = ultra or (self.data or {}).get("ultra", [])

        # 2. 육상예보 (fct_afs_dl.php)
        land, status["land_forecast"] = await self._fetch_optional(
            "육상예보", self.client.async_get_land_forecast(self.land_reg), default=[]
        )
        if not land and self.data and "land" in self.data:
            data["land"] = self.data["land"]
            refresh_meta["land_stale"] = True
            _LOGGER.debug("육상예보 데이터가 비어 있어 이전 값을 유지합니다.")
        else:
            data["land"] = land

        # 3. 해상예보 (fct_afs_do.php)
        marine, status["marine_forecast"] = await self._fetch_optional(
            "해상예보", self.client.async_get_marine_forecast(self.marine_reg), default=[]
        )
        if not marine and self.data and "marine" in self.data:
            data["marine"] = self.data["marine"]
            refresh_meta["marine_stale"] = True
            _LOGGER.debug("해상예보 데이터가 비어 있어 이전 값을 유지합니다.")
        else:
            data["marine"] = marine

        # 3-2. PM10(미세먼지) 관측 (kma_pm10.php) [실측 검증 2026-07-01]
        pm10_obs, status["pm10"] = await self._fetch_optional(
            "미세먼지(PM10)", self.client.async_get_pm10_now(stn=self.stn), default=None
        )
        if pm10_obs is None and self.data and "pm10" in self.data:
            data["pm10"] = self.data["pm10"]
            refresh_meta["pm10_stale"] = True
            _LOGGER.debug("PM10 데이터가 없어 이전 값을 유지합니다.")
        else:
            data["pm10"] = pm10_obs

        # 3-3. 자외선지수/대기정체지수 (연중 제공 — 실패 시 이전 값 유지)
        uv_obs, status["uv_index"] = await self._fetch_optional(
            "자외선지수", self.client.async_get_uv_index(area_no=self.area_no), default=None
        )
        if uv_obs is None and self.data and "uv_index" in self.data:
            data["uv_index"] = self.data["uv_index"]
            refresh_meta["uv_index_stale"] = True
        else:
            data["uv_index"] = uv_obs

        air_obs, status["air_stagnation"] = await self._fetch_optional(
            "대기정체지수", self.client.async_get_air_stagnation_index(area_no=self.area_no), default=None
        )
        if air_obs is None and self.data and "air_stagnation" in self.data:
            data["air_stagnation"] = self.data["air_stagnation"]
            refresh_meta["air_stagnation_stale"] = True
        else:
            data["air_stagnation"] = air_obs

        # 3-4. 꽃가루농도위험지수 3종 (계절 서비스 — 비시즌 None은 정상 상태이므로
        # 이전 값을 이어붙이지 않는다. 이어붙이면 시즌 종료 후에도 옛 값이 남아 오해를 준다).
        oak_obs, status["oak_pollen"] = await self._fetch_optional(
            "꽃가루(참나무)", self.client.async_get_oak_pollen_risk(area_no=self.area_no), default=None
        )
        data["oak_pollen"] = oak_obs

        pine_obs, status["pine_pollen"] = await self._fetch_optional(
            "꽃가루(소나무)", self.client.async_get_pine_pollen_risk(area_no=self.area_no), default=None
        )
        data["pine_pollen"] = pine_obs

        weed_obs, status["weed_pollen"] = await self._fetch_optional(
            "꽃가루(잡초류)", self.client.async_get_weed_pollen_risk(area_no=self.area_no), default=None
        )
        data["weed_pollen"] = weed_obs

        # 3-5. 행정구역별 레이더 강수강도 (WthrRadarInfoService/getCompCappiQcdArea)
        # 실측 결과 특정 지역(광주, 구코드 2900000000 — 통합특별시 개편으로 대체된
        # 레거시 코드)에서 간헐적으로 오류가 발생함이 확인되어(2026-07-01), 실패 시
        # 이전 값을 유지한다.
        radar_obs, status["radar_precipitation"] = await self._fetch_optional(
            "레이더 강수강도",
            self.client.async_get_radar_precipitation(dong_code=self.area_no),
            default=None,
        )
        if radar_obs is None and self.data and "radar_precipitation" in self.data:
            data["radar_precipitation"] = self.data["radar_precipitation"]
            refresh_meta["radar_precipitation_stale"] = True
        else:
            data["radar_precipitation"] = radar_obs

        # 4. 특보현황 (wrn_now_data.php)
        warnings, status["warning_now"] = await self._fetch_optional(
            "기상특보", self.client.async_get_warning_now(), default=[]
        )
        # 특보 호출 실패 시에는 이전 특보 데이터를 유지하고, 성공했으나 내용이 없는 경우는 빈 목록으로 업데이트합니다.
        if status["warning_now"].startswith("error") and self.data and "warnings" in self.data:
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

        # API별 에러 카운트 / 마지막 에러 시각 업데이트 (UpdateFailed 이전에 기록해야 함)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        for api_key, api_stat in status.items():
            if isinstance(api_stat, str) and api_stat.startswith("error"):
                self._api_error_counts[api_key] = self._api_error_counts.get(api_key, 0) + 1
                self._api_last_error_time[api_key] = now_utc

        # 핵심 데이터인 동네예보(village)가 연결 오류(error)이거나 모든 API가 연결 오류면
        # 통합 단위 실패(UpdateFailed)로 처리하여 센서를 '사용 불가(오류)' 상태로 표시하고 재시도를 유도합니다.
        # (미신청/NODATA는 정상 동작 범위로 보고 실패시키지 않습니다.)
        if status.get("village_forecast", "").startswith("error"):
            raise UpdateFailed("동네예보 API 호출이 실패했습니다.")
        if status and all(isinstance(v, str) and v.startswith("error") for v in status.values()):
            raise UpdateFailed("모든 기상청 API 호출이 실패했습니다.")

        self._refresh_meta = refresh_meta
        return data

    async def _fetch_optional(
        self, label: str, coro: Any, *, default: Any = None
    ) -> tuple[Any, str]:
        """선택적 API 호출을 수행하고 (결과, 상태)를 반환한다.

        상태: "ok" | "not_applied"(403) | "error: 메시지". 실패 시 결과는 default.
        """
        try:
            return await coro, "ok"
        except KmaActivationRequiredError:
            _LOGGER.warning("%s API 미신청(403). 활용신청이 필요합니다.", label)
            return default, "not_applied"
        except KmaApiError as err:
            _LOGGER.warning("%s 업데이트 경고: %s", label, err)
            return default, f"error: {err}"

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

    @property
    def refresh_meta(self) -> dict[str, bool]:
        """마지막 갱신에서 이전 값을 유지한 데이터 항목 여부."""
        return dict(self._refresh_meta)

    def _nearest_village(self) -> VillageForecast | None:
        """현재 시각에 가장 가까운 동네예보 레코드(폴백/POP용)."""
        village: list[VillageForecast] = (self.data or {}).get("village", [])
        if not village:
            return None
        now = datetime.datetime.now()
        best, best_diff = None, None
        for vf in village:
            try:
                vdt = datetime.datetime.strptime(f"{vf.fcst_date}{vf.fcst_time}", "%Y%m%d%H%M")
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
                dt = datetime.datetime.strptime(key, "%Y%m%d%H%M")
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
                dt = datetime.datetime.strptime(key, "%Y%m%d%H%M")
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
        now = datetime.datetime.now()
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
            dt = datetime.datetime.strptime(base_date + base_time, "%Y%m%d%H%M")
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


class KmaImageCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """레이더/위성/강수예측 이미지 코디네이터 (허브 단위, Zone과 무관한 전국 이미지 세트).

    ImageEntity는 `image_last_updated`를 코디네이터 갱신 시점에만 바꿔야 하므로
    (async_image 내부에서 바꾸면 순환 트리거가 됨), 바이트 페칭은 여기서 수행하고
    엔티티는 캐시된 바이트만 반환한다.

    이미지들 모두 게시 지연이 있어(레이더/강수예측 ~20분, 위성 거의 없음) 아직
    게시되지 않은 경우 async_get_*_image()가 None을 반환한다 — 이때는 이전 값을
    유지한다.
    """

    def __init__(self, hass: HomeAssistant, client: KmaApiClient, config_entry: ConfigEntry) -> None:
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_image",
            update_interval=timedelta(minutes=10),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """레이더/위성/강수예측 최신 이미지를 조회. 실패/미게시 시 이전 값을 유지."""
        data: dict[str, Any] = dict(
            self.data or {"radar": None, "satellite": None, "precipitation_forecast": None}
        )

        try:
            radar = await self.client.async_get_radar_image()
            if radar is not None:
                data["radar"] = radar
        except KmaActivationRequiredError:
            _LOGGER.warning("레이더 이미지 API 미신청(403). 활용신청이 필요합니다.")
        except KmaApiError as err:
            _LOGGER.debug("레이더 이미지 갱신 실패: %s", err)

        try:
            satellite = await self.client.async_get_satellite_image()
            if satellite is not None:
                data["satellite"] = satellite
        except KmaActivationRequiredError:
            _LOGGER.warning("위성 이미지 API 미신청(403). 활용신청이 필요합니다.")
        except KmaApiError as err:
            _LOGGER.debug("위성 이미지 갱신 실패: %s", err)

        try:
            precip_forecast = await self.client.async_get_precipitation_forecast_image()
            if precip_forecast is not None:
                data["precipitation_forecast"] = precip_forecast
        except KmaActivationRequiredError:
            _LOGGER.warning("강수예측 이미지 API 미신청(403). 활용신청이 필요합니다.")
        except KmaApiError as err:
            _LOGGER.debug("강수예측 이미지 갱신 실패: %s", err)

        return data
