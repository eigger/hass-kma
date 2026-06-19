"""DataUpdateCoordinator for KMA integration."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, PROVINCE_WARNING_KEYWORDS
from .api import KmaApiClient, KmaApiError, KmaActivationRequiredError

_LOGGER = logging.getLogger(__name__)


class KmaForecastCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """KMA 예·특보 데이터 코디네이터."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: KmaApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """코디네이터 초기화."""
        self.client = client
        self.config_entry = config_entry
        self.nx = config_entry.data["nx"]
        self.ny = config_entry.data["ny"]
        self.land_reg = config_entry.data["land_reg"]
        self.marine_reg = config_entry.data["marine_reg"]

        scan_interval = config_entry.options.get("scan_interval", 10)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_forecast_{self.land_reg}",
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """기상청 API로부터 실시간 예보 및 특보 데이터를 가져옵니다."""
        data: dict[str, Any] = {}

        # 1. 동네예보 (getVilageFcst)
        try:
            # 기상청 단기예보 발표 시각은 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 입니다.
            # 가장 최근 발표 기준 시각을 실시간 계산
            now = datetime.datetime.now()
            base_date, base_time = self._get_latest_forecast_time(now)
            
            village_forecasts = await self.client.async_get_village_forecast(
                self.nx, self.ny, base_date=base_date, base_time=base_time
            )
            data["village"] = village_forecasts
        except KmaApiError as err:
            _LOGGER.error("기상청 동네예보(getVilageFcst) 업데이트 실패: %s", err)
            raise UpdateFailed(f"동네예보 업데이트 실패: {err}") from err

        # 2. 육상예보 (fct_afs_dl.php)
        try:
            land_forecasts = await self.client.async_get_land_forecast(self.land_reg)
            data["land"] = land_forecasts
        except KmaApiError as err:
            _LOGGER.warning("기상청 육상예보(fct_afs_dl) 업데이트 경고: %s", err)
            data["land"] = []

        # 3. 해상예보 (fct_afs_do.php)
        try:
            marine_forecasts = await self.client.async_get_marine_forecast(self.marine_reg)
            data["marine"] = marine_forecasts
        except KmaApiError as err:
            _LOGGER.warning("기상청 해상예보(fct_afs_do) 업데이트 경고: %s", err)
            data["marine"] = []

        # 4. 특보현황 (wrn_now_data.php)
        try:
            warnings = await self.client.async_get_warning_now()
            # 내 구역에 대한 특보만 필터링 (광역 매핑)
            my_warnings = []
            keywords = PROVINCE_WARNING_KEYWORDS.get(self.land_reg, [])
            
            for w in warnings:
                reg_up_ko = w.get("REG_UP_KO", "")
                reg_ko = w.get("REG_KO", "")
                
                match = False
                for kw in keywords:
                    if kw in reg_up_ko or kw in reg_ko:
                        match = True
                        break
                
                if match:
                    my_warnings.append(w)
            data["warnings"] = my_warnings
        except KmaActivationRequiredError:
            # 특보 API가 미신청(403) 상태인 경우 경고만 기록하고 우회
            _LOGGER.warning("기상특보 API가 활성화되지 않았습니다. 활용 신청 후 승인이 필요합니다.")
            data["warnings"] = []
        except KmaApiError as err:
            _LOGGER.warning("기상특보(wrn_now_data) 업데이트 경고: %s", err)
            data["warnings"] = []

        return data

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
