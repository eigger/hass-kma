"""Tests for KMA diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kma.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kma_api,
) -> None:
    """Test config entry diagnostics data structure and redaction."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics_data = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "entry" in diagnostics_data
    assert diagnostics_data["entry"]["entry_id"] == mock_config_entry.entry_id
    assert "zones" in diagnostics_data
    assert "aws" in diagnostics_data
    assert "images" in diagnostics_data
    assert "hub" in diagnostics_data

    # Verify zone diagnostics
    zones = diagnostics_data["zones"]
    assert len(zones) >= 1
    zone_data = next(iter(zones.values()))
    assert "zone_name" in zone_data
    assert "current_data_source" in zone_data
    assert "record_counts" in zone_data

    # Verify AWS diagnostics
    aws = diagnostics_data["aws"]
    assert len(aws) >= 1
    aws_data = next(iter(aws.values()))
    assert "station_id" in aws_data
    assert "status" in aws_data
    assert "observation" in aws_data

    # Verify Images diagnostics
    images = diagnostics_data["images"]
    assert "image_available" in images
    assert "api_status" in images

    # Verify Hub diagnostics
    hub = diagnostics_data["hub"]
    assert "data_available" in hub
    assert "api_status" in hub
