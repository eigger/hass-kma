"""기상청(KMA) 통합 구성요소 초기화.

부모 엔트리는 API 클라이언트를 공유하고, Zone 서브엔트리마다 코디네이터를 둔다.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .api import KmaApiClient
from .coordinator import KmaForecastCoordinator, KmaImageCoordinator

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

    coordinators: dict[str, KmaForecastCoordinator] = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            continue
        coordinator = KmaForecastCoordinator(hass, client, entry, subentry)
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry_id] = coordinator

    image_coordinator = KmaImageCoordinator(hass, client, entry)
    await image_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinators": coordinators,
        "image_coordinator": image_coordinator,
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
