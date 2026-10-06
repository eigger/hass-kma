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
from .const import CONF_AWS_STATION_ID, DOMAIN
from .helpers import (
    get_nearest_land_zone,
    get_nearest_marine_zone,
    latlon_to_grid,
    parse_aws_station_id,
)

_LOGGER = logging.getLogger(__name__)

CONF_AUTH_KEY = "auth_key"
CONF_ZONE_ID = "zone_id"
SUBENTRY_TYPE_ZONE = "zone"

# 인증키 발급(회원가입/마이페이지) 페이지
APIHUB_URL = "https://apihub.kma.go.kr"


def _aws_station_selector() -> selector.TextSelector:
    """`aws_station_id` 입력용 HA 직렬화 가능 selector.

    폼 스키마는 프론트엔드로 JSON 직렬화되므로(HA 2026.9.x), callable 검증기를
    스키마 값으로 쓰면 `unable to serialize schema` ValueError(HTTP 500)가 난다.
    따라서 숫자 입력을 유도하는 텍스트 selector만 두고, 실제 검증은 서버에서
    parse_aws_station_id가 수행한다(빈 값=비활성화, 양의 정수, bool 거부).
    """
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.NUMBER)
    )


def _aws_station_schema_field(current: Any = None) -> vol.Optional:
    """`aws_station_id` 스키마 필드. 재구성 시 기존값을 suggested_value로 노출."""
    if current is None:
        return vol.Optional(CONF_AWS_STATION_ID)
    return vol.Optional(
        CONF_AWS_STATION_ID, description={"suggested_value": str(current)}
    )


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
        """이 통합이 지원하는 서브엔트리 유형(Zone)."""
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler}

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

            # AWS 지점번호는 선택 사항이다 — 양의 정수만 허용, 공백/None은 비활성화.
            # 부모 설정(API 키)에는 영향을 주지 않으므로 미설정 Zone도 그대로 동작한다.
            aws_station_id: int | None = None
            try:
                aws_station_id = parse_aws_station_id(
                    user_input.get(CONF_AWS_STATION_ID)
                )
            except ValueError:
                errors["base"] = "invalid_aws_station"

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
                errors.setdefault("base", "invalid_zone_coords")
            elif not errors:
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
                if aws_station_id is not None:
                    # 비활성화(None)면 키 자체를 쓰지 않는다 — 기존 설정이 지워진다.
                    data[CONF_AWS_STATION_ID] = aws_station_id

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

        # 재구성 시에는 기존 서브엔트리의 zone을 기본값으로 유지한다. 그러지 않으면
        # 선택적 AWS 지점번호만 바꾸려는 사용자가 홈/첫 zone으로 조용히 옮겨진다.
        default_zone: str | None = None
        current_aws_station: Any = None
        if reconfigure:
            subentry = self._get_reconfigure_subentry()
            current_zone = subentry.data.get(CONF_ZONE_ID)
            if current_zone in zone_options:
                default_zone = current_zone
            current_aws_station = subentry.data.get(CONF_AWS_STATION_ID)
        if default_zone is None:
            default_zone = (
                "zone.home" if "zone.home" in zone_options else next(iter(zone_options))
            )
        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE_ID, default=default_zone): vol.In(zone_options),
                _aws_station_schema_field(current_aws_station): (
                    _aws_station_selector()
                ),
            }
        )
        return self.async_show_form(
            step_id="reconfigure" if reconfigure else "user",
            data_schema=schema,
            errors=errors,
        )


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
