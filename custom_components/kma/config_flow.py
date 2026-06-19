"""Config flow for KMA integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .api import KmaApiClient, KmaAuthError, KmaApiError
from .helpers import latlon_to_grid, get_nearest_land_zone, get_nearest_marine_zone

_LOGGER = logging.getLogger(__name__)


def _get_zone_options(hass: HomeAssistant) -> dict[str, str]:
    """현재 홈어시스턴트에 등록된 zone 엔티티 목록을 가져옵니다."""
    options = {}
    for state in hass.states.async_all("zone"):
        options[state.entity_id] = f"{state.name} ({state.entity_id})"
    
    # 만약 zone이 없다면 기본 home zone 구성용으로 예비 옵션 추가
    if not options:
        options["zone.home"] = "Home (zone.home)"
    return options


class KmaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """KMA 통합 구성요소 설정 흐름."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """사용자 설정 첫 단계."""
        errors: dict[str, str] = {}
        zone_options = _get_zone_options(self.hass)

        if user_input is not None:
            auth_key = user_input["auth_key"]
            zone_id = user_input["zone_id"]

            # 1. API 키 검증
            session = async_get_clientsession(self.hass)
            client = KmaApiClient(session, auth_key)
            try:
                valid = await client.async_validate_auth()
                if not valid:
                    errors["base"] = "invalid_auth"
            except KmaAuthError:
                errors["base"] = "invalid_auth"
            except KmaApiError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("API 키 검증 중 오류 발생: %s", err)
                errors["base"] = "unknown"

            if not errors:
                # 2. 선택된 Zone 정보 획득 및 좌표 변환
                zone_state = self.hass.states.get(zone_id)
                if zone_state is None:
                    # zone.home 등 기본 좌표 조회 시도
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
                    # 기상청 격자 및 육상/해상 예보구역 매핑
                    nx, ny = latlon_to_grid(latitude, longitude)
                    land_reg = get_nearest_land_zone(latitude, longitude)
                    marine_reg = get_nearest_marine_zone(latitude, longitude)

                    # 고유 ID 설정 (동일 구역 중복 설치 방지)
                    await self.async_set_unique_id(f"{land_reg}_{nx}_{ny}")
                    self._abort_if_unique_id_configured()

                    # 데이터 저장 및 생성
                    return self.async_create_entry(
                        title=title,
                        data={
                            "auth_key": auth_key,
                            "zone_id": zone_id,
                            "latitude": latitude,
                            "longitude": longitude,
                            "nx": nx,
                            "ny": ny,
                            "land_reg": land_reg,
                            "marine_reg": marine_reg,
                        },
                    )

        # 폼 제공
        default_zone = "zone.home" if "zone.home" in zone_options else list(zone_options.keys())[0]
        schema = vol.Schema(
            {
                vol.Required("auth_key"): str,
                vol.Required("zone_id", default=default_zone): vol.In(zone_options),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> KmaOptionsFlowHandler:
        """KMA 옵션 흐름 획득."""
        return KmaOptionsFlowHandler(config_entry)


class KmaOptionsFlowHandler(config_entries.OptionsFlow):
    """KMA 통합 구성요소 옵션 관리 흐름."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """옵션 흐름 초기화."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """옵션 설정 단계 (갱신 주기 설정)."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # 현재 저장된 옵션값 가져오기 (기본값은 10분)
        scan_interval = self.config_entry.options.get("scan_interval", 10)

        options_schema = vol.Schema(
            {
                vol.Required(
                    "scan_interval",
                    default=scan_interval,
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=180)),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=options_schema
        )
