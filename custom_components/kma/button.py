"""기상청(KMA) 버튼(Button) 플랫폼 구현."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KmaForecastCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Zone 서브엔트리별 버튼 엔티티 추가."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, KmaForecastCoordinator] = store["coordinators"]

    for subentry_id, coordinator in coordinators.items():
        subentry = entry.subentries[subentry_id]
        async_add_entities(
            [KmaRefreshButton(coordinator, subentry)],
            config_subentry_id=subentry_id,
        )


class KmaRefreshButton(CoordinatorEntity[KmaForecastCoordinator], ButtonEntity):
    """기상청 수동 갱신 버튼."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: KmaForecastCoordinator, subentry: ConfigSubentry
    ) -> None:
        """버튼 초기화."""
        super().__init__(coordinator)
        self._attr_translation_key = "refresh"
        self._attr_unique_id = f"{subentry.subentry_id}_refresh"

        zone_name = subentry.title or subentry.data.get("zone_name") or "KMA"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=zone_name,
            manufacturer="Korea Meteorological Administration",
            model="KMA APIhub Forecast",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
        )

    async def async_press(self) -> None:
        """버튼을 눌렀을 때 강제 업데이트 수행."""
        _LOGGER.info("기상청 데이터를 수동으로 갱신 요청합니다.")
        await self.coordinator.async_request_refresh()
