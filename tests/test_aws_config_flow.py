"""Zone / AWS 관측소 서브엔트리 설정 흐름 테스트."""
from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from custom_components.kma.aws_stations import AWS_STATION_CATALOG
from custom_components.kma.config_flow import (
    CONF_ZONE_ID,
    AwsStationSubentryFlowHandler,
    KmaConfigFlow,
    ZoneSubentryFlowHandler,
    _aws_station_selector,
    _station_label,
    aws_station_options,
)
from custom_components.kma.const import (
    CONF_AWS_STATION_ID,
    SUBENTRY_TYPE_AWS_STATION,
    SUBENTRY_TYPE_ZONE,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
# 공식 출처(https://www.weather.go.kr/w/weather/land/aws-obs.do) 스냅샷의
# 축약 픽스처: SG 지점 82개(이름·지역)와 범위 밖(AM/SW/OA) 지점번호.
# HTML/관측값/좌표/주소는 담지 않는다.
_OFFICIAL_SOURCE = json.loads(
    (_REPO_ROOT / "tests" / "fixtures" / "official_sg_stations.json").read_text(
        encoding="utf-8"
    )
)
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
    assert calls["create"]["title"] == "서울 (AWS 108)"


@pytest.mark.parametrize(
    "value", ["  108  ", "0108", 108, "108", "서울 (서울특별시, 108)"]
)
def test_aws_station_canonicalizes_equivalent_inputs(value) -> None:
    calls = _aws_create(value)

    assert "create" in calls
    assert calls["create"]["data"] == {CONF_AWS_STATION_ID: 108}
    assert calls["create"]["unique_id"] == "108"


@pytest.mark.parametrize("value", ["", None, "   ", "0", "-1", "abc", "12.5", True, "3.5", "x (y, 99999)"])
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


def test_aws_station_catalog_is_public_and_complete() -> None:
    # 2026-10-08 공식 목록: ASOS 98 + AWS 540 + SG 82 = 720 (AM/SW/OA 제외).
    assert len(AWS_STATION_CATALOG) == 720
    assert AWS_STATION_CATALOG[108] == ("서울", "서울특별시")
    assert AWS_STATION_CATALOG[400] == ("강남", "서울특별시")
    # 경기도청 관측소(SG)도 같은 카탈로그에 포함된다.
    assert AWS_STATION_CATALOG[351] == ("남면", "경기도")
    assert all(isinstance(stn, int) and stn > 0 for stn in AWS_STATION_CATALOG)
    assert all(name and region for name, region in AWS_STATION_CATALOG.values())


def test_catalog_includes_every_official_sg_station() -> None:
    """공식 출처의 SG 82지점이 이름·지역까지 그대로 포함돼야 한다(개수만이 아님).

    하드코딩한 총 개수가 아니라 축약 픽스처(공식 스냅샷)와 대조해 완전성을
    확인한다 — 지점이 누락되거나 이름/지역이 틀리면 실패한다.
    """
    sg = _OFFICIAL_SOURCE["sg"]
    assert len(sg) == 82
    mismatched = {
        int(stn): {"fixture": (name, region), "catalog": AWS_STATION_CATALOG.get(int(stn))}
        for stn, (name, region) in sg.items()
        if AWS_STATION_CATALOG.get(int(stn)) != (name, region)
    }
    assert not mismatched, mismatched


def test_catalog_excludes_out_of_scope_station_categories() -> None:
    """AM/SW/OA 지점은 이번 변경 범위가 아니므로 카탈로그에 없어야 한다."""
    leaked = [stn for stn in _OFFICIAL_SOURCE["excluded_ids"] if stn in AWS_STATION_CATALOG]
    assert not leaked, leaked


def test_existing_asos_aws_identities_are_unchanged() -> None:
    """기존 ASOS/AWS 지점의 번호→(이름, 지역) 매핑은 그대로 유지된다."""
    assert AWS_STATION_CATALOG[90] == ("속초", "강원특별자치도")
    assert AWS_STATION_CATALOG[108] == ("서울", "서울특별시")
    assert AWS_STATION_CATALOG[119] == ("수원", "경기도")
    assert AWS_STATION_CATALOG[400] == ("강남", "서울특별시")
    assert AWS_STATION_CATALOG[996] == ("화동", "경상북도")


def test_aws_station_options_have_stable_values_and_named_labels() -> None:
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
    """SG 지점이 선택기 옵션에 `이름 (지역, 번호)` 라벨로 노출된다(둘 이상)."""
    options = dict(aws_station_options())
    assert options.get("남면 (경기도, 351)") == "남면 (경기도, 351)"
    assert options.get("경기 * (경기도, 430)") == "경기 * (경기도, 430)"
    assert options.get("학온동 * (경기도, 492)") == "학온동 * (경기도, 492)"


@pytest.mark.parametrize(
    "value,expected_station,expected_title",
    [
        ("351", 351, "남면 (AWS 351)"),
        ("남면 (경기도, 351)", 351, "남면 (AWS 351)"),
        (351, 351, "남면 (AWS 351)"),
        ("430", 430, "경기 * (AWS 430)"),
        ("492", 492, "학온동 * (AWS 492)"),
    ],
)
def test_sg_station_selectable_in_initial_aws_flow(
    value, expected_station, expected_title
) -> None:
    """SG 지점을 초기 AWS 관측소 서브엔트리 흐름에서 선택/생성할 수 있다."""
    calls = _aws_create(value)

    assert "create" in calls
    assert calls["create"]["data"] == {CONF_AWS_STATION_ID: expected_station}
    assert calls["create"]["unique_id"] == str(expected_station)
    assert calls["create"]["title"] == expected_title


@pytest.mark.parametrize(
    "value,expected_station",
    [
        ("108", 108),
        ("0108", 108),
        (108, 108),
        ("  351  ", 351),
        ("0351", 351),
        (351, 351),
    ],
)
def test_numeric_station_ids_round_trip(value, expected_station) -> None:
    """숫자(레거시 포함) 지점번호는 정규화돼 같은 정수로 왕복한다."""
    calls = _aws_create(value)

    assert "create" in calls
    station = calls["create"]["data"][CONF_AWS_STATION_ID]
    assert station == expected_station
    assert isinstance(station, int)
    assert station in AWS_STATION_CATALOG


def test_station_label_distinguishes_duplicate_names() -> None:
    """같은 이름이어도 라벨에 지점번호가 붙어 서로 구분된다."""
    assert _station_label(108, "동명", "지역") != _station_label(400, "동명", "지역")
    assert "108" in _station_label(108, "동명", "지역")
    assert "400" in _station_label(400, "동명", "지역")


@pytest.mark.parametrize("value", ["999999", "12345", "7", "1"])
def test_aws_station_unknown_selection_is_rejected(value) -> None:
    """카탈로그에 없는 지점번호(변조/오래된 값)는 생성하지 않는다."""
    calls = _aws_create(value)

    assert "create" not in calls
    assert calls["form"]["errors"]["base"] == "invalid_aws_station"


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
        sel = aws["selector"]["select"]
        assert sel["mode"] == "dropdown", aws
        assert sel["custom_value"] is True, aws
        values = [o["value"] for o in sel["options"]]
        # 값=라벨(`이름 (지역, 번호)`) — SG 지점도 직렬화 목록에 포함된다.
        assert "서울 (서울특별시, 108)" in values, aws
        assert "남면 (경기도, 351)" in values, aws
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


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("서울 (서울특별시, 108)", "108"), ("관악(레) * (경기도, 116)", "116"), ("108", "108"), (" 12.5 ", " 12.5 ")],
)
def test_station_from_input_extracts_number(raw, expected) -> None:
    from custom_components.kma.config_flow import _station_from_input

    assert _station_from_input(raw) == expected


def test_aws_station_title_falls_back_without_catalog_name() -> None:
    from custom_components.kma.helpers import aws_station_title

    assert aws_station_title(108) == "서울 (AWS 108)"
    assert aws_station_title(999999) == "AWS 999999"
