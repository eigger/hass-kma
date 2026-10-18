"""Test KMA weather platform."""

from __future__ import annotations

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
)
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kma.weather import (
    get_ha_condition,
)


async def test_weather_entity_state(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test weather entity is added and has correct state and attributes."""
    state = hass.states.get("weather.home")
    assert state is not None
    assert state.state in (ATTR_CONDITION_SUNNY, ATTR_CONDITION_CLEAR_NIGHT)
    assert state.attributes["temperature"] == 22.5  # From ultra ncst
    assert state.attributes["humidity"] == 60.0
    assert state.attributes["wind_speed"] == 9.0  # 2.5 m/s in km/h
    assert state.attributes["wind_bearing"] == 180.0


async def test_get_ha_condition() -> None:
    """Test mapping of KMA sky and pty to Home Assistant weather conditions."""
    # pty takes precedence over sky
    assert get_ha_condition("1", "1", is_night=False) == ATTR_CONDITION_RAINY
    assert get_ha_condition("1", "2", is_night=False) == ATTR_CONDITION_SNOWY_RAINY
    assert get_ha_condition("1", "3", is_night=False) == ATTR_CONDITION_SNOWY
    assert get_ha_condition("1", "4", is_night=False) == ATTR_CONDITION_POURING
    assert get_ha_condition("1", "5", is_night=False) == ATTR_CONDITION_RAINY
    assert get_ha_condition("1", "6", is_night=False) == ATTR_CONDITION_SNOWY_RAINY
    assert get_ha_condition("1", "7", is_night=False) == ATTR_CONDITION_SNOWY

    # When pty is 0 or None, sky is used
    assert get_ha_condition("1", "0", is_night=False) == ATTR_CONDITION_SUNNY
    assert get_ha_condition("1", "0", is_night=True) == ATTR_CONDITION_CLEAR_NIGHT
    assert get_ha_condition("3", "0", is_night=False) == ATTR_CONDITION_PARTLYCLOUDY
    assert get_ha_condition("4", "0", is_night=False) == ATTR_CONDITION_CLOUDY
    assert get_ha_condition(None, None, is_night=False) == ATTR_CONDITION_CLOUDY


async def test_weather_forecast_methods(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test daily and hourly forecast generation on entity."""
    entity = hass.data[WEATHER_DOMAIN].get_entity("weather.home")
    assert entity is not None

    daily = await entity.async_forecast_daily()
    assert isinstance(daily, list)
    assert len(daily) > 0
    assert "datetime" in daily[0]
    assert "native_temperature" in daily[0]
    assert "condition" in daily[0]
    assert daily[0]["native_temperature"] == 22.0
    assert daily[0]["condition"] == ATTR_CONDITION_SUNNY

    hourly = await entity.async_forecast_hourly()
    assert isinstance(hourly, list)
    assert len(hourly) > 0
    assert "datetime" in hourly[0]
    assert "native_temperature" in hourly[0]
    assert "condition" in hourly[0]
    assert hourly[0]["native_temperature"] == 22.0
    assert hourly[0]["condition"] in (ATTR_CONDITION_SUNNY, ATTR_CONDITION_CLEAR_NIGHT)
