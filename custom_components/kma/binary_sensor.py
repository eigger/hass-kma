"""기상청(KMA) 바이너리 센서(Binary Sensor) 플랫폼 구현."""
from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KmaForecastCoordinator

_LOGGER = logging.getLogger(__name__)

# 허브(부모 엔트리) 단위로 활용신청 상태를 표시할 API 목록.
# 키는 coordinator.data["api_status"] 및 translation_key(activation_*)와 일치.
API_STATUS_KEYS = [
    "village_forecast",
    "land_forecast",
    "marine_forecast",
    "warning_now",
]

# 특보 종류 및 등급 매핑 (다국어 지원)
WARNING_TYPES_KO = {
    "강풍": "강풍",
    "호우": "호우",
    "한파": "한파",
    "건조": "건조",
    "폭풍해일": "폭풍해일",
    "풍랑": "풍랑",
    "태풍": "태풍",
    "대설": "대설",
    "황사": "황사",
    "폭염": "폭염",
    "W": "강풍",
    "R": "호우",
    "C": "한파",
    "D": "건조",
    "O": "폭풍해일",
    "V": "풍랑",
    "T": "태풍",
    "S": "대설",
    "H": "폭염",
    "Y": "황사",
}

WARNING_TYPES_EN = {
    "강풍": "Gale",
    "호우": "Heavy Rain",
    "한파": "Cold Wave",
    "건조": "Dry",
    "폭풍해일": "Storm Surge",
    "풍랑": "High Waves",
    "태풍": "Typhoon",
    "대설": "Heavy Snow",
    "황사": "Yellow Dust",
    "폭염": "Heat Wave",
    "W": "Gale",
    "R": "Heavy Rain",
    "C": "Cold Wave",
    "D": "Dry",
    "O": "Storm Surge",
    "V": "High Waves",
    "T": "Typhoon",
    "S": "Heavy Snow",
    "H": "Heat Wave",
    "Y": "Yellow Dust",
}

WARNING_LEVELS_KO = {
    "주의": "주의보",
    "주의보": "주의보",
    "경보": "경보",
    "1": "주의보",
    "2": "경보",
}

WARNING_LEVELS_EN = {
    "주의": "Advisory",
    "주의보": "Advisory",
    "경보": "Warning",
    "1": "Advisory",
    "2": "Warning",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Zone 서브엔트리별 특보 센서 + 허브 단위 활용신청 상태 센서 추가."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, KmaForecastCoordinator] = store["coordinators"]

    for subentry_id, coordinator in coordinators.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [
                KmaWarningBinarySensor(coordinator, subentry),
                KmaPrecipitationBinarySensor(coordinator, subentry),
            ],
            config_subentry_id=subentry_id,
        )

    # 허브(통합) 기기: API별 활용신청 상태 진단 센서.
    # Zone 호출 피드백을 그대로 사용하므로, 임의의(첫) Zone 코디네이터에 연결한다.
    if coordinators:
        rep_coordinator = next(iter(coordinators.values()))
        async_add_entities(
            [
                KmaApiStatusBinarySensor(rep_coordinator, entry, key)
                for key in API_STATUS_KEYS
            ]
        )


