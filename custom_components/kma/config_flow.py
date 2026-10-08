"""Config flow for KMA integration.

부모 엔트리는 API 키만 보유하고, 각 Zone은 서브엔트리(서브 디바이스)로 등록한다.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KmaApiClient, KmaApiError, KmaAuthError
from .aws_stations import AWS_STATION_CATALOG
from .const import (
    CONF_AWS_STATION_ID,
    DOMAIN,
    SUBENTRY_TYPE_AWS_STATION,
    SUBENTRY_TYPE_ZONE,
)
from .helpers import (
    aws_station_title,
    get_nearest_land_zone,
    get_nearest_marine_zone,
    latlon_to_grid,
    parse_aws_station_id,
)

_LOGGER = logging.getLogger(__name__)

CONF_AUTH_KEY = "auth_key"
CONF_ZONE_ID = "zone_id"

# 인증키 발급(회원가입/마이페이지) 페이지
APIHUB_URL = "https://apihub.kma.go.kr"


def _station_label(station: int, name: str, region: str) -> str:
    """지점 라벨 = 이름 (지역, 지점번호). 지점번호가 항상 붙어 동명이인도 구분된다."""
    return f"{name} ({region}, {station})"


def aws_station_options() -> list[tuple[str, str]]:
    """SelectSelector 옵션 목록 (value=str(지점번호), label=이름·지역·번호)."""
    return [
        (str(station), _station_label(station, name, region))
        for station, (name, region) in sorted(AWS_STATION_CATALOG.items())
    ]


def _aws_station_selector() -> selector.SelectSelector:
    """`aws_station_id` 선택용 HA 직렬화 가능 SelectSelector.

    번들된 공개 카탈로그(`aws_stations.AWS_STATION_CATALOG`)의 지점번호를 안정
    값(`value=str(station)`)으로, 이름·지역·번호를 라벨로 노출한다. 검색어
    입력이 가능한 DROPDOWN 모드는 `custom_value=True`일 때 제공되므로 임의
    텍스트도 스키마를 통과하지만, 서버에서 기존대로 정식 지점번호 정규화
    (parse_aws_station_id)와 카탈로그 포함 여부로 검증해 목록 밖 값은 거부한다.
    저장 데이터 형식은 바뀌지 않는다(숫자 지점번호 단일 값).
    """
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                selector.SelectOptionDict(value=value, label=label)
                for value, label in aws_station_options()
            ],
            mode=selector.SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )


def _aws_station_subentries(entry: ConfigEntry):
    return [
        sub
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_TYPE_AWS_STATION
    ]


def _station_in_use(entry: ConfigEntry, station: int) -> bool:
    """같은 부모 엔트리에 이미 등록된 지점번호인지(정규화 후) 확인한다."""
    for sub in _aws_station_subentries(entry):
        try:
            existing = parse_aws_station_id(sub.data.get(CONF_AWS_STATION_ID))
        except ValueError:
            continue
        if existing == station:
            return True
    return False


def _get_zone_options(
    hass: HomeAssistant, *, exclude_zone_ids: set[str] | None = None
) -> dict[str, str]:
    """등록 가능한 zone 엔티티 목록을 반환. 이미 추가된 zone은 제외."""
    exclude = exclude_zone_ids or set()
    options: dict[str, str] = {}
    for state in hass.states.async_all("zone"):
        if state.entity_id in exclude:
            continue
        options[state.entity_id] = f"{state.name} ({state.entity_id})"

    # zone이 하나도 없으면 home zone 예비 옵션 제공
    if not options and "zone.home" not in exclude:
        options["zone.home"] = "Home (zone.home)"
    return options


class KmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """KMA 통합 설정 흐름 (부모: API 키)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """API 키만 입력받는다."""
        errors: dict[str, str] = {}

        if user_input is not None:
            auth_key = user_input[CONF_AUTH_KEY]

            # 동일 키 중복 등록 방지
            await self.async_set_unique_id(auth_key)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = KmaApiClient(session, auth_key)
            try:
                if not await client.async_validate_auth():
                    errors["base"] = "invalid_auth"
            except KmaAuthError:
                errors["base"] = "invalid_auth"
            except KmaApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("API 키 검증 중 오류 발생")
                errors["base"] = "unknown"

            if not errors:
                return self.async_create_entry(
                    title="기상청 APIhub",
                    data={CONF_AUTH_KEY: auth_key},
                )

        schema = vol.Schema({vol.Required(CONF_AUTH_KEY): str})
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={"apihub_url": APIHUB_URL},
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """이 통합이 지원하는 서브엔트리 유형(Zone + AWS 관측소)."""
        return {
            SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler,
            SUBENTRY_TYPE_AWS_STATION: AwsStationSubentryFlowHandler,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> KmaOptionsFlowHandler:
        """옵션 흐름(갱신 주기)."""
        return KmaOptionsFlowHandler()


class ZoneSubentryFlowHandler(ConfigSubentryFlow):
    """Zone 서브엔트리 추가/재구성 흐름."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Zone 추가."""
        return await self._async_zone_step(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Zone 재구성."""
        return await self._async_zone_step(user_input, reconfigure=True)

    async def _async_zone_step(
        self, user_input: dict[str, Any] | None, reconfigure: bool = False
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_entry()

        current_sub_id: str | None = None
        if reconfigure:
            current_sub_id = self._get_reconfigure_subentry().subentry_id

        # 이미 추가된 zone은 후보에서 제외 (재구성 중인 자기 자신은 유지)
        used_zone_ids = {
            sub.data.get(CONF_ZONE_ID)
            for sub_id, sub in entry.subentries.items()
            if sub_id != current_sub_id
        }
        zone_options = _get_zone_options(self.hass, exclude_zone_ids=used_zone_ids)

        if user_input is not None:
            zone_id = user_input[CONF_ZONE_ID]
            zone_state = self.hass.states.get(zone_id)
            if zone_state is None:
                latitude = self.hass.config.latitude
                longitude = self.hass.config.longitude
                title = "Home"
            else:
                latitude = zone_state.attributes.get("latitude")
                longitude = zone_state.attributes.get("longitude")
                title = zone_state.name or zone_id

            if latitude is None or longitude is None:
                errors["base"] = "invalid_zone_coords"
            else:
                nx, ny = latlon_to_grid(latitude, longitude)
                data: dict[str, Any] = {
                    CONF_ZONE_ID: zone_id,
                    "zone_name": title,
                    "latitude": latitude,
                    "longitude": longitude,
                    "nx": nx,
                    "ny": ny,
                    "land_reg": get_nearest_land_zone(latitude, longitude),
                    "marine_reg": get_nearest_marine_zone(latitude, longitude),
                }
                if reconfigure:
                    return self.async_update_and_abort(
                        entry,
                        self._get_reconfigure_subentry(),
                        title=title,
                        data=data,
                        unique_id=zone_id,
                    )
                return self.async_create_entry(
                    title=title, data=data, unique_id=zone_id
                )

        if not zone_options:
            return self.async_abort(reason="no_zones_available")

        # 재구성 시에는 기존 서브엔트리의 zone을 기본값으로 유지한다.
        default_zone: str | None = None
        if reconfigure:
            current_zone = self._get_reconfigure_subentry().data.get(CONF_ZONE_ID)
            if current_zone in zone_options:
                default_zone = current_zone
        if default_zone is None:
            default_zone = (
                "zone.home" if "zone.home" in zone_options else next(iter(zone_options))
            )
        schema = vol.Schema(
            {vol.Required(CONF_ZONE_ID, default=default_zone): vol.In(zone_options)}
        )
        return self.async_show_form(
            step_id="reconfigure" if reconfigure else "user",
            data_schema=schema,
            errors=errors,
        )


class AwsStationSubentryFlowHandler(ConfigSubentryFlow):
    """AWS 관측소 서브엔트리 추가 흐름.

    지점번호는 서브엔트리 고유ID이자 안정 식별자라 생성 후 바꿀 수 없다. 그래서
    재구성 스텝을 두지 않는다 — HA는 `async_step_reconfigure`가 없으면 재구성
    버튼을 노출하지 않으므로, 잘못된 재구성 동작이 생기지 않는다.
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                station = parse_aws_station_id(user_input.get(CONF_AWS_STATION_ID))
            except ValueError:
                station = None
                errors["base"] = "invalid_aws_station"
            if not errors and station is None:
                # 지점번호는 필수 — 빈 값은 비활성화가 아니라 오류다.
                errors["base"] = "invalid_aws_station"
            if not errors:
                entry = self._get_entry()
                if station not in AWS_STATION_CATALOG:
                    # 카탈로그에 없는 지점번호 — 변조/오래된 값 방어.
                    errors["base"] = "invalid_aws_station"
                elif _station_in_use(entry, station):
                    errors["base"] = "already_configured"
                else:
                    return self.async_create_entry(
                        title=aws_station_title(station),
                        data={CONF_AWS_STATION_ID: station},
                        unique_id=str(station),
                    )

        schema = vol.Schema(
            {vol.Required(CONF_AWS_STATION_ID): _aws_station_selector()}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class KmaOptionsFlowHandler(config_entries.OptionsFlow):
    """KMA 옵션 관리 흐름 (갱신 주기). config_entry는 베이스에서 자동 제공."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        scan_interval = self.config_entry.options.get("scan_interval", 10)
        options_schema = vol.Schema(
            {
                vol.Required(
                    "scan_interval", default=scan_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=180)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=options_schema)
