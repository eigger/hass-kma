"""Test KMA sensor platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_zone_sensors(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test zone sensor entities are registered and have valid states."""
    ent_reg = er.async_get(hass)

    # Check representative zone sensors
    temp_state = hass.states.get("sensor.home_temperature")
    assert temp_state is not None
    assert float(temp_state.state) == 22.5

    reh_state = hass.states.get("sensor.home_humidity")
    assert reh_state is not None
    assert float(reh_state.state) == 60.0

    pm10_state = hass.states.get("sensor.home_pm10_fine_dust")
    assert pm10_state is not None
    assert float(pm10_state.state) == 25.0

    pm10_grade = hass.states.get("sensor.home_pm10_grade")
    assert pm10_grade is not None
    assert pm10_grade.state == "good"

    uv_state = hass.states.get("sensor.home_uv_index")
    assert uv_state is not None
    assert float(uv_state.state) == 5.0

    uv_grade = hass.states.get("sensor.home_uv_index_grade")
    assert uv_grade is not None
    assert uv_grade.state == "moderate"

    air_state = hass.states.get("sensor.home_atmospheric_stagnation_index")
    assert air_state is not None
    assert float(air_state.state) == 50.0

    air_grade = hass.states.get("sensor.home_atmospheric_stagnation_grade")
    assert air_grade is not None
    assert air_grade.state == "moderate"

    # Verify unique ID in registry
    entry = ent_reg.async_get("sensor.home_temperature")
    assert entry is not None
    assert entry.unique_id == "sub_zone_home_temperature"


async def test_aws_station_sensors(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test AWS station sensor entities."""
    ent_reg = er.async_get(hass)

    # AWS Seoul station 108: entity_id is slugified from "AWS 108 <Name>"
    temp_state = hass.states.get("sensor.aws_108_temperature")
    assert temp_state is not None
    assert float(temp_state.state) == 23.1

    humidity_state = hass.states.get("sensor.aws_108_humidity")
    assert humidity_state is not None
    assert float(humidity_state.state) == 71.0

    dew_state = hass.states.get("sensor.aws_108_dew_point")
    assert dew_state is not None
    assert float(dew_state.state) == 17.7

    rain_15m = hass.states.get("sensor.aws_108_rain_15_min")
    assert rain_15m is not None
    assert float(rain_15m.state) == 0.5

    rain_today = hass.states.get("sensor.aws_108_rain_today")
    assert rain_today is not None
    assert float(rain_today.state) == 14.0

    pressure = hass.states.get("sensor.aws_108_station_pressure")
    assert pressure is not None
    assert float(pressure.state) == 1013.4

    # Verify unique ID follows parent_entry_id_aws_{station}_{key} format
    entry = ent_reg.async_get("sensor.aws_108_temperature")
    assert entry is not None
    assert entry.unique_id == f"{loaded_entry.entry_id}_aws_108_temperature"


async def test_hub_error_count_sensors(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test hub error count diagnostic sensors."""
    hub_sensor = hass.states.get(
        "sensor.gisangceong_apihub_village_forecast_api_error_count"
    )
    assert hub_sensor is not None
    assert int(hub_sensor.state) == 0
