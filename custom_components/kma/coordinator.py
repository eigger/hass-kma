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
        # 기상청 단기예보 발표 시각은 0200, 0500, 0800, 1100, 1400, 1700, 2000, 2300 입니다.
        # 가장 최근 발표분이 아직 게시 전(NODATA)일 수 있으므로 이전 발표시각으로 backoff 재시도합니다.
        now = datetime.datetime.now()
        village_forecasts: list = []
        last_err: KmaApiError | None = None
        for base_date, base_time in self._iter_forecast_base_times(now):
            try:
                village_forecasts = await self.client.async_get_village_forecast(
                    self.nx, self.ny, base_date=base_date, base_time=base_time
                )
            except KmaActivationRequiredError:
                # 활용신청/키 문제는 즉시 표면화 (backoff로 해결되지 않음)
                raise
            except KmaApiError as err:
                last_err = err
                _LOGGER.debug("동네예보 base_time=%s%s 호출 실패: %s", base_date, base_time, err)
                continue
            if village_forecasts:
                break

        if not village_forecasts and last_err is not None:
            # 모든 후보 발표시각에서 연결/오류 → 통합 단위 실패로 표면화하여 재시도 유도
            _LOGGER.error("기상청 동네예보(getVilageFcst) 업데이트 실패: %s", last_err)
            raise UpdateFailed(f"동네예보 업데이트 실패: {last_err}") from last_err

        if not village_forecasts:
            _LOGGER.warning("기상청 동네예보 데이터가 비어 있습니다(NODATA). 다음 주기에 재시도합니다.")
        data["village"] = village_forecasts

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
