"""AWS 센서 엔티티/디스크립션 단위 테스트."""
from __future__ import annotations

import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.kma.api import AwsObservation
from custom_components.kma.const import DOMAIN
from conftest import make_aws_observation as _obs
from custom_components.kma.sensor import (
    AWS_SENSOR_DESCRIPTIONS,
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


def _coordinator(
    obs: AwsObservation | None = None,
    *,
    fresh: bool = True,
    status: str = "ok",
    station: int = 108,
    entry_id: str = "entry-1",
):
    coordinator = MagicMock()
    coordinator.aws_observation = obs
    coordinator.aws_observation_fresh = fresh
    coordinator.aws_status = status
    coordinator.aws_station_id = station
    coordinator.aws_unique_key = f"{entry_id}_aws_{station}"
    coordinator.last_update_success = True
    coordinator.data = {"error_count": 2}
    return coordinator


def _sensor(description, coordinator=None) -> KmaAwsSensor:
    coordinator = coordinator or _coordinator(_obs())
    device = {(DOMAIN, coordinator.aws_unique_key)}
    return KmaAwsSensor(coordinator, description, {"identifiers": device})


def _real_aws_coordinator(*, entry_id: str, station: int, subentry_id: str):
    """실제 `KmaAwsCoordinator`를 만든다(부모 엔트리/지점/서브엔트리 ID 지정)."""
    from custom_components.kma.const import CONF_AWS_STATION_ID
    from custom_components.kma.coordinator import KmaAwsCoordinator

    entry = SimpleNamespace(entry_id=entry_id)
    subentry = SimpleNamespace(
        subentry_id=subentry_id, data={CONF_AWS_STATION_ID: station}
    )
    return KmaAwsCoordinator(MagicMock(), MagicMock(), entry, subentry)


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
    # 방향(measurement_angle)과 관측 시각(timestamp)을 뺀 나머지는 measurement.
    numeric_keys = [
        "aws_temperature",
        "aws_humidity",
        "aws_dew_point",
        "aws_wind_speed_1m",
        "aws_gust_speed",
        "aws_wind_speed_10m",
        "aws_rain_15m",
        "aws_rain_60m",
        "aws_rain_12h",
        "aws_rain_today",
        "aws_pressure",
        "aws_sea_level_pressure",
    ]
    for key in numeric_keys:
        assert _by_key(key).state_class == "measurement", key


def test_unique_id_and_device_are_isolated_from_existing_sensors() -> None:
    desc = _by_key("aws_temperature")
    sensor = _sensor(desc, _coordinator(_obs(), entry_id="entry-9"))

    # 고유ID/디바이스 식별자 = 부모 엔트리 ID + 지점번호 기반(서브엔트리 ID 무관).
    assert sensor._attr_unique_id == "entry-9_aws_108_temperature"
    assert sensor.entity_description.key == desc.key
    # AWS 전용 디바이스 — 기존 Zone 디바이스 식별자와 섞이지 않는다.
    assert sensor._attr_device_info["identifiers"] == {(DOMAIN, "entry-9_aws_108")}


def test_unique_id_is_stable_across_subentry_recreation() -> None:
    """서브엔트리 ID가 달라도 같은 부모 엔트리+지점이면 고유 키/ID가 동일하다.

    실제 `KmaAwsCoordinator`를 같은 부모 엔트리/지점, 다른 서브엔트리 ID로 만들어
    정체성이 일시적인 subentry_id가 아니라 부모 엔트리 ID + 지점번호에서 나오는지
    확인한다(서브엔트리 ID에 의존하면 이 테스트가 실패한다).
    """
    desc = _by_key("aws_temperature")
    first = _real_aws_coordinator(entry_id="entry-1", station=108, subentry_id="sub-old")
    second = _real_aws_coordinator(entry_id="entry-1", station=108, subentry_id="sub-new")

    assert first.subentry.subentry_id != second.subentry.subentry_id
    assert first.aws_unique_key == second.aws_unique_key == "entry-1_aws_108"

    sensor1 = _sensor(desc, first)
    sensor2 = _sensor(desc, second)
    assert sensor1._attr_unique_id == sensor2._attr_unique_id == "entry-1_aws_108_temperature"
    assert (
        sensor1._attr_device_info["identifiers"]
        == sensor2._attr_device_info["identifiers"]
    )


def test_unique_id_differs_for_different_parent_entries() -> None:
    desc = _by_key("aws_temperature")
    a = _sensor(desc, _coordinator(_obs(), entry_id="entry-a", station=108))
    b = _sensor(desc, _coordinator(_obs(), entry_id="entry-b", station=108))

    assert a._attr_unique_id != b._attr_unique_id
    assert (
        a._attr_device_info["identifiers"] != b._attr_device_info["identifiers"]
    )


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
        f"entry-1_aws_108_{key.removeprefix('aws_')}" for key in EXPECTED_KEYS
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


def test_aws_object_id_names_cover_all_sensors() -> None:
    from custom_components.kma.sensor import AWS_OBJECT_ID_NAMES, AWS_SENSOR_DESCRIPTIONS

    assert set(AWS_OBJECT_ID_NAMES) == {d.key for d in AWS_SENSOR_DESCRIPTIONS}
