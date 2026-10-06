"""AWS 센서 엔티티/디스크립션 단위 테스트."""
from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.kma.api import AwsObservation
from custom_components.kma.const import DOMAIN
from custom_components.kma.sensor import (
    AWS_SENSOR_DESCRIPTIONS,
    AWS_VALUE_ATTRS,
    KmaAwsSensor,
    async_setup_entry,
)

_KST = datetime.timezone(datetime.timedelta(hours=9))
OBSERVED_AT = datetime.datetime(2026, 7, 3, 14, 31, tzinfo=_KST)

EXPECTED_KEYS = [
    "aws_observation_time",
    "aws_temperature",
    "aws_humidity",
    "aws_dew_point",
    "aws_wind_direction_1m",
    "aws_wind_speed_1m",
    "aws_gust_direction",
    "aws_gust_speed",
    "aws_wind_direction_10m",
    "aws_wind_speed_10m",
    "aws_rain_15m",
    "aws_rain_60m",
    "aws_rain_12h",
    "aws_rain_today",
    "aws_pressure",
    "aws_sea_level_pressure",
]


def _obs(**overrides) -> AwsObservation:
    values = dict(
        stn="108",
        tm="202607031431",
        observed_at=OBSERVED_AT,
        wind_dir_1m=225.0,
        wind_speed_1m=1.8,
        gust_dir=180.0,
        gust_speed=6.2,
        wind_dir_10m=190.0,
        wind_speed_10m=2.4,
        temperature=23.1,
        rain_flag=0,
        rain_15m=0.5,
        rain_60m=2.0,
        rain_12h=8.5,
        rain_day=14.0,
        humidity=71.0,
        pressure=1013.4,
        sea_level_pressure=1015.8,
        dew_point=17.7,
    )
    values.update(overrides)
    return AwsObservation(**values)


def _coordinator(
    obs: AwsObservation | None = None, *, fresh: bool = True, status: str = "ok"
):
    coordinator = MagicMock()
    coordinator.aws_observation = obs
    coordinator.aws_observation_fresh = fresh
    coordinator.aws_status = status
    coordinator.aws_station_id = 108
    coordinator.last_update_success = True
    coordinator.data = {"error_count": 2}
    return coordinator


def _sensor(description, coordinator=None, subentry_id: str = "sub-1") -> KmaAwsSensor:
    subentry = SimpleNamespace(subentry_id=subentry_id, data={"zone_name": "Home"})
    device = {(DOMAIN, f"{subentry_id}_aws")}
    return KmaAwsSensor(
        coordinator or _coordinator(_obs()),
        subentry,
        description,
        {"identifiers": device},
    )


def _by_key(key: str):
    for desc in AWS_SENSOR_DESCRIPTIONS:
        if desc.key == key:
            return desc
    raise AssertionError(f"description not found: {key}")


def test_aws_descriptions_cover_the_contracted_sensor_set() -> None:
    assert len(AWS_SENSOR_DESCRIPTIONS) == 16
    assert [desc.key for desc in AWS_SENSOR_DESCRIPTIONS] == EXPECTED_KEYS
    assert all(desc.key.startswith("aws_") for desc in AWS_SENSOR_DESCRIPTIONS)
    assert len({desc.key for desc in AWS_SENSOR_DESCRIPTIONS}) == 16
    assert all(desc.translation_key == desc.key for desc in AWS_SENSOR_DESCRIPTIONS)


def test_aws_units_match_the_contract() -> None:
    unit = {
        "aws_temperature": "°C",
        "aws_dew_point": "°C",
        "aws_humidity": "%",
        "aws_wind_direction_1m": "°",
        "aws_gust_direction": "°",
        "aws_wind_direction_10m": "°",
        "aws_wind_speed_1m": "m/s",
        "aws_gust_speed": "m/s",
        "aws_wind_speed_10m": "m/s",
        "aws_rain_15m": "mm",
        "aws_rain_60m": "mm",
        "aws_rain_12h": "mm",
        "aws_rain_today": "mm",
        "aws_pressure": "hPa",
        "aws_sea_level_pressure": "hPa",
    }
    for key, expected in unit.items():
        assert _by_key(key).native_unit_of_measurement == expected, key

    # 관측 시각은 timestamp device class (단위 없음)
    stamp = _by_key("aws_observation_time")
    assert stamp.device_class == "timestamp"
    assert stamp.native_unit_of_measurement is None


def test_rolling_rain_windows_are_not_total_increasing() -> None:
    for key in ("aws_rain_15m", "aws_rain_60m", "aws_rain_12h", "aws_rain_today"):
        desc = _by_key(key)
        assert desc.state_class == "measurement", key
        assert desc.state_class != "total_increasing", key
        assert desc.device_class == "precipitation", key


def test_wind_direction_uses_measurement_angle_state_class() -> None:
    for key in ("aws_wind_direction_1m", "aws_gust_direction", "aws_wind_direction_10m"):
        desc = _by_key(key)
        assert desc.device_class == "wind_direction", key
        assert desc.state_class == "measurement_angle", key
        assert desc.native_unit_of_measurement == "°", key


def test_all_numeric_sensors_are_measurement_except_directions() -> None:
    direction_keys = {
        "aws_wind_direction_1m",
        "aws_gust_direction",
        "aws_wind_direction_10m",
    }
    for key in AWS_VALUE_ATTRS:
        if key in direction_keys:
            continue
        assert _by_key(key).state_class == "measurement", key


