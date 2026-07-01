"""diagnostics.py 단위 테스트."""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock

from custom_components.kma.diagnostics import _zone_diagnostics


def test_zone_diagnostics_includes_mapping_and_source() -> None:
    coordinator = MagicMock()
    coordinator.data = {
        "village": [1, 2],
        "ultra": [1],
        "land": [],
        "marine": [],
        "warnings": [],
    }
    coordinator.get_current.return_value = MagicMock(source="village")
    coordinator.api_status = {"village_forecast": "ok"}
    coordinator.api_error_counts = {"village_forecast": 0}
    coordinator.api_last_error_times = {"village_forecast": None}
    coordinator.refresh_meta = {"village_stale": True, "ncst_stale": False}
    coordinator.last_update_success = True
    coordinator.last_exception = None

    result = _zone_diagnostics(
        coordinator,
        "zone-1",
        {
            "zone_id": "zone.home",
            "zone_name": "Home",
            "nx": 55,
            "ny": 127,
            "land_reg": "11B10101",
            "marine_reg": "12A20100",
        },
    )

    assert result["current_data_source"] == "village"
    assert result["nx"] == 55
    assert result["data_refresh"]["village_stale"] is True
    assert result["record_counts"]["village"] == 2


def test_zone_diagnostics_formats_last_error_time() -> None:
    coordinator = MagicMock()
    coordinator.data = {}
    coordinator.get_current.return_value = MagicMock(source="none")
    coordinator.api_status = {}
    coordinator.api_error_counts = {}
    ts = datetime.datetime(2026, 7, 1, 12, 0, tzinfo=datetime.timezone.utc)
    coordinator.api_last_error_times = {"village_forecast": ts}
    coordinator.refresh_meta = {}
    coordinator.last_update_success = False
    coordinator.last_exception = RuntimeError("boom")

    result = _zone_diagnostics(coordinator, "zone-1", {})

    assert result["api_last_error_times"]["village_forecast"] is not None
    assert result["coordinator"]["last_exception"] == "boom"
