"""Test KMA binary sensor platform."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_zone_binary_sensors(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test zone warning and precipitation binary sensors."""
    warning_sensor = hass.states.get("binary_sensor.home_weather_warning")
    assert warning_sensor is not None
    # In mock_kma_api we returned a warning for Seoul, so state is 'on'
    assert warning_sensor.state == "on"
    assert "active_warnings" in warning_sensor.attributes
    assert warning_sensor.attributes["warnings_count"] == 1

    precip_sensor = hass.states.get("binary_sensor.home_precipitation_expected")
    assert precip_sensor is not None
    # pty=0 so precipitation_expected is 'off'
    assert precip_sensor.state == "off"


async def test_hub_api_status_binary_sensors(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test hub API status connectivity binary sensors."""
    village_api = hass.states.get(
        "binary_sensor.gisangceong_apihub_village_forecast_api"
    )
    assert village_api is not None
    assert village_api.state == "on"
    assert village_api.attributes.get("status") == "ok"

    aws_api = hass.states.get("binary_sensor.gisangceong_apihub_aws_observation_api")
    assert aws_api is not None
    assert aws_api.state == "on"
