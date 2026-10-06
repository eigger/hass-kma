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


def _aws_coordinator() -> MagicMock:
    observed = datetime.datetime(
        2026, 7, 3, 14, 31, tzinfo=datetime.timezone(datetime.timedelta(hours=9))
    )
    coordinator = MagicMock()
    coordinator.aws_station_id = 108
    coordinator.aws_status = "error: 403 authKey=TOPSECRET rejected"
    coordinator.aws_observation_fresh = False
    coordinator.aws_observation = MagicMock(
        stn="108",
        tm="202607031431",
        observed_at=observed,
        temperature=23.1,
        humidity=71.0,
        dew_point=17.7,
        wind_dir_1m=225.0,
        wind_speed_1m=1.8,
        gust_dir=180.0,
        gust_speed=6.2,
        wind_dir_10m=190.0,
        wind_speed_10m=2.4,
        rain_15m=0.5,
        rain_60m=2.0,
        rain_12h=8.5,
        rain_day=14.0,
        pressure=1013.4,
        sea_level_pressure=1015.8,
    )
    coordinator.data = {
        "status": coordinator.aws_status,
        "last_attempt": datetime.datetime(2026, 7, 3, 14, 41, tzinfo=datetime.timezone.utc),
        "last_success": None,
        "error_count": 3,
        "last_error": "403 authKey=TOPSECRET rejected",
        "last_error_time": datetime.datetime(
            2026, 7, 3, 14, 41, tzinfo=datetime.timezone.utc
        ),
    }
    coordinator.last_update_success = True
    coordinator.last_exception = None
    return coordinator


def test_aws_diagnostics_exposes_station_status_and_snapshot() -> None:
    from custom_components.kma.diagnostics import _aws_diagnostics

    result = _aws_diagnostics(_aws_coordinator(), "zone-1")

    assert result["subentry_id"] == "zone-1"
    assert result["station_id"] == 108
    assert result["observation_fresh"] is False
    assert result["error_count"] == 3
    assert result["observation"]["tm"] == "202607031431"
    assert result["observation"]["temperature"] == 23.1
    assert result["observation"]["rain_day"] == 14.0
    assert result["last_attempt"] is not None
    assert result["last_success"] is None
    assert result["last_error"] is not None
    assert result["coordinator"]["last_update_success"] is True


def test_aws_diagnostics_redacts_auth_key() -> None:
    from custom_components.kma.diagnostics import _aws_diagnostics

    result = _aws_diagnostics(_aws_coordinator(), "zone-1")

    assert "TOPSECRET" not in result["status"]
    assert "TOPSECRET" not in result["last_error"]
    assert "authKey=***" in result["status"]


def test_aws_diagnostics_without_snapshot() -> None:
    from custom_components.kma.diagnostics import _aws_diagnostics

    coordinator = _aws_coordinator()
    coordinator.aws_observation = None
    coordinator.data = {"error_count": 0, "last_error": None, "last_success": None}

    result = _aws_diagnostics(coordinator, "zone-1")

    assert result["observation"] is None
    assert result["last_error"] is None
