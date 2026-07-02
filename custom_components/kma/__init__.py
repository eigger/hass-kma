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
    """이 통합(domain=kma) 소속 고아 엔티티/기기를 레지스트리 전체에서 정리한다.

    세 가지 경우를 잡는다:
    1. **삭제된 config entry에 남은 잔재**: "통합을 통째로 삭제 후 재설치"하면
       매번 새 entry_id가 발급되는데, 예전 entry_id에 연결된 엔티티가 어떤
       이유로든(정상적인 core 정리가 실패하는 등) 레지스트리에 남을 수 있다.
       이런 항목은 config_entry_id가 "현재 로드된 kma entry 중 하나"에 아예
       속하지 않으므로 무조건 고아다. (실측 확인 2026-07-02: entry_id로만
       필터링하면 이 케이스를 놓쳐서, 재설치할 때마다 고아가 쌓이고 entity_id
       뒤에 `_2`, `_3`, ... 로 계속 번호가 늘어나는 문제가 있었음 — 이전 수정의
       버그였고 이번에 전체 레지스트리를 훑도록 범위를 넓혀 수정.)
    2. **삭제된 Zone 서브엔트리에 남은 잔재**: Zone을 삭제 후 재추가하면 새
       subentry_id가 발급되는데, 옛 subentry_id로 등록된 엔티티가 남을 수 있다.
    3. **옛 허브 이미지 엔티티**: 허브 디바이스에 레이더/위성 이미지를 두던
       시기(524acc2 이전)의 unique_id.

    entity_id는 전역에서 유일해야 하므로, 위 고아들이 하나라도 남아있으면 같은
    이름을 쓰는 정상 엔티티가 매번 entity_id 뒤에 번호가 붙는 형태로 계속
    충돌한다 — 그래서 매 셋업(재시작 포함)마다 방어적으로 전체를 정리한다.
    """
    ent_reg = er.async_get(hass)
    valid_entry_ids = {e.entry_id for e in hass.config_entries.async_entries(DOMAIN)}
    valid_subentry_ids = set(entry.subentries.keys())
    legacy_hub_unique_ids = {f"{entry.entry_id}_{key}" for key in _LEGACY_HUB_IMAGE_KEYS}

    _LOGGER.info("=== KMA Registry Entities Cleanup Check ===")
    _LOGGER.info("valid_entry_ids: %s", valid_entry_ids)
    _LOGGER.info("valid_subentry_ids: %s", valid_subentry_ids)
    _LOGGER.info("legacy_hub_unique_ids: %s", legacy_hub_unique_ids)

    for entity_entry in list(ent_reg.entities.values()):
        if entity_entry.platform != DOMAIN:
            continue
        
        is_deleted_entry = entity_entry.config_entry_id not in valid_entry_ids
        is_stale_subentry = (
            entity_entry.config_entry_id == entry.entry_id
            and entity_entry.config_subentry_id is not None
            and entity_entry.config_subentry_id not in valid_subentry_ids
        )
        is_legacy_hub_image = entity_entry.unique_id in legacy_hub_unique_ids
        
        _LOGGER.info(
            "Entity: %s, unique_id: %s, subentry: %s, is_deleted: %s, is_stale: %s, is_legacy: %s",
            entity_entry.entity_id,
            entity_entry.unique_id,
            entity_entry.config_subentry_id,
            is_deleted_entry,
            is_stale_subentry,
            is_legacy_hub_image,
        )
        
        if is_deleted_entry or is_stale_subentry or is_legacy_hub_image:
            _LOGGER.info("고아 엔티티 정리 실행: %s", entity_entry.entity_id)
            ent_reg.async_remove(entity_entry.entity_id)
    _LOGGER.info("==========================================")

    dev_reg = dr.async_get(hass)
    for device_entry in list(dev_reg.devices.values()):
        if not any(ident[0] == DOMAIN for ident in device_entry.identifiers):
            continue
        if not (device_entry.config_entries & valid_entry_ids):
            _LOGGER.info("고아 기기 정리(삭제된 entry): %s (%s)", device_entry.name, device_entry.id)
            dev_reg.async_remove_device(device_entry.id)
            continue
        subentries_for_entry = device_entry.config_entries_subentries.get(entry.entry_id)
        if subentries_for_entry is None:
            continue
        # 이 기기가 (허브 포함) 최소 하나의 유효한 subentry에 연결돼 있으면 유지.
        # None은 허브 자체를 뜻하므로 항상 유효.
        if subentries_for_entry & (valid_subentry_ids | {None}):
            continue
        _LOGGER.info("고아 기기 정리(삭제된 subentry): %s (%s)", device_entry.name, device_entry.id)
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
