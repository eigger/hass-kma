"""AWS(관측소 1분 자료) 파서/클라이언트 단위 테스트."""
from __future__ import annotations

import asyncio
import datetime
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.kma.api import (
    AWS_ENDPOINT,
    AWS_REQUEST_WINDOW_MINUTES,
    AwsObservation,
    KmaApiClient,
    KmaApiError,
    _is_aws_timestamp,
    _parse_aws_line,
    _parse_aws_response,
    _to_aws_float,
    _to_wind_dir,
    aws_row_has_measurement,
)

_KST = datetime.timezone(datetime.timedelta(hours=9))


def _row(
    tm: str = "202607031431",
    stn: str = "108",
    wd1: str = "225",
    ws1: str = "1.8",
    wds: str = "180",
    wss: str = "6.2",
    wd10: str = "190",
    ws10: str = "2.4",
    ta: str = "23.1",
    re: str = "0",
    rn15: str = "0.5",
    rn60: str = "2.0",
    rn12: str = "8.5",
    rntd: str = "14.0",
    hm: str = "71",
    pa: str = "1013.4",
    ps: str = "1015.8",
    td: str = "17.7",
) -> str:
    """원시 18컬럼 라인 생성 (YYMMDDHHMI STN WD1 WS1 WDS WSS WD10 WS10 TA RE ...)."""
    return ",".join(
        [
            tm, stn, wd1, ws1, wds, wss, wd10, ws10, ta, re,
            rn15, rn60, rn12, rntd, hm, pa, ps, td,
        ]
    )


def _response(*rows: str, start: bool = True, end: bool = True) -> str:
    lines: list[str] = ["#AWS1Minute"]  # START 이전 주석 라인
    if start:
        lines.append("#START3")
    lines.extend(rows)
    if end:
        lines.append("#3END")
    return "\n".join(lines) + "\n"


def test_parse_aws_response_returns_full_snapshot() -> None:
    obs = _parse_aws_response(_response(_row()), 108)

    assert isinstance(obs, AwsObservation)
    assert obs.stn == "108"
    assert obs.tm == "202607031431"
    assert obs.observed_at == datetime.datetime(
        2026, 7, 3, 14, 31, tzinfo=_KST
    )
    assert obs.temperature == 23.1
    assert obs.humidity == 71.0
    assert obs.dew_point == 17.7
    assert obs.wind_dir_1m == 225.0
    assert obs.wind_speed_1m == 1.8
    assert obs.gust_dir == 180.0
    assert obs.gust_speed == 6.2
    assert obs.wind_dir_10m == 190.0
    assert obs.wind_speed_10m == 2.4
    assert obs.rain_15m == 0.5
    assert obs.rain_60m == 2.0
    assert obs.rain_12h == 8.5
    assert obs.rain_day == 14.0
    assert obs.pressure == 1013.4
    assert obs.sea_level_pressure == 1015.8
    assert obs.rain_flag == 0


def test_parse_aws_response_selects_newest_row_for_requested_station() -> None:
    rows = [
        _row(tm="202607031429"),
        _row(tm="202607031432"),
        _row(tm="202607031431"),
    ]
    obs = _parse_aws_response(_response(*rows), 108)
    assert obs.tm == "202607031432"


def test_parse_aws_response_ignores_other_stations() -> None:
    rows = [
        _row(tm="202607031435", stn="105"),
        _row(tm="202607031430", stn="108"),
    ]
    obs = _parse_aws_response(_response(*rows), 108)
    assert obs.stn == "108"
    assert obs.tm == "202607031430"


def test_parse_aws_response_accepts_int_stn() -> None:
    obs = _parse_aws_response(_response(_row()), 108)
    assert obs.stn == "108"


def test_parse_aws_response_tolerates_trailing_equals_token() -> None:
    obs = _parse_aws_response(_response(_row() + ",="), 108)
    assert obs.temperature == 23.1


def test_parse_aws_response_skips_comment_lines_between_markers() -> None:
    text = "\n".join(["#START3", "#col1,col2", _row(), "#3END"]) + "\n"
    assert _parse_aws_response(text, 108).temperature == 23.1


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n",
        # START 없음(오류 본문/안내문/빈 응답)
        _row() + "\n",
        "# col1,col2\n" + _row() + "\n#1END\n",
        "#3END\n",
        # START 는 있는데 END 없음(잘린 응답) — 관측 0으로 위장하지 않는다
        "#START3\n" + _row() + "\n",
        "#START3\n",
        # 본문이 없는 마커만 있는 응답
        "#START3\n#3END\n",
    ],
)
def test_parse_aws_response_rejects_unterminated_or_markerless_payloads(text: str) -> None:
    with pytest.raises(KmaApiError):
        _parse_aws_response(text, 108)


