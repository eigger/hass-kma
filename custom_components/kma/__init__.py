"""기상청(KMA) 통합 구성요소 초기화.

부모 엔트리는 API 클라이언트를 공유하고, Zone 서브엔트리마다 코디네이터를 둔다.
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .api import KmaApiClient
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

# 2026-06-30 이전(허브 디바이스에 레이더/위성 이미지를 두던 시기)에 쓰던
# unique_id. Zone 전용으로 옮기면서(524acc2) 코드에서는 제거했지만 엔티티
# 레지스트리에는 남아 "사용할 수 없음" 상태로 영구히 고아가 되고, Zone에
# 새로 생긴 같은 이름의 엔티티와 entity_id가 충돌해 `_2`가 붙는 문제가
# 실측으로 확인됨(2026-07-02). _async_cleanup_orphaned_entities에서 정리한다.
_LEGACY_HUB_IMAGE_KEYS = ("radar_image", "satellite_image")


def _async_cleanup_orphaned_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """더 이상 존재하지 않는 Zone 서브엔트리(삭제 후 재생성 등)나 옛 허브 이미지
    엔티티에 연결된 고아 엔티티/기기를 레지스트리에서 정리한다.

    Zone을 삭제 후 다시 추가하면 새 subentry_id가 발급되는데, 옛 subentry_id로
    등록된 엔티티는 자동으로 지워지지 않고 "사용할 수 없음" 상태로 남아 같은
    이름의 새 엔티티와 entity_id가 충돌한다(`_2` 접미사) — 실측으로 확인된
    문제(2026-07-02)라 매 셋업마다 방어적으로 정리한다.
    """
    ent_reg = er.async_get(hass)
    valid_subentry_ids = set(entry.subentries.keys())
    legacy_hub_unique_ids = {f"{entry.entry_id}_{key}" for key in _LEGACY_HUB_IMAGE_KEYS}

    for entity_entry in list(ent_reg.entities.values()):
        if entity_entry.config_entry_id != entry.entry_id:
            continue
        is_stale_subentry = (
            entity_entry.config_subentry_id is not None
            and entity_entry.config_subentry_id not in valid_subentry_ids
        )
        is_legacy_hub_image = entity_entry.unique_id in legacy_hub_unique_ids
        if is_stale_subentry or is_legacy_hub_image:
            _LOGGER.info("고아 엔티티 정리: %s (unique_id=%s)", entity_entry.entity_id, entity_entry.unique_id)
            ent_reg.async_remove(entity_entry.entity_id)

    dev_reg = dr.async_get(hass)
    for device_entry in list(dev_reg.devices.values()):
        subentries_for_entry = device_entry.config_entries_subentries.get(entry.entry_id)
        if subentries_for_entry is None:
            continue
        # 이 기기가 (허브 포함) 최소 하나의 유효한 subentry에 연결돼 있으면 유지.
        # None은 허브 자체를 뜻하므로 항상 유효.
        if subentries_for_entry & (valid_subentry_ids | {None}):
            continue
        _LOGGER.info("고아 기기 정리: %s (%s)", device_entry.name, device_entry.id)
        dev_reg.async_remove_device(device_entry.id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """부모 엔트리 셋업: 키 검증 후 Zone 서브엔트리별 코디네이터 생성."""
    _async_cleanup_orphaned_entities(hass, entry)

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

    hub_coordinator = KmaHubCoordinator(hass, client, entry)
    await hub_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinators": coordinators,
        "image_coordinator": image_coordinator,
        "hub_coordinator": hub_coordinator,
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
