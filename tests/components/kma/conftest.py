"""Fixtures for the KMA component tests."""

# <!-- hass-standards:domain-fixtures:start -->
# Use pytest_homeassistant_custom_component.common.MockConfigEntry for
# mock_config_entry when the integration uses config entries.
# Define mock_client only when an external communication client is present.
# Mock external communication boundaries, never Home Assistant core modules.
# Keep integration-specific fixtures below this managed block.
# <!-- hass-standards:domain-fixtures:end -->

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kma.api import (
    AirStagnationForecast,
    AwsObservation,
    EarthquakeNotice,
    ImageBinary,
    LandForecast,
    Pm10HourlyStats,
    Pm10Observation,
    StationBulletin,
    UVIndexForecast,
    VillageForecast,
)
from custom_components.kma.config_flow import CONF_ZONE_ID
from custom_components.kma.const import (
    CONF_AWS_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_AWS_STATION,
    SUBENTRY_TYPE_ZONE,
)

_KST = datetime.timezone(datetime.timedelta(hours=9))

CALL_LATER_CALLS: list[dict[str, Any]] = []


def make_aws_observation(**overrides) -> AwsObservation:
    """Generate a valid AwsObservation instance."""
    values = dict(
        stn="108",
        tm="202607031431",
        observed_at=datetime.datetime(2026, 7, 3, 14, 31, tzinfo=_KST),
        wind_dir_1m=225.0,
        wind_speed_1m=1.8,
        gust_dir=180.0,
        gust_speed=6.2,
        wind_dir_10m=190.0,
        wind_speed_10m=2.4,
        temperature=23.1,
        rain_flag=0,
        rain_15m=0.5,
        rain_60m=2.0,
        rain_12h=8.5,
        rain_day=14.0,
        humidity=71.0,
        pressure=1013.4,
        sea_level_pressure=1015.8,
        dew_point=17.7,
    )
    values.update(overrides)
    return AwsObservation(**values)


def make_village_forecasts() -> list[VillageForecast]:
    """Generate a sample set of village forecasts."""
    now = datetime.datetime.now(_KST)
    fcst_date = now.strftime("%Y%m%d")
    fcst_time = now.strftime("%H00")
    return [
        VillageForecast(
            fcst_date=fcst_date,
            fcst_time=fcst_time,
            tmp=22.0,
            uuu=0.0,
            vvv=2.5,
            vec=180.0,
            wsd=2.5,
            sky="1",
            pty="0",
            pop=20.0,
            pcp="0",
            sno="0",
            reh=60.0,
        )
    ]


@pytest.fixture
def sample_aws_observation() -> AwsObservation:
    """Fixture for sample AWS observation."""
    return make_aws_observation()


@pytest.fixture
def sample_village_forecasts() -> list[VillageForecast]:
    """Fixture for sample village forecasts."""
    return make_village_forecasts()


@pytest.fixture
def sample_land_forecasts() -> list[LandForecast]:
    """Fixture for sample land forecasts."""
    return [
        LandForecast(
            reg_id="11B10101",
            tm_fc="202610180600",
            tm_ef="202610190000",
            mod="A01",
            ne=1,
            stn="108",
            wind_dir1="N",
            wind_dir2="NE",
            ta=22.0,
            pop=20.0,
            sky="DB01",
            prep="0",
            wf="맑음",
        )
    ]


@pytest.fixture
def sample_ultra_ncst():
    """Fixture for ultra short-term current status."""
    from custom_components.kma.api import UltraNcst

    return UltraNcst(
        base_date="20261018",
        base_time="1200",
        t1h=22.5,
        rn1=0.0,
        reh=60.0,
        pty="0",
        wsd=2.5,
        vec=180.0,
        uuu=0.0,
        vvv=2.5,
    )


@pytest.fixture
def sample_ultra_forecasts():
    """Fixture for ultra short-term forecasts."""
    from custom_components.kma.api import UltraFcst

    now = datetime.datetime.now(_KST)
    return [
        UltraFcst(
            fcst_date=now.strftime("%Y%m%d"),
            fcst_time=(now + datetime.timedelta(hours=1)).strftime("%H00"),
            t1h=22.0,
            sky="1",
            pty="0",
            reh=60.0,
            wsd=2.5,
            vec=180.0,
            rn1=0.0,
        )
    ]


