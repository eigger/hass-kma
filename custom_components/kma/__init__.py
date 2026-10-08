"""기상청(KMA) 통합 구성요소 초기화.

부모 엔트리는 API 클라이언트를 공유하고, Zone 서브엔트리마다 코디네이터를 둔다.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType

from .api import KmaApiClient
from .const import (
    CONF_AWS_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_AWS_STATION,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import (
    KmaAwsCoordinator,
    KmaForecastCoordinator,
    KmaHubCoordinator,
    KmaImageCoordinator,
)
from .helpers import parse_aws_station_id

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.WEATHER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.IMAGE,
]


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
    aws_coordinators: dict[str, KmaAwsCoordinator] = {}
    refreshes = []
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_ZONE:
            coordinator = KmaForecastCoordinator(hass, client, entry, subentry)
            coordinator.hub_device_id = hub_device.id
            coordinators[subentry_id] = coordinator
            refreshes.append(coordinator.async_config_entry_first_refresh())
        elif subentry.subentry_type == SUBENTRY_TYPE_AWS_STATION:
            # AWS 관측소는 Zone과 독립 서브엔트리다. 지점번호는 생성 시 검증되어
            # 저장되며, 손상된 값은 건너뛴다(셋업을 깨지 않는다).
            try:
                station = parse_aws_station_id(subentry.data.get(CONF_AWS_STATION_ID))
            except ValueError:
                station = None
            if station is None:
                _LOGGER.warning(
                    "AWS 관측소 서브엔트리 %s의 지점번호가 유효하지 않아 건너뜁니다.",
                    subentry_id,
                )
                continue
            aws_coordinator = KmaAwsCoordinator(hass, client, entry, subentry)
            aws_coordinator.hub_device_id = hub_device.id
            aws_coordinators[subentry_id] = aws_coordinator
            refreshes.append(aws_coordinator.async_config_entry_first_refresh())

    image_coordinator = KmaImageCoordinator(hass, client, entry)
    image_coordinator.hub_device_id = hub_device.id
    hub_coordinator = KmaHubCoordinator(hass, client, entry)
    hub_coordinator.hub_device_id = hub_device.id
    # AWS 관측소 코디네이터가 실제 시도 결과를 허브 집계에 보고하도록 연결한다.
    # (첫 refresh 전에 연결해야 첫 시도부터 집계에 반영된다.)
    for aws_coordinator in aws_coordinators.values():
        aws_coordinator.hub_coordinator = hub_coordinator
    refreshes.append(image_coordinator.async_config_entry_first_refresh())
    refreshes.append(hub_coordinator.async_config_entry_first_refresh())
    await asyncio.gather(*refreshes)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinators": coordinators,
        "aws_coordinators": aws_coordinators,
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