def test_parse_aws_response_requires_valid_row_for_station() -> None:
    # 18컬럼이 아닌 라인은 구조적으로 무효 → 유효 행이 없으면 예외
    with pytest.raises(KmaApiError):
        _parse_aws_response(_response("202607031431,108,225"), 108)
    # 다른 지점만 있는 경우
    with pytest.raises(KmaApiError):
        _parse_aws_response(_response(_row(stn="105")), 108)


def _missing_row(tm: str = "202607031431", **overrides) -> str:
    """모든 측정 컬럼이 결측 센티널인 행(구조는 유효)."""
    row = _row(tm=tm)
    sentinel_parts = [row.split(",")[0], row.split(",")[1]] + [
        "-99.9"
    ] * (18 - 2)
    for key, value in overrides.items():
        index = {
            "wd1": 2, "ws1": 3, "wds": 4, "wss": 5, "wd10": 6, "ws10": 7,
            "ta": 8, "re": 9, "rn15": 10, "rn60": 11, "rn12": 12,
            "rntd": 13, "hm": 14, "pa": 15, "ps": 16, "td": 17,
        }[key]
        sentinel_parts[index] = value
    return ",".join(sentinel_parts)


def test_parse_aws_response_skips_all_missing_rows() -> None:
    """모든 측정 컬럼이 결측인 행은 실측 자료가 아니므로 건너뛴다."""
    rows = [
        _row(tm="202607031435"),  # 실측 행(더 늦은 시각)
        _missing_row(tm="202607031436"),  # 전부 결측 — 실측 아님
    ]
    obs = _parse_aws_response(_response(*rows), 108)
    assert obs.tm == "202607031435"


def test_parse_aws_response_all_missing_rows_raise() -> None:
    """요청 지점의 행이 전부 결측이면 관측 0 으로 위장하지 않고 예외."""
    with pytest.raises(KmaApiError):
        _parse_aws_response(_response(_missing_row(tm="202607031431")), 108)


def test_parse_aws_response_all_missing_older_row_does_not_hide_newer() -> None:
    """전부 결측 행이 실측 행을 덮지 않는다."""
    rows = [
        _missing_row(tm="202607031436"),
        _row(tm="202607031435"),
    ]
    obs = _parse_aws_response(_response(*rows), 108)
    assert obs.tm == "202607031435"


def test_parse_aws_response_preserves_partial_missingness() -> None:
    """일부 컬럼만 결측인 행은 그대로 유지한다(결측 필드를 채우지 않는다)."""
    row = _row(tm="202607031431", ta="-99.9", pa="-99.9", ps="-99.9", hm="-99.9")
    obs = _parse_aws_response(_response(row), 108)

    assert obs.temperature is None
    assert obs.pressure is None
    assert obs.sea_level_pressure is None
    assert obs.humidity is None
    # 나머지 필드는 그대로 살아 있다.
    assert obs.wind_speed_1m == 1.8
    assert obs.rain_15m == 0.5
    assert obs.dew_point == 17.7


def test_parse_aws_response_preserves_genuine_zero_values() -> None:
    """0 은 진짜 실측값 — 결측으로 취급하지 않는다."""
    row = _row(tm="202607031431", ws1="0.0", ta="0.0", rn15="0.0", hm="0")
    obs = _parse_aws_response(_response(row), 108)

    assert obs.wind_speed_1m == 0.0
    assert obs.temperature == 0.0
    assert obs.rain_15m == 0.0
    assert obs.humidity == 0.0


def test_aws_row_has_measurement_contract() -> None:
    """실측 판정: 16개 측정 컬럼 중 하나라도 값이 있으면 실측 행."""
    all_missing = _parse_aws_line(_missing_row())
    assert all_missing is not None
    assert aws_row_has_measurement(all_missing) is False

    # 0 하나라도 있으면 실측 행이다.
    with_zero = _parse_aws_line(_missing_row(ws1="0.0"))
    assert with_zero is not None
    assert aws_row_has_measurement(with_zero) is True

    # 진짜 값이 하나라도 있으면 실측 행.
    normal = _parse_aws_line(_row())
    assert normal is not None
    assert aws_row_has_measurement(normal) is True


def test_parse_aws_line_skips_unparseable_timestamp() -> None:
    assert _parse_aws_line(_row(tm="not-a-time")) is None
    assert _parse_aws_line("too,few,columns") is None


