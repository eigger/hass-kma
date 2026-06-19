"""기상청(KMA) 통합 구성요소 초기화."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .api import KmaApiClient
from .coordinator import KmaForecastCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.WEATHER, Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """설정 엔트리 초기화."""
    session = async_get_clientsession(hass)
    client = KmaApiClient(session, entry.data["auth_key"])

    coordinator = KmaForecastCoordinator(hass, client, entry)

    # 최초 데이터 강제 동기화 (오류 발생 시 통합 구성요소 셋업 실패 처리)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 옵션 업데이트 리스너 등록
    entry.async_on_unload(entry.add_update_listener(update_listener))

    # 하위 플랫폼(Weather, Sensor, Binary Sensor) 등록
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """옵션 변경 시 코디네이터의 업데이트 주기를 갱신합니다."""
    coordinator: KmaForecastCoordinator = hass.data[DOMAIN][entry.entry_id]
    scan_interval = entry.options.get("scan_interval", 10)
    from datetime import timedelta
    coordinator.update_interval = timedelta(minutes=scan_interval)
    _LOGGER.info("KMA 통합구성요소 갱신 주기가 %d분으로 변경되었습니다.", scan_interval)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """설정 엔트리 제거/언로드."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
