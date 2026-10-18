"""Test KMA button platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kma.const import DOMAIN


async def test_refresh_button(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test manual refresh button press triggers coordinator refresh."""
    button_state = hass.states.get("button.home_manual_refresh")
    assert button_state is not None

    coordinator = hass.data[DOMAIN][loaded_entry.entry_id]["coordinators"][
        "sub_zone_home"
    ]
    with patch.object(
        coordinator, "async_request_refresh", new=AsyncMock()
    ) as mock_refresh:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.home_manual_refresh"},
            blocking=True,
        )
        mock_refresh.assert_called_once()
