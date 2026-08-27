"""기상청(KMA) 통합 구성요소 초기화.

부모 엔트리는 API 클라이언트를 공유하고, Zone 서브엔트리마다 코디네이터를 둔다.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType

from .api import KmaApiClient
from .const import DOMAIN
from .coordinator import KmaForecastCoordinator, KmaHubCoordinator, KmaImageCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.WEATHER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
]

SUBENTRY_TYPE_ZONE = "zone"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """부모 엔트리 셋업: 키 검증 후 Zone 서브엔트리별 코디네이터 생성."""

    session = async_get_clientsession(hass)
    client = KmaApiClient(session, entry.data["auth_key"])

    # Zone 디바이스들이 via_device_id로 참조할 허브 디바이스를 플랫폼 셋업 전에
    # 미리 등록해둔다. 플랫폼들은 async_forward_entry_setups로 동시에 셋업되므로,
    # 허브 디바이스가 각 플랫폼의 진단 엔티티를 통해 뒤늦게 생성되는 것에 기대면
    # via_device_id가 아직 없는 디바이스 id를 참조해 DeviceInfoError가 날 수 있다.
    hub_device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="기상청 APIhub",
        manufacturer="Korea Meteorological Administration",
        model="API Hub",
        entry_type=DeviceEntryType.SERVICE,
    )

    coordinators: dict[str, KmaForecastCoordinator] = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            continue
        coordinator = KmaForecastCoordinator(hass, client, entry, subentry)
        coordinator.hub_device_id = hub_device.id
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry_id] = coordinator

    image_coordinator = KmaImageCoordinator(hass, client, entry)
    image_coordinator.hub_device_id = hub_device.id
    await image_coordinator.async_config_entry_first_refresh()

    hub_coordinator = KmaHubCoordinator(hass, client, entry)
    hub_coordinator.hub_device_id = hub_device.id
    await hub_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinators": coordinators,
        "image_coordinator": image_coordinator,
        "hub_coordinator": hub_coordinator,
        "hub_device_id": hub_device.id,
    }

    # 옵션/서브엔트리 변경 시 리로드
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """옵션 변경 또는 Zone 서브엔트리 추가/삭제 시 통합을 다시 로드한다."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """부모 엔트리 언로드."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