def test_unique_id_and_device_are_isolated_from_existing_sensors() -> None:
    desc = _by_key("aws_temperature")
    sensor = _sensor(desc, subentry_id="sub-9")

    assert sensor._attr_unique_id == "sub-9_aws_temperature"
    assert sensor.entity_description.key == desc.key
    # AWS 전용 디바이스 — 기존 Zone 디바이스 식별자와 섞이지 않는다.
    assert sensor._attr_device_info["identifiers"] == {(DOMAIN, "sub-9_aws")}


@pytest.mark.parametrize(
    "key,expected",
    [
        ("aws_temperature", 23.1),
        ("aws_humidity", 71.0),
        ("aws_dew_point", 17.7),
        ("aws_wind_direction_1m", 225.0),
        ("aws_wind_speed_1m", 1.8),
        ("aws_gust_direction", 180.0),
        ("aws_gust_speed", 6.2),
        ("aws_wind_direction_10m", 190.0),
        ("aws_wind_speed_10m", 2.4),
        ("aws_rain_15m", 0.5),
        ("aws_rain_60m", 2.0),
        ("aws_rain_12h", 8.5),
        ("aws_rain_today", 14.0),
        ("aws_pressure", 1013.4),
        ("aws_sea_level_pressure", 1015.8),
    ],
)
def test_native_value_maps_to_observation_fields(key, expected) -> None:
    assert _sensor(_by_key(key)).native_value == expected


def test_observation_time_returns_aware_datetime() -> None:
    value = _sensor(_by_key("aws_observation_time")).native_value
    assert value == OBSERVED_AT
    assert value.tzinfo is not None


def test_native_value_is_none_without_fresh_observation() -> None:
    desc = _by_key("aws_temperature")

    assert _sensor(desc, _coordinator(None)).native_value is None
    assert _sensor(desc, _coordinator(_obs(), fresh=False)).native_value is None


def test_missing_field_yields_none() -> None:
    sensor = _sensor(_by_key("aws_temperature"), _coordinator(_obs(temperature=None)))
    assert sensor.native_value is None


def test_availability_follows_freshness() -> None:
    desc = _by_key("aws_temperature")

    assert _sensor(desc, _coordinator(_obs(), fresh=True)).available is True
    assert _sensor(desc, _coordinator(_obs(), fresh=False)).available is False
    assert _sensor(desc, _coordinator(None, fresh=False)).available is False


def test_availability_is_false_when_coordinator_update_fails() -> None:
    coordinator = _coordinator(_obs(), fresh=True)
    coordinator.last_update_success = False
    assert _sensor(_by_key("aws_temperature"), coordinator).available is False


def test_extra_state_attributes_expose_station_and_observation_time() -> None:
    attrs = _sensor(_by_key("aws_temperature"), _coordinator(_obs())).extra_state_attributes

    assert attrs["station_id"] == 108
    assert attrs["observation_time"] == OBSERVED_AT
    assert attrs["status"] == "ok"
    assert attrs["error_count"] == 2


def test_extra_state_attributes_without_snapshot() -> None:
    attrs = _sensor(_by_key("aws_temperature"), _coordinator(None)).extra_state_attributes

    assert attrs["station_id"] == 108
    assert attrs["observation_time"] is None


def _setup(aws_coordinators, coordinators=None):
    entry_id = "entry-1"
    subentry = SimpleNamespace(subentry_id="sub-1", title="Home", data={"zone_name": "Home"})
    store = {
        "coordinators": coordinators or {},
        "aws_coordinators": aws_coordinators,
        "hub_device_id": "hub-1",
        "hub_coordinator": None,
        "image_coordinator": None,
    }
    entry = SimpleNamespace(
        entry_id=entry_id, subentries={"sub-1": subentry}
    )
    hass = MagicMock()
    hass.data = {DOMAIN: {entry_id: store}}
    added = []

    def _add(entities, **kwargs):
        added.extend(entities)

    asyncio.run(async_setup_entry(hass, entry, _add))
    return added


def test_setup_adds_sixteen_aws_sensors_when_opted_in() -> None:
    aws = {"sub-1": _coordinator(_obs())}
    entities = _setup(aws)

    assert len(entities) == 16
    assert all(isinstance(entity, KmaAwsSensor) for entity in entities)
    assert {entity._attr_unique_id for entity in entities} == {
        f"sub-1_{key}" for key in EXPECTED_KEYS
    }


def test_setup_creates_no_aws_entities_without_station_id() -> None:
    assert _setup({}) == []


def test_setup_passes_config_subentry_id_for_aws_entities() -> None:
    entry_id = "entry-1"
    subentry = SimpleNamespace(subentry_id="sub-1", title="Home", data={"zone_name": "Home"})
    store = {
        "coordinators": {},
        "aws_coordinators": {"sub-1": _coordinator(_obs())},
        "hub_device_id": "hub-1",
        "hub_coordinator": None,
        "image_coordinator": None,
    }
    entry = SimpleNamespace(entry_id=entry_id, subentries={"sub-1": subentry})
    hass = MagicMock()
    hass.data = {DOMAIN: {entry_id: store}}
    calls = []

    def _add(entities, **kwargs):
        calls.append((list(entities), kwargs))

    asyncio.run(async_setup_entry(hass, entry, _add))

    assert len(calls) == 1
    assert calls[0][1].get("config_subentry_id") == "sub-1"
