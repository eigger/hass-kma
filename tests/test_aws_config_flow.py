"""Zone / AWS 관측소 서브엔트리 설정 흐름 테스트."""
from __future__ import annotations

import asyncio
import inspect
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from custom_components.kma.config_flow import (
    CONF_ZONE_ID,
    AwsStationSubentryFlowHandler,
    KmaConfigFlow,
    ZoneSubentryFlowHandler,
    _aws_station_selector,
)
from custom_components.kma.const import (
    CONF_AWS_STATION_ID,
    SUBENTRY_TYPE_AWS_STATION,
    SUBENTRY_TYPE_ZONE,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
# 실제 Home Assistant가 설치된 환경에서만 직렬화 회귀 테스트를 돌린다(CI는 미설치).
_REAL_HA_AVAILABLE = (
    subprocess.run(
        [sys.executable, "-c", "import homeassistant.helpers.selector"],
        capture_output=True,
    ).returncode
    == 0
)

ZONE_STATE = SimpleNamespace(
    entity_id="zone.home",
    name="Home",
    attributes={"latitude": 37.5665, "longitude": 126.9780},
)
# 홈이 아닌 zone — 재구성 기본값이 홈으로 덮어써지지 않는지 확인용
ZONE_WORK_STATE = SimpleNamespace(
    entity_id="zone.work",
    name="Work",
    attributes={"latitude": 37.5000, "longitude": 127.0000},
)
# 좌표가 없는 zone — 위경도 검증 경로가 그대로 살아 있는지 확인용
ZONE_NO_COORDS_STATE = SimpleNamespace(
    entity_id="zone.nocoords", name="NoCoords", attributes={}
)


class _States:
    def __init__(self, states) -> None:
        self._states = {state.entity_id: state for state in states}

    def get(self, entity_id):
        return self._states.get(entity_id)

    def async_all(self, domain=None):
        return list(self._states.values())


def _handler(subentry=None, *, states=(ZONE_STATE,), other_subentries=()):
    # 재구성 대상 서브엔트리도 실제처럼 entry.subentries에 넣어 used_zone_ids 계산이
    # 자기 자신을 제외하는 경로를 그대로 태운다.
    subentries = {sub.subentry_id: sub for sub in other_subentries}
    if subentry is not None:
        subentries[subentry.subentry_id] = subentry
    handler = ZoneSubentryFlowHandler()
    handler.hass = SimpleNamespace(
        states=_States(states),
        config=SimpleNamespace(latitude=37.5665, longitude=126.9780),
    )
    handler._get_entry = lambda: SimpleNamespace(subentries=subentries)
    if subentry is not None:
        handler._get_reconfigure_subentry = lambda: subentry

    calls = {}
    handler.async_show_form = lambda **kw: calls.setdefault("form", kw) or ("form", kw)
    handler.async_create_entry = lambda **kw: calls.setdefault("create", kw) or (
        "create",
        kw,
    )
    handler.async_update_and_abort = lambda *a, **kw: calls.setdefault(
        "update", (a, kw)
    ) or ("update", kw)
    handler.async_abort = lambda **kw: calls.setdefault("abort", kw) or ("abort", kw)
    return handler, calls


def _aws_handler(*, existing=()):
    subentries = {sub.subentry_id: sub for sub in existing}
    handler = AwsStationSubentryFlowHandler()
    handler.hass = SimpleNamespace()
    handler._get_entry = lambda: SimpleNamespace(subentries=subentries)

    calls = {}
    handler.async_show_form = lambda **kw: calls.setdefault("form", kw) or ("form", kw)
    handler.async_create_entry = lambda **kw: calls.setdefault("create", kw) or (
        "create",
        kw,
    )
    return handler, calls


def _field(schema, name):
    """폼 스키마에서 지정한 키의 voluptuous 마커를 찾는다."""
    return next(key for key in schema if key.schema == name)


def _zone_field_default(calls):
    zone_key = _field(calls["form"]["data_schema"].schema, CONF_ZONE_ID)
    # voluptuous 0.16 wraps the default in a factory.
    default = zone_key.default
    return default() if callable(default) else default


def _aws_create(value):
    handler, calls = _aws_handler()
    asyncio.run(handler.async_step_user({CONF_AWS_STATION_ID: value}))
    return calls


def _aws_existing(station: int, sub_id: str = "sub-aws"):
    return SimpleNamespace(
        subentry_id=sub_id,
        subentry_type=SUBENTRY_TYPE_AWS_STATION,
        data={CONF_AWS_STATION_ID: station},
    )


# --- Zone 흐름 -------------------------------------------------------------


def test_zone_create_stores_zone_without_any_aws_field() -> None:
    handler, calls = _handler()
    asyncio.run(handler.async_step_user({CONF_ZONE_ID: "zone.home"}))

    assert "create" in calls
    assert calls["create"]["data"][CONF_ZONE_ID] == "zone.home"
    assert CONF_AWS_STATION_ID not in calls["create"]["data"]


def test_zone_form_has_no_aws_field() -> None:
    handler, calls = _handler()
    asyncio.run(handler.async_step_user(None))

    keys = [key.schema for key in calls["form"]["data_schema"].schema]
    assert keys == [CONF_ZONE_ID]
    assert CONF_AWS_STATION_ID not in keys


def test_zone_without_coordinates_keeps_the_original_error() -> None:
    handler, calls = _handler(states=(ZONE_STATE, ZONE_NO_COORDS_STATE))
    asyncio.run(handler.async_step_user({CONF_ZONE_ID: "zone.nocoords"}))

    assert "create" not in calls
    assert calls["form"]["errors"]["base"] == "invalid_zone_coords"


def test_zone_without_coordinates_falls_back_to_home_when_state_missing() -> None:
    handler, calls = _handler(states=())
    asyncio.run(handler.async_step_user({CONF_ZONE_ID: "zone.missing"}))

    assert "create" in calls
    assert calls["create"]["data"]["latitude"] == 37.5665


@pytest.mark.parametrize(
    "current_zone, other_home, expected",
    [
        # 비홈 기존 zone은 기본값으로 유지된다.
        ("zone.work", False, "zone.work"),
        # 다른 서브엔트리가 홈을 차지해도 현재 zone은 후보에서 빠지지 않는다.
        ("zone.work", True, "zone.work"),
        # 기존 zone 엔티티가 사라졌으면 홈으로 폴백한다.
        ("zone.gone", False, "zone.home"),
    ],
)
def test_reconfigure_form_defaults_zone(current_zone, other_home, expected) -> None:
    other = (
        [
            SimpleNamespace(
                subentry_id="sub-other",
                subentry_type=SUBENTRY_TYPE_ZONE,
                data={CONF_ZONE_ID: "zone.home", "zone_name": "Home"},
            )
        ]
        if other_home
        else []
    )
    subentry = SimpleNamespace(
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_ZONE,
        data={CONF_ZONE_ID: current_zone, "zone_name": "Zone"},
    )
    handler, calls = _handler(
        subentry, states=(ZONE_STATE, ZONE_WORK_STATE), other_subentries=other
    )
    asyncio.run(handler.async_step_reconfigure(None))

    assert _zone_field_default(calls) == expected


def test_reconfigure_submitting_preserved_zone_keeps_it() -> None:
    """폼이 고른 기본값(기존 비홈 zone)을 그대로 제출하면 zone이 유지된다."""
    subentry = SimpleNamespace(
        subentry_id="sub-1",
        subentry_type=SUBENTRY_TYPE_ZONE,
        data={CONF_ZONE_ID: "zone.work", "zone_name": "Work"},
    )
    handler, calls = _handler(subentry, states=(ZONE_STATE, ZONE_WORK_STATE))
    asyncio.run(handler.async_step_reconfigure(None))
    selected_zone = _zone_field_default(calls)
    assert selected_zone == "zone.work"

    asyncio.run(
        handler.async_step_reconfigure({CONF_ZONE_ID: selected_zone})
    )

    _, kwargs = calls["update"]
    assert kwargs["data"][CONF_ZONE_ID] == "zone.work"
    assert CONF_AWS_STATION_ID not in kwargs["data"]
    assert kwargs["unique_id"] == "zone.work"


# --- AWS 관측소 흐름 -------------------------------------------------------


def test_aws_station_create_stores_canonical_id_and_stable_unique_id() -> None:
    calls = _aws_create("108")

    assert "create" in calls
    assert calls["create"]["data"] == {CONF_AWS_STATION_ID: 108}
    # 서브엔트리 고유ID = 지점번호(문자열) → 중복 방지/불변성의 근거.
    assert calls["create"]["unique_id"] == "108"
    assert calls["create"]["title"] == "AWS 108"


@pytest.mark.parametrize("value", ["  108  ", "0108", 108, "108"])
def test_aws_station_canonicalizes_equivalent_inputs(value) -> None:
    calls = _aws_create(value)

    assert "create" in calls
    assert calls["create"]["data"] == {CONF_AWS_STATION_ID: 108}
    assert calls["create"]["unique_id"] == "108"


@pytest.mark.parametrize("value", ["", None, "   ", "0", "-1", "abc", "12.5", True, "3.5"])
def test_aws_station_invalid_input_shows_error_and_creates_nothing(value) -> None:
    calls = _aws_create(value)

    assert "create" not in calls
    assert calls["form"]["errors"]["base"] == "invalid_aws_station"
    assert calls["form"]["step_id"] == "user"


def test_aws_station_form_field_is_required_and_not_a_plain_function() -> None:
    handler, calls = _aws_handler()
    asyncio.run(handler.async_step_user(None))

    schema = calls["form"]["data_schema"].schema
    key = _field(schema, CONF_AWS_STATION_ID)
    # Required(빈 값 불가) + 값은 직렬화 가능한 selector(평범한 함수가 아님).
    assert isinstance(key, vol.Required)
    value = next(v for k, v in schema.items() if k.schema == CONF_AWS_STATION_ID)
    assert not inspect.isfunction(value)


def test_aws_station_schema_value_is_not_a_plain_function() -> None:
    """회귀(CI): 스키마 값이 평범한 함수면 실제 HA 폼 직렬화가 HTTP 500으로 실패한다.

    실제 HA 직렬화 서브프로세스 테스트는 CI에서 건너뛰어지므로, 그 형태 자체를
    여기서 잡는다.
    """
    handler, calls = _aws_handler()
    asyncio.run(handler.async_step_user(None))

    value = next(
        v for key, v in calls["form"]["data_schema"].schema.items()
        if key.schema == CONF_AWS_STATION_ID
    )
    assert not inspect.isfunction(value)


def test_aws_station_duplicate_within_parent_is_rejected() -> None:
    handler, calls = _aws_handler(existing=(_aws_existing(108),))
    asyncio.run(handler.async_step_user({CONF_AWS_STATION_ID: "108"}))

    assert "create" not in calls
    assert calls["form"]["errors"]["base"] == "already_configured"


def test_aws_station_duplicate_detection_canonicalizes() -> None:
    handler, calls = _aws_handler(existing=(_aws_existing(108),))
    asyncio.run(handler.async_step_user({CONF_AWS_STATION_ID: "0108"}))

    assert "create" not in calls
    assert calls["form"]["errors"]["base"] == "already_configured"


def test_aws_station_different_number_in_same_parent_is_allowed() -> None:
    handler, calls = _aws_handler(existing=(_aws_existing(108),))
    asyncio.run(handler.async_step_user({CONF_AWS_STATION_ID: "400"}))

    assert "create" in calls
    assert calls["create"]["data"] == {CONF_AWS_STATION_ID: 400}


def test_aws_station_ignores_zone_subentries_for_duplicate_check() -> None:
    """레거시 Zone 서브엔트리의 AWS 필드는 중복 판정에 쓰지 않는다."""
    legacy_zone = SimpleNamespace(
        subentry_id="sub-zone",
        subentry_type=SUBENTRY_TYPE_ZONE,
        data={CONF_ZONE_ID: "zone.home", CONF_AWS_STATION_ID: 108},
    )
    handler, calls = _aws_handler(existing=(legacy_zone,))
    asyncio.run(handler.async_step_user({CONF_AWS_STATION_ID: "108"}))

    assert "create" in calls


def test_aws_station_flow_has_no_reconfigure_step() -> None:
    """지점번호는 불변 — 재구성 스텝이 없어 HA가 재구성 버튼을 노출하지 않는다."""
    assert not hasattr(AwsStationSubentryFlowHandler, "async_step_reconfigure")
    assert not hasattr(AwsStationSubentryFlowHandler, "async_step_user_reconfigure")


def test_parent_reports_both_subentry_types_with_expected_reconfigure_support() -> None:
    entry = SimpleNamespace()
    supported = KmaConfigFlow.async_get_supported_subentry_types(entry)

    assert supported[SUBENTRY_TYPE_ZONE] is ZoneSubentryFlowHandler
    assert supported[SUBENTRY_TYPE_AWS_STATION] is AwsStationSubentryFlowHandler
    assert hasattr(ZoneSubentryFlowHandler, "async_step_reconfigure")
    assert not hasattr(AwsStationSubentryFlowHandler, "async_step_reconfigure")


def test_aws_station_selector_is_serializable_in_isolated_interpreter() -> None:
    assert hasattr(_aws_station_selector(), "serialize")


@pytest.mark.skipif(not _REAL_HA_AVAILABLE, reason="real Home Assistant not installed")
def test_form_schema_serializes_with_real_ha() -> None:
    """HA 2026.9.x 플로우 매니저의 실제 직렬화 경로로 폼 스키마가 통과해야 한다.

    callable 스키마 값이면 `unable to serialize schema` ValueError가 났다. 실제 HA를
    conftest의 모의 없이 쓰기 위해 별도 인터프리터에서 실행한다.
    """
    code = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(_REPO_ROOT)!r})
        import homeassistant  # noqa: F401  (installs probatio as voluptuous)
        import voluptuous as vol
        from probatio import to_field_list
        from homeassistant.helpers import config_validation as cv
        from custom_components.kma.config_flow import _aws_station_selector
        from custom_components.kma.const import CONF_AWS_STATION_ID

        schema = vol.Schema(
            {{vol.Required(CONF_AWS_STATION_ID): _aws_station_selector()}}
        )
        fields = to_field_list(schema, custom_serializer=cv.custom_serializer)
        aws = next(f for f in fields if f.get("name") == "aws_station_id")
        assert aws["selector"]["text"]["type"] == "number", aws
        print("SERIALIZED_OK")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    assert "SERIALIZED_OK" in proc.stdout


def test_parent_setup_form_does_not_ask_for_aws() -> None:
    """부모(API 키) 설정에는 AWS 항목이 없어야 한다 — AWS 권한/정보가 필요 없다."""
    flow = KmaConfigFlow()
    flow.async_show_form = MagicMock(side_effect=lambda **kw: kw)
    result = asyncio.run(flow.async_step_user(None))

    keys = [getattr(key, "schema", key) for key in result["data_schema"].schema]
    assert keys == ["auth_key"]
    assert CONF_AWS_STATION_ID not in keys
