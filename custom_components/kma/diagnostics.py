"""KMA 통합 구성요소 진단 정보."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import API_STATUS_HUB_KEYS, API_STATUS_IMAGE_KEYS, DOMAIN
from .coordinator import KmaForecastCoordinator, KmaHubCoordinator, KmaImageCoordinator

REDACT_KEYS = ("auth_key", "authKey")


def _image_diagnostics(coordinator: KmaImageCoordinator) -> dict[str, Any]:
    """허브 단위 이미지 코디네이터(레이더/위성/강수예측) 진단 스냅샷을 구성한다."""
    data = coordinator.data or {}
    return {
        "api_status": coordinator.api_status,
        "api_error_counts": coordinator.api_error_counts,
        "api_last_error_times": {
            key: dt_util.as_local(value).isoformat() if value is not None else None
            for key, value in coordinator.api_last_error_times.items()
        },
        "image_available": {key: data.get(key) is not None for key in API_STATUS_IMAGE_KEYS},
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
        },
    }


def _hub_diagnostics(coordinator: KmaHubCoordinator) -> dict[str, Any]:
    """허브 단위 비-이미지 코디네이터(지진/태풍) 진단 스냅샷을 구성한다."""
    data = coordinator.data or {}
    return {
        "api_status": coordinator.api_status,
        "api_error_counts": coordinator.api_error_counts,
        "api_last_error_times": {
            key: dt_util.as_local(value).isoformat() if value is not None else None
            for key, value in coordinator.api_last_error_times.items()
        },
        "data_available": {key: data.get(key) is not None for key in API_STATUS_HUB_KEYS},
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
        },
    }


def _zone_diagnostics(
    coordinator: KmaForecastCoordinator, subentry_id: str, subentry_data: dict[str, Any]
) -> dict[str, Any]:
    """Zone 코디네이터 기준 진단 스냅샷을 구성한다."""
    data = coordinator.data or {}
    current = coordinator.get_current()

    return {
        "subentry_id": subentry_id,
        "zone_id": subentry_data.get("zone_id"),
        "zone_name": subentry_data.get("zone_name"),
        "nx": subentry_data.get("nx"),
        "ny": subentry_data.get("ny"),
        "land_reg": subentry_data.get("land_reg"),
        "marine_reg": subentry_data.get("marine_reg"),
        "current_data_source": current.source,
        "api_status": coordinator.api_status,
        "api_error_counts": coordinator.api_error_counts,
        "api_last_error_times": {
            key: dt_util.as_local(value).isoformat() if value is not None else None
            for key, value in coordinator.api_last_error_times.items()
        },
        "data_refresh": coordinator.refresh_meta,
        "record_counts": {
            "village": len(data.get("village") or []),
            "ultra": len(data.get("ultra") or []),
            "land": len(data.get("land") or []),
            "marine": len(data.get("marine") or []),
            "warnings": len(data.get("warnings") or []),
        },
        "pm10_available": data.get("pm10") is not None,
        "uv_index_available": data.get("uv_index") is not None,
        "air_stagnation_available": data.get("air_stagnation") is not None,
        "oak_pollen_available": data.get("oak_pollen") is not None,
        "pine_pollen_available": data.get("pine_pollen") is not None,
        "weed_pollen_available": data.get("weed_pollen") is not None,
        "radar_precipitation_available": data.get("radar_precipitation") is not None,
        "sfc_observation_available": data.get("sfc_observation") is not None,
        "heat_wave_risk_available": data.get("heat_wave_risk") is not None,
        "cold_wave_risk_available": data.get("cold_wave_risk") is not None,
        "hazard_info_available": data.get("hazard_info") is not None,
        "weather_commentary_available": data.get("weather_commentary") is not None,
        "snow_depth_available": data.get("snow_depth") is not None,
        "pm10_hourly_available": data.get("pm10_hourly") is not None,
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """통합 설정 > 진단 정보 다운로드용 JSON을 반환한다."""
    from homeassistant.components.diagnostics import async_redact_data

    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinators: dict[str, KmaForecastCoordinator] = store.get("coordinators", {})
    image_coordinator: KmaImageCoordinator | None = store.get("image_coordinator")
    hub_coordinator: KmaHubCoordinator | None = store.get("hub_coordinator")

    zones = {
        subentry_id: _zone_diagnostics(
            coordinator,
            subentry_id,
            entry.subentries[subentry_id].data,
        )
        for subentry_id, coordinator in coordinators.items()
    }

    return async_redact_data(
        {
            "entry": {
                "entry_id": entry.entry_id,
                "scan_interval_minutes": entry.options.get("scan_interval", 10),
                "zone_count": len(zones),
            },
            "zones": zones,
            "images": _image_diagnostics(image_coordinator) if image_coordinator else None,
            "hub": _hub_diagnostics(hub_coordinator) if hub_coordinator else None,
        },
        REDACT_KEYS,
    )