class KmaWarningBinarySensor(CoordinatorEntity[KmaForecastCoordinator], BinarySensorEntity):
    """기상청 특보 경보 바이너리 센서."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self, coordinator: KmaForecastCoordinator, subentry: ConfigSubentry
    ) -> None:
        """바이너리 센서 구성원 초기화."""
        super().__init__(coordinator)
        self._attr_translation_key = "warning"
        self._attr_unique_id = f"{subentry.subentry_id}_warning"

        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    @property
    def is_on(self) -> bool:
        """특보 발효 중이면 True 반환."""
        warnings = self.coordinator.data.get("warnings", [])
        return len(warnings) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """특보 상세 내역 속성 반환."""
        warnings = self.coordinator.data.get("warnings", [])
        
        # 언어 판단 (한국어 설정 여부 확인)
        lang = "en"
        if self.hass and hasattr(self.hass, "config") and self.hass.config.language == "ko":
            lang = "ko"

        warnings_detail = []
        for w in warnings:
            wrn_code = w.get("WRN", "")
            lvl_code = w.get("LVL", "")
            
            if lang == "ko":
                wrn_name = WARNING_TYPES_KO.get(wrn_code, wrn_code)
                lvl_name = WARNING_LEVELS_KO.get(lvl_code, lvl_code)
            else:
                wrn_name = WARNING_TYPES_EN.get(wrn_code, wrn_code)
                lvl_name = WARNING_LEVELS_EN.get(lvl_code, lvl_code)
            
            warnings_detail.append(
                {
                    "region": w.get("REG_KO"),
                    "warning_code": wrn_code,
                    "warning_name": wrn_name,
                    "level_code": lvl_code,
                    "level_name": lvl_name,
                    "effective_time": w.get("TM_EF"),
                    "release_time": w.get("TM_FC"),
                }
            )
            
        return {
            "warnings_count": len(warnings),
            "active_warnings": warnings_detail,
        }


PRECIP_WINDOW_HOURS = 6

PTY_NAMES_KO = {
    "1": "비", "2": "비/눈", "3": "눈", "4": "소나기",
    "5": "빗방울", "6": "빗방울/눈날림", "7": "눈날림",
}


class KmaPrecipitationBinarySensor(
    CoordinatorEntity[KmaForecastCoordinator], BinarySensorEntity
):
    """향후 일정 시간 내 강수(비/눈) 예보 여부. 자동화 트리거용.

    on  = 향후 PRECIP_WINDOW_HOURS 시간 내 강수 예보 있음
    속성 = 유형/시작시각/강수확률/예상량/남은시간
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: KmaForecastCoordinator, subentry: ConfigSubentry
    ) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = "precipitation_expected"
        self._attr_unique_id = f"{subentry.subentry_id}_precipitation_expected"
        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    def _next(self):
        nxt = self.coordinator.next_precipitation()
        if nxt is None:
            return None
        hours = (nxt.dt - datetime.datetime.now()).total_seconds() / 3600.0
        return nxt, hours

    @property
    def is_on(self) -> bool:
        result = self._next()
        return result is not None and result[1] <= PRECIP_WINDOW_HOURS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self._next()
        if result is None:
            return {"window_hours": PRECIP_WINDOW_HOURS}
        nxt, hours = result
        return {
            "window_hours": PRECIP_WINDOW_HOURS,
            "start_time": dt_util.as_local(nxt.dt).isoformat(),
            "type": PTY_NAMES_KO.get(nxt.pty, "강수"),
            "type_code": nxt.pty,
            "precipitation_probability": nxt.pop,
            "precipitation_amount": nxt.pcp,
            "hours_until": round(hours, 1),
        }


class KmaApiStatusBinarySensor(
    CoordinatorEntity[KmaForecastCoordinator], BinarySensorEntity
):
    """허브 단위 API 활용신청/접근 상태 진단 센서.

    on  = 정상 응답(활용신청 완료)
    off = 미신청(403)/오류 — status 속성으로 상세 구분
    """

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: KmaForecastCoordinator,
        entry: ConfigEntry,
        api_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._api_key = api_key
        self._attr_translation_key = f"activation_{api_key}"
        self._attr_unique_id = f"{entry.entry_id}_activation_{api_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="기상청 APIhub",
            manufacturer="Korea Meteorological Administration",
            model="API Hub",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """해당 API가 정상 응답하면 True."""
        return self.coordinator.api_status.get(self._api_key) == "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """상세 상태(ok/not_applied/error/unknown)."""
        return {"status": self.coordinator.api_status.get(self._api_key, "unknown")}
