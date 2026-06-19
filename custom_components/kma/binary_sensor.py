"""기상청(KMA) 바이너리 센서(Binary Sensor) 플랫폼 구현."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KmaForecastCoordinator

_LOGGER = logging.getLogger(__name__)

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
    "H": "황사",
    "Y": "폭염",
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
    "H": "Yellow Dust",
    "Y": "Heat Wave",
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
    """기상청 바이너리 센서 엔티티 추가."""
    coordinator: KmaForecastCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([KmaWarningBinarySensor(coordinator, entry)])


class KmaWarningBinarySensor(CoordinatorEntity[KmaForecastCoordinator], BinarySensorEntity):
    """기상청 특보 경보 바이너리 센서."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, coordinator: KmaForecastCoordinator, entry: ConfigEntry) -> None:
        """바이너리 센서 구성원 초기화."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_translation_key = "warning"
        self._attr_unique_id = f"{entry.entry_id}_warning"
        device_name = entry.title
        if not device_name.startswith("기상청 APIhub"):
            device_name = f"기상청 APIhub ({device_name})"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
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
