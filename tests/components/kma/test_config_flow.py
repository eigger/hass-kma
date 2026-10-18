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


def test_aws_station_catalog_is_public_and_complete() -> None:
    from custom_components.kma.aws_stations import AWS_STATION_CATALOG

    # 2026-10-08 공식 목록: ASOS 98 + AWS 540 + SG 82 = 720 (AM/SW/OA 제외).
    assert len(AWS_STATION_CATALOG) == 720
    assert AWS_STATION_CATALOG[108] == ("서울", "서울특별시")
    assert AWS_STATION_CATALOG[400] == ("강남", "서울특별시")
    assert AWS_STATION_CATALOG[351] == ("남면", "경기도")
    assert all(isinstance(stn, int) and stn > 0 for stn in AWS_STATION_CATALOG)
    assert all(name and region for name, region in AWS_STATION_CATALOG.values())


def test_catalog_includes_every_official_sg_station() -> None:
    """공식 출처의 SG 82지점이 이름·지역까지 그대로 포함돼야 한다."""
    import json
    from pathlib import Path

    from custom_components.kma.aws_stations import AWS_STATION_CATALOG

    repo_root = Path(__file__).resolve().parents[3]
    official = json.loads(
        (repo_root / "tests" / "fixtures" / "official_sg_stations.json").read_text(
            encoding="utf-8"
        )
    )
    sg = official["sg"]
    assert len(sg) == 82
    mismatched = {
        int(stn): {
            "fixture": (name, region),
            "catalog": AWS_STATION_CATALOG.get(int(stn)),
        }
        for stn, (name, region) in sg.items()
        if AWS_STATION_CATALOG.get(int(stn)) != (name, region)
    }
    assert not mismatched, mismatched


def test_catalog_excludes_out_of_scope_station_categories() -> None:
    """AM/SW/OA 지점은 카탈로그에 없어야 한다."""
    import json
    from pathlib import Path

    from custom_components.kma.aws_stations import AWS_STATION_CATALOG

    repo_root = Path(__file__).resolve().parents[3]
    official = json.loads(
        (repo_root / "tests" / "fixtures" / "official_sg_stations.json").read_text(
            encoding="utf-8"
        )
    )
    leaked = [stn for stn in official["excluded_ids"] if stn in AWS_STATION_CATALOG]
    assert not leaked, leaked


def test_existing_asos_aws_identities_are_unchanged() -> None:
    """기존 ASOS/AWS 지점 매핑 유지 검증."""
    from custom_components.kma.aws_stations import AWS_STATION_CATALOG

    assert AWS_STATION_CATALOG[90] == ("속초", "강원특별자치도")
    assert AWS_STATION_CATALOG[108] == ("서울", "서울특별시")
    assert AWS_STATION_CATALOG[119] == ("수원", "경기도")
    assert AWS_STATION_CATALOG[400] == ("강남", "서울특별시")
    assert AWS_STATION_CATALOG[996] == ("화동", "경상북도")


def test_aws_station_options_have_stable_values_and_named_labels() -> None:
    from custom_components.kma.config_flow import aws_station_options

    options = aws_station_options()
    values = [value for value, _ in options]
    labels = [label for _, label in options]

    assert len(options) == 720
    assert values == labels  # 선택 후에도 이름이 보이도록 값=라벨
    assert len(set(values)) == len(values)  # 값은 고유
    assert len(set(labels)) == len(labels)  # 라벨도 고유(번호 포함)
    assert ("서울 (서울특별시, 108)", "서울 (서울특별시, 108)") in options
    assert ("강남 (서울특별시, 400)", "강남 (서울특별시, 400)") in options


def test_sg_stations_are_selectable_in_the_selector_options() -> None:
    """SG 지점이 선택기 옵션에 `이름 (지역, 번호)` 라벨로 노출된다."""
    from custom_components.kma.config_flow import aws_station_options

    options = dict(aws_station_options())
    assert options.get("남면 (경기도, 351)") == "남면 (경기도, 351)"
    assert options.get("경기 * (경기도, 430)") == "경기 * (경기도, 430)"
    assert options.get("학온동 * (경기도, 492)") == "학온동 * (경기도, 492)"


def test_station_label_distinguishes_duplicate_names() -> None:
    from custom_components.kma.config_flow import _station_label

    assert _station_label(108, "동명", "지역") != _station_label(400, "동명", "지역")
    assert "108" in _station_label(108, "동명", "지역")
    assert "400" in _station_label(400, "동명", "지역")
