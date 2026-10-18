"""Test KMA image platform."""

from __future__ import annotations

from homeassistant.components.image import DOMAIN as IMAGE_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_image_entities(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test image platform entities for radar and satellite."""
    ent_reg = er.async_get(hass)

    radar_state = hass.states.get("image.home_radar_composite_image")
    assert radar_state is not None
    assert radar_state.state != "unavailable"

    satellite_state = hass.states.get("image.home_satellite_image")
    assert satellite_state is not None
    assert satellite_state.state != "unavailable"

    # Verify unique ID
    radar_entry = ent_reg.async_get("image.home_radar_composite_image")
    assert radar_entry is not None
    assert radar_entry.unique_id == "sub_zone_home_radar_image"

    sat_entry = ent_reg.async_get("image.home_satellite_image")
    assert sat_entry is not None
    assert sat_entry.unique_id == "sub_zone_home_satellite_image"


async def test_async_image_bytes(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test async_image returns cached image binary data."""
    entity = hass.data[IMAGE_DOMAIN].get_entity("image.home_radar_composite_image")
    assert entity is not None

    image_bytes = await entity.async_image()
    assert image_bytes == b"\x89PNG\r\n\x1a\nfake_png"
