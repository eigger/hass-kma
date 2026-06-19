"""DataUpdateCoordinator for KMA integration."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PROVINCE_WARNING_KEYWORDS
from .api import KmaApiClient, KmaApiError, KmaActivationRequiredError

_LOGGER = logging.getLogger(__name__)


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
        data["village"] = village_forecasts

        # 2. 육상예보 (fct_afs_dl.php)
        data["land"], status["land_forecast"] = await self._fetch_optional(
            "육상예보", self.client.async_get_land_forecast(self.land_reg)
        )

        # 3. 해상예보 (fct_afs_do.php)
        data["marine"], status["marine_forecast"] = await self._fetch_optional(
            "해상예보", self.client.async_get_marine_forecast(self.marine_reg)
        )

        # 4. 특보현황 (wrn_now_data.php)
        warnings, status["warning_now"] = await self._fetch_optional(
            "기상특보", self.client.async_get_warning_now()
        )
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

        # 핵심 데이터인 동네예보(village)가 연결 오류(error)이거나 모든 API가 연결 오류면
        # 통합 단위 실패(UpdateFailed)로 처리하여 센서를 '사용 불가(오류)' 상태로 표시하고 재시도를 유도합니다.
        # (미신청/NODATA는 정상 동작 범위로 보고 실패시키지 않습니다.)
        if status.get("village_forecast", "").startswith("error"):
            raise UpdateFailed("동네예보 API 호출이 실패했습니다.")
        if status and all(isinstance(v, str) and v.startswith("error") for v in status.values()):
            raise UpdateFailed("모든 기상청 API 호출이 실패했습니다.")

        return data

    async def _fetch_optional(self, label: str, coro: Any) -> tuple[list, str]:
        """선택적 API 호출을 수행하고 (결과, 상태)를 반환한다.

        상태: "ok" | "not_applied"(403) | "error: 메시지". 실패 시 결과는 빈 리스트.
        """
        try:
            return await coro, "ok"
        except KmaActivationRequiredError as err:
            _LOGGER.warning("%s API 미신청(403). 활용신청이 필요합니다.", label)
            return [], "not_applied"
        except KmaApiError as err:
            _LOGGER.warning("%s 업데이트 경고: %s", label, err)
            return [], f"error: {err}"

    @property
    def api_status(self) -> dict[str, str]:
        """현재 기록된 API별 접근 상태."""
        return (self.data or {}).get("api_status", {})

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
