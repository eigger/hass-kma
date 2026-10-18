"""Test KMA config flow and subentry flows."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kma.api import KmaApiError, KmaAuthError
from custom_components.kma.config_flow import CONF_AUTH_KEY, CONF_ZONE_ID
from custom_components.kma.const import (
    CONF_AWS_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_AWS_STATION,
    SUBENTRY_TYPE_ZONE,
)


async def test_user_flow_success(hass: HomeAssistant, mock_kma_api) -> None:
    """Test successful user step creating the parent entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUTH_KEY: "my_valid_auth_key"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "기상청 APIhub"
    assert result2["data"] == {CONF_AUTH_KEY: "my_valid_auth_key"}


async def test_user_flow_invalid_auth(hass: HomeAssistant, mock_kma_api) -> None:
    """Test user flow with invalid authentication."""
    mock_kma_api.async_validate_auth.side_effect = KmaAuthError("invalid")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUTH_KEY: "wrong_key"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_kma_api) -> None:
    """Test user flow with connection error."""
    mock_kma_api.async_validate_auth.side_effect = KmaApiError("connection error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUTH_KEY: "some_key"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate configuration aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUTH_KEY: "test_auth_key"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_zone_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a zone subentry."""
    hass.states.async_set(
        "zone.office",
        "zoning",
        {"latitude": 37.5000, "longitude": 127.0000, "friendly_name": "Office"},
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ZONE_ID: "zone.office"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Office"
    assert result2["data"]["nx"] is not None
    assert result2["data"]["ny"] is not None
    assert result2["data"]["land_reg"] is not None


async def test_zone_subentry_no_zones_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test abort when all zones are already configured and none left."""
    # mock_config_entry already has zone.home. No other zones exist in hass.states.
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_zones_available"


async def test_zone_subentry_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguring an existing zone subentry."""
    hass.states.async_set(
        "zone.work",
        "zoning",
        {"latitude": 37.4979, "longitude": 127.0276, "friendly_name": "Work"},
    )

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_ZONE),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": "sub_zone_home",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_ZONE_ID: "zone.work"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_aws_station_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an AWS station subentry."""
    # Station 119 is Suwon (수원), valid in catalog and not in mock_config_entry (which has 108).
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_AWS_STATION),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_AWS_STATION_ID: "119"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_AWS_STATION_ID] == 119


async def test_aws_station_subentry_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an AWS station that is already configured."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_AWS_STATION),
        context={"source": config_entries.SOURCE_USER},
    )
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_AWS_STATION_ID: "108"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "already_configured"}


async def test_aws_station_subentry_invalid_station(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an invalid AWS station not in catalog."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_AWS_STATION),
        context={"source": config_entries.SOURCE_USER},
    )
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_AWS_STATION_ID: "99999"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_aws_station"}


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow for scan_interval."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"scan_interval": 20},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"scan_interval": 20}