@pytest.mark.parametrize(
    "tm",
    [
        "20260703143",     # 11자리 — strptime 이 허용하지만 계약은 정확히 12자리
        "2026070314315",  # 13자리
        "20260703143a",   # 비숫자 포함
        "20260703143 ",   # 공백(토큰 단위 거절)
        "２０２６０７０３１４３１",  # 전각 숫자 — isdigit() 은 True 이지만 ASCII 가 아니다
        "٢٠٢٦٠٧٠٣١٤٣١",  # 아라비아-인도 숫자 — 유니코드 숫자
    ],
)
def test_parse_aws_line_rejects_non_12_ascii_digit_timestamps(tm: str) -> None:
    """관측시각은 정확히 12자리 ASCII 숫자여야 한다(strptime 파싱 전 검사)."""
    assert _is_aws_timestamp(tm) is False
    assert _parse_aws_line(_row(tm=tm)) is None


def test_is_aws_timestamp_accepts_exactly_12_ascii_digits() -> None:
    assert _is_aws_timestamp("202607031431") is True
    assert _is_aws_timestamp("20260703143") is False
    assert _is_aws_timestamp("2026070314315") is False
    assert _is_aws_timestamp("20260703143a") is False
    # strptime 의 \d 가 매칭할 수 있는 유니코드 숫자도 여기서 걸러진다.
    assert _is_aws_timestamp("２０２６０７０３１４３１") is False
    assert _is_aws_timestamp("٢٠٢٦٠٧٠٣١٤٣١") is False


def test_parse_aws_line_skips_wrong_column_count() -> None:
    # 19개 토큰(트레일링 '=' 없이 추가 토큰) → 거절
    assert _parse_aws_line(_row() + ",extra") is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("-99.9", None),
        ("-99", None),
        ("-99.0", None),
        ("-9.9", -9.9),
        ("-9.0", -9.0),
        ("0", 0.0),
        ("0.0", 0.0),
        ("23.1", 23.1),
        ("nan", None),
        ("inf", None),
        ("-inf", None),
        ("abc", None),
        ("", None),
    ],
)
def test_to_aws_float_sentinels_and_preservation(raw: str, expected: float | None) -> None:
    assert _to_aws_float(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0", 0.0),       # 북 — 0도는 값으로 보존
        ("360", None),    # 무풍 표기 — 북풍이 아니다
        ("360.0", None),
        ("180", 180.0),
        ("-99.9", None),
    ],
)
def test_to_wind_dir_maps_360_to_none(raw: str, expected: float | None) -> None:
    assert _to_wind_dir(raw) == expected


def test_parse_aws_line_applies_360_only_to_direction_fields() -> None:
    obs = _parse_aws_line(
        _row(wd1="360", wds="360", wd10="360", ws1="0.0", wss="0.0", ws10="0.0")
    )
    assert obs is not None
    assert obs.wind_dir_1m is None
    assert obs.gust_dir is None
    assert obs.wind_dir_10m is None
    # 풍속 0은 정상 값이다
    assert obs.wind_speed_1m == 0.0
    assert obs.gust_speed == 0.0
    assert obs.wind_speed_10m == 0.0


def test_parse_aws_line_does_not_infer_precipitation_from_rain_flag() -> None:
    obs = _parse_aws_line(_row(re="1", rn15="-99.9"))
    assert obs is not None
    assert obs.rain_flag == 1
    # RE 플래그만 있고 강수량은 결측 → 강수량을 0이나 1로 만들지 않는다
    assert obs.rain_15m is None


def test_async_get_aws_observation_builds_window_and_endpoint() -> None:
    client = KmaApiClient(None, "secret-key")
    client._request = AsyncMock(return_value=_response(_row()))  # type: ignore[method-assign]

    now = datetime.datetime(2026, 7, 3, 14, 41, tzinfo=_KST)
    with patch("custom_components.kma.api._now_kst", return_value=now):
        obs = asyncio.run(client.async_get_aws_observation(stn=108))

    assert obs.tm == "202607031431"
    endpoint, params = client._request.call_args.args
    assert endpoint == AWS_ENDPOINT
    assert endpoint.startswith("https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-aws2_min")
    assert params["stn"] == 108
    assert params["disp"] == 1
    assert params["help"] == 0
    assert params["tm2"] == "202607031441"
    assert params["tm1"] == "202607031431"
    # 조회 창은 10분
    tm2 = datetime.datetime.strptime(params["tm2"], "%Y%m%d%H%M")
    tm1 = datetime.datetime.strptime(params["tm1"], "%Y%m%d%H%M")
    assert (tm2 - tm1) == datetime.timedelta(minutes=AWS_REQUEST_WINDOW_MINUTES)
    # authKey 는 로그/상태에 노출되지 않으므로 쿼리로만 넘어간다
    assert "authKey" not in params


def test_async_get_aws_observation_propagates_parse_failure() -> None:
    client = KmaApiClient(None, "secret-key")
    client._request = AsyncMock(return_value="no markers here")  # type: ignore[method-assign]

    with pytest.raises(KmaApiError):
        asyncio.run(client.async_get_aws_observation(stn=108))
