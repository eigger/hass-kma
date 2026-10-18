"""Tests for KMA coordinators."""

from __future__ import annotations

import datetime

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kma.api import KmaApiError
from custom_components.kma.const import DOMAIN

from .conftest import make_aws_observation

_KST = datetime.timezone(datetime.timedelta(hours=9))


async def test_zone_coordinator_staleness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kma_api,
) -> None:
    """Test zone coordinator falls back to previous data and marks stale on API error."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinators = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinators"]
    coord = coordinators["sub_zone_home"]

    # Initial state should be fresh
    assert coord.data is not None
    assert coord.data["village"] is not None
    assert coord.refresh_meta["village_stale"] is False

    current = coord.get_current()
    assert current is not None
    assert current.tmp == 22.5

    # Simulate village forecast error on next refresh
    mock_kma_api.async_get_village_forecast.side_effect = KmaApiError("KMA 500 error")
    mock_kma_api.async_get_ultra_ncst.side_effect = KmaApiError("KMA 500 error")

    await coord.async_refresh()
    await hass.async_block_till_done()

    # Previous data should be retained, but marked stale
    assert coord.data["village"] is not None
    assert coord.refresh_meta["village_stale"] is True


async def test_aws_coordinator_freshness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kma_api,
) -> None:
    """Test AWS coordinator freshness calculation."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    aws_coordinators = hass.data[DOMAIN][mock_config_entry.entry_id]["aws_coordinators"]
    coord = aws_coordinators["sub_aws_108"]

    assert coord.aws_observation is not None
    assert coord.aws_status == "ok"

    # With observation observed_at = now, freshness should be True
    assert coord.aws_observation_fresh is True

    # When observation is older than 15 minutes, freshness becomes False
    old_time = datetime.datetime.now(_KST) - datetime.timedelta(minutes=20)
    coord.data["observation"] = make_aws_observation(
        observed_at=old_time,
        tm=old_time.strftime("%Y%m%d%H%M"),
    )
    assert coord.aws_observation_fresh is False


async def test_image_and_hub_coordinators(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kma_api,
) -> None:
    """Test image and hub coordinators."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
    image_coord = entry_data["image_coordinator"]
    hub_coord = entry_data["hub_coordinator"]

    assert image_coord.last_update_success is True
    assert hub_coord.last_update_success is True

    assert "radar" in image_coord.data
    assert "earthquake" in hub_coord.data
