"""Test KMA integration setup, unload, reload and subentry handling."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kma.const import (
    CONF_AWS_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_AWS_STATION,
)


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kma_api,
) -> None:
    """Test successful setup of entry and platforms."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert "coordinators" in entry_data
    assert "aws_coordinators" in entry_data
    assert "image_coordinator" in entry_data
    assert "hub_coordinator" in entry_data
    assert "sub_zone_home" in entry_data["coordinators"]
    assert "sub_aws_108" in entry_data["aws_coordinators"]


async def test_async_unload_entry(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test entry unload cleanly unloads platforms and clears hass.data."""
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
    assert loaded_entry.entry_id not in hass.data[DOMAIN]


async def test_reload_on_options_update(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test integration reloads when options change."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(
            loaded_entry,
            options={"scan_interval": 15},
        )
        await hass.async_block_till_done()
        mock_reload.assert_called_once_with(loaded_entry.entry_id)


async def test_setup_skips_invalid_aws_station_subentry(
    hass: HomeAssistant,
    mock_kma_api,
) -> None:
    """Test that invalid AWS station ID does not crash setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="기상청 APIhub",
        data={"auth_key": "test_auth_key"},
        unique_id="test_invalid_station_entry",
        subentries_data=[
            {
                "subentry_id": "sub_aws_invalid",
                "subentry_type": SUBENTRY_TYPE_AWS_STATION,
                "title": "Invalid Station",
                "unique_id": "invalid",
                "data": {
                    CONF_AWS_STATION_ID: "not-a-number",
                },
            },
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    entry_data = hass.data[DOMAIN][entry.entry_id]
    assert len(entry_data["aws_coordinators"]) == 0