@pytest.fixture
def mock_kma_api(
    sample_aws_observation,
    sample_village_forecasts,
    sample_land_forecasts,
    sample_ultra_ncst,
    sample_ultra_forecasts,
):
    """Mock external KmaApiClient methods."""
    with (
        patch("custom_components.kma.KmaApiClient") as mock_client_cls,
        patch("custom_components.kma.config_flow.KmaApiClient") as mock_flow_client_cls,
    ):
        client = mock_client_cls.return_value
        mock_flow_client_cls.return_value = client

        client.async_validate_auth = AsyncMock(return_value=True)
        client.async_get_village_forecast = AsyncMock(
            return_value=sample_village_forecasts
        )
        client.async_get_ultra_ncst = AsyncMock(return_value=sample_ultra_ncst)
        client.async_get_ultra_fcst = AsyncMock(return_value=sample_ultra_forecasts)
        client.async_get_land_forecast = AsyncMock(return_value=sample_land_forecasts)
        client.async_get_marine_forecast = AsyncMock(return_value=[])
        client.async_get_pm10_now = AsyncMock(
            return_value=Pm10Observation(
                stn="108",
                tm="202610181200",
                pm10=25.0,
                raw="202610181200, 108, 25,000000,,=",
            )
        )
        client.async_get_uv_index = AsyncMock(
            return_value=UVIndexForecast(
                area_no="1100000000",
                date="202610181200",
                current=5.0,
                hourly={"h0": 5.0},
            )
        )
        client.async_get_air_stagnation_index = AsyncMock(
            return_value=AirStagnationForecast(
                area_no="1100000000",
                date="202610181200",
                current=50.0,
                hourly={"h0": 50.0},
            )
        )
        client.async_get_oak_pollen_risk = AsyncMock(return_value=1.0)
        client.async_get_pine_pollen_risk = AsyncMock(return_value=1.0)
        client.async_get_weed_pollen_risk = AsyncMock(return_value=1.0)
        client.async_get_radar_precipitation = AsyncMock(return_value=0.0)
        client.async_get_sfc_observation = AsyncMock(
            return_value={"ta": 22.0, "hm": 60.0}
        )
        client.async_get_heat_wave_risk = AsyncMock(return_value=0)
        client.async_get_cold_wave_risk = AsyncMock(return_value=0)
        client.async_get_hazard_info = AsyncMock(
            return_value=StationBulletin(
                stn="109",
                issued_at="202610181200",
                title="기상정보 요약",
                body="<중점 사항>\n주의사항 본문",
            )
        )
        client.async_get_weather_commentary = AsyncMock(
            return_value=StationBulletin(
                stn="109",
                issued_at="202610181200",
                title="날씨해설 요약",
                body="<중점 사항>\n날씨전망 본문",
            )
        )
        client.async_get_snow_depth = AsyncMock(return_value=0.0)
        client.async_get_pm10_hourly_stats = AsyncMock(
            return_value=Pm10HourlyStats(
                stn="108",
                tm="2026.10.18.12:00",
                avg=25.0,
                min=15.0,
                max=35.0,
            )
        )
        client.async_get_warning_now = AsyncMock(
            return_value=[
                {
                    "REG_UP_KO": "서울",
                    "REG_KO": "서울",
                    "WAR": "호우주의보",
                    "TM_EF": "202610181200",
                }
            ]
        )
        client.async_get_aws_observation = AsyncMock(
            return_value=sample_aws_observation
        )
        sample_img = ImageBinary(
            data=b"\x89PNG\r\n\x1a\nfake_png",
            content_type="image/png",
            filename="fake.png",
        )
        client.async_get_radar_image = AsyncMock(return_value=sample_img)
        client.async_get_satellite_image = AsyncMock(return_value=sample_img)
        client.async_get_precipitation_forecast_image = AsyncMock(
            return_value=sample_img
        )
        client.async_get_dust_satellite_image = AsyncMock(return_value=sample_img)
        client.async_get_earthquake_recent = AsyncMock(
            return_value=EarthquakeNotice(
                msg_code="국내지진정보",
                domestic=True,
                location="경북 상주시 북북서쪽 11km",
                issued_at="202610181205",
                occurred_at="202610181200",
                magnitude=2.1,
                depth=12.0,
                lat=36.5,
                lon=128.0,
                reference="최대진도 Ⅰ",
            )
        )
        client.async_get_typhoon_now = AsyncMock(return_value=None)

        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock KMA config entry with zone and AWS station subentries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="기상청 APIhub",
        data={"auth_key": "test_auth_key"},
        unique_id="test_auth_key",
        subentries_data=[
            {
                "subentry_id": "sub_zone_home",
                "subentry_type": SUBENTRY_TYPE_ZONE,
                "title": "Home",
                "unique_id": "zone.home",
                "data": {
                    CONF_ZONE_ID: "zone.home",
                    "zone_name": "Home",
                    "latitude": 37.5665,
                    "longitude": 126.9780,
                    "nx": 60,
                    "ny": 127,
                    "land_reg": "11B10101",
                    "marine_reg": "12A20100",
                },
            },
            {
                "subentry_id": "sub_aws_108",
                "subentry_type": SUBENTRY_TYPE_AWS_STATION,
                "title": "서울 (108)",
                "unique_id": "108",
                "data": {
                    CONF_AWS_STATION_ID: 108,
                },
            },
        ],
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_kma_api: AsyncMock,
) -> MockConfigEntry:
    """Set up the mock entry and wait for completion."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
