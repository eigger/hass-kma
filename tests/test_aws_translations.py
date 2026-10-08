"""AWS 관련 번역 키 정합성 테스트 (strings.json / en.json / ko.json)."""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "kma"
_FILES = {
    "strings": _ROOT / "strings.json",
    "en": _ROOT / "translations" / "en.json",
    "ko": _ROOT / "translations" / "ko.json",
}
_AWS_SENSOR_KEYS = [
    "aws_observation_time",
    "aws_temperature",
    "aws_humidity",
    "aws_dew_point",
    "aws_wind_direction_1m",
    "aws_wind_speed_1m",
    "aws_gust_direction",
    "aws_gust_speed",
    "aws_wind_direction_10m",
    "aws_wind_speed_10m",
    "aws_rain_15m",
    "aws_rain_60m",
    "aws_rain_12h",
    "aws_rain_today",
    "aws_pressure",
    "aws_sea_level_pressure",
]


def _load(name: str) -> dict:
    return json.loads(_FILES[name].read_text(encoding="utf-8"))


def test_every_strings_key_exists_in_both_translation_files() -> None:
    """strings.json 의 키는 en/ko 번역 파일에 반드시 존재해야 한다(hassfest 요구).

    참고: 번역 파일에는 strings.json 에 없는 `entity.button.refresh` 가 이미 남아
    있었는데(기존 동작), 이 테스트는 "번역 누락" 방향만 검사한다.
    """
    reference = _load("strings")

    def _keys(node, prefix: str = "") -> set[str]:
        found: set[str] = set()
        if isinstance(node, dict):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else key
                found.add(path)
                found |= _keys(value, path)
        return found

    reference_keys = _keys(reference)
    for name in ("en", "ko"):
        missing = reference_keys - _keys(_load(name))
        assert not missing, f"{name}: {sorted(missing)}"


def test_all_aws_sensor_names_exist_in_every_translation() -> None:
    for name in ("strings", "en", "ko"):
        sensor = _load(name)["entity"]["sensor"]
        for key in _AWS_SENSOR_KEYS:
            assert key in sensor, f"{name}: {key}"
            assert sensor[key]["name"], f"{name}: {key} empty"


def test_aws_sensor_names_are_translated_differently_in_korean() -> None:
    english = _load("en")["entity"]["sensor"]
    korean = _load("ko")["entity"]["sensor"]
    for key in _AWS_SENSOR_KEYS:
        assert english[key]["name"] != korean[key]["name"], key
        assert any("가" <= ch <= "힣" for ch in korean[key]["name"]), key


def test_aws_sensor_names_do_not_repeat_the_device_aws_prefix() -> None:
    """디바이스 이름이 이미 `AWS <지점>`이므로 표시 이름에서 AWS를 반복하지 않는다."""
    for name in ("strings", "en", "ko"):
        sensor = _load(name)["entity"]["sensor"]
        for key in _AWS_SENSOR_KEYS:
            assert "aws" not in sensor[key]["name"].lower(), (name, key)


def test_zone_forms_do_not_ask_for_aws_station() -> None:
    """AWS 지점번호는 Zone 폼이 아니라 독립 aws_station 서브엔트리에서 받는다."""
    for name in ("strings", "en", "ko"):
        zone = _load(name)["config_subentries"]["zone"]
        for step in ("user", "reconfigure"):
            assert "aws_station_id" not in zone["step"][step]["data"], f"{name}/{step}"
            assert "AWS" not in zone["step"][step]["description"], f"{name}/{step}"


def test_aws_station_subentry_strings_exist() -> None:
    for name in ("strings", "en", "ko"):
        aws = _load(name)["config_subentries"]["aws_station"]
        assert aws["step"]["user"]["data"]["aws_station_id"], name
        assert aws["step"]["user"]["description"], name
        assert aws["error"]["invalid_aws_station"], name
        assert aws["error"]["already_configured"], name
        assert aws["abort"]["already_configured"], name
        assert aws["initiate_flow"]["user"], name
        assert aws["entry_type"], name
