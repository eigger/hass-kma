"""KMA 통합 구성요소 진단 정보."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import KmaForecastCoordinator

REDACT_KEYS = ("auth_key", "authKey")


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
        },
        REDACT_KEYS,
    )
