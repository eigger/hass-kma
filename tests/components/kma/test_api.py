"""api.py 순수 함수 및 클라이언트 단위 테스트 — 네트워크 호출 없음."""

import asyncio
import json

import aiohttp
import pytest

from custom_components.kma.api import (
    KmaActivationRequiredError,
    KmaApiClient,
    KmaApiError,
    KmaAuthError,
    KmaSecurityPolicyError,
    KmaTransientError,
    Pm10HourlyStats,
    Pm10Observation,
    SnowObservation,
    StationBulletin,
    _hourly_current,
    _is_allowed_public_url,
    _is_png,
    _normalize_public_url,
    _parse_pm10_hourly_line,
    _parse_pm10_line,
    _parse_snow_line,
    _parse_station_bulletins,
    _parse_typ02_items,
    _raise_for_error_payload,
    _split_with_trailing_quoted,
    _to_float,
    _to_int,
    bulletin_section,
    iter_data_lines,
    split_bulletin_sections,
)


# ---------------------------------------------------------------------------
# iter_data_lines
# ---------------------------------------------------------------------------
class TestIterDataLines:
    def test_skips_comment_lines(self):
        text = "# comment\ndata1\n# another\ndata2"
        assert list(iter_data_lines(text)) == ["data1", "data2"]

    def test_skips_empty_lines(self):
        text = "\ndata1\n\ndata2\n"
        assert list(iter_data_lines(text)) == ["data1", "data2"]

    def test_skips_start_marker(self):
        text = "#START7777\ndata1\n#7777END"
        assert list(iter_data_lines(text)) == ["data1"]

    def test_empty_input(self):
        assert list(iter_data_lines("")) == []

    def test_all_comments(self):
        text = "# line1\n# line2"
        assert list(iter_data_lines(text)) == []

    def test_strips_whitespace(self):
        text = "  data1  \n  # comment  "
        result = list(iter_data_lines(text))
        assert result == ["data1"]


# ---------------------------------------------------------------------------
# _to_int
# ---------------------------------------------------------------------------
class TestToInt:
    def test_normal_value(self):
        assert _to_int("5") == 5

    def test_negative_value(self):
        assert _to_int("-10") == -10

    def test_missing_value(self):
        assert _to_int("-99") is None

    def test_invalid_string(self):
        assert _to_int("abc") is None

    def test_none_input(self):
        assert _to_int(None) is None


# ---------------------------------------------------------------------------
# _to_float
# ---------------------------------------------------------------------------
class TestToFloat:
    def test_normal_value(self):
        assert _to_float("3.14") == pytest.approx(3.14)

    def test_integer_string(self):
        assert _to_float("5") == pytest.approx(5.0)

    def test_missing_float(self):
        assert _to_float("-99.0") is None

    def test_missing_int(self):
        assert _to_float("-99") is None

    def test_invalid_string(self):
        assert _to_float("abc") is None

    def test_none_input(self):
        assert _to_float(None) is None

    def test_zero(self):
        assert _to_float("0.0") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _split_with_trailing_quoted
# ---------------------------------------------------------------------------
class TestSplitWithTrailingQuoted:
    def test_quoted_wf_with_spaces(self):
        line = '11B10101 202506191200 202506191200 A01 1 STN N NE 15 60 DB03 1 "흐리고 한때 비 곳"'
        head, wf = _split_with_trailing_quoted(line, 13)
        assert wf == "흐리고 한때 비 곳"
        assert "DB03" in head

    def test_simple_quoted(self):
        line = 'A B C "hello world"'
        head, tail = _split_with_trailing_quoted(line, 3)
        assert head == ["A", "B", "C"]
        assert tail == "hello world"

    def test_no_quotes_fallback(self):
        line = "A B C D"
        head, tail = _split_with_trailing_quoted(line, 3)
        assert head == ["A", "B", "C"]
        assert tail == "D"

    def test_empty_quoted(self):
        line = 'A B C ""'
        head, tail = _split_with_trailing_quoted(line, 3)
        assert tail == ""


# ---------------------------------------------------------------------------
# _parse_typ02_items
# ---------------------------------------------------------------------------
class TestParseTyp02Items:
    def _wrap(self, result_code: str, result_msg: str, items=None) -> str:
        body: dict = {}
        if items is not None:
            body = {"items": {"item": items}}
        return json.dumps(
            {
                "response": {
                    "header": {"resultCode": result_code, "resultMsg": result_msg},
                    "body": body,
                }
            }
        )

    def test_success_single_item(self):
        payload = self._wrap("00", "OK", [{"category": "T1H", "obsrValue": "22.5"}])
        result = _parse_typ02_items(payload, "test")
        assert len(result) == 1
        assert result[0]["category"] == "T1H"

    def test_success_multiple_items(self):
        items = [
            {"category": "T1H", "obsrValue": "22.5"},
            {"category": "RN1", "obsrValue": "0"},
        ]
        payload = self._wrap("00", "OK", items)
        result = _parse_typ02_items(payload, "test")
        assert len(result) == 2

    def test_nodata_03_returns_empty(self):
        payload = self._wrap("03", "NODATA_ERROR")
        result = _parse_typ02_items(payload, "test")
        assert result == []

    def test_nodata_04_returns_empty(self):
        payload = self._wrap("04", "NO_DATA")
        result = _parse_typ02_items(payload, "test")
        assert result == []

    def test_auth_error_raises(self):
        payload = self._wrap("10", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR")
        with pytest.raises(KmaAuthError):
            _parse_typ02_items(payload, "test")

    def test_generic_error_raises(self):
        payload = self._wrap("98", "SYSTEM_ERROR_REASON")
        with pytest.raises(KmaApiError):
            _parse_typ02_items(payload, "test")

    def test_nodata_99_returns_empty(self):
        # 생활기상지수/보건기상지수 API(예: 꽃가루)는 서비스 기간이 아니거나 지역코드에
        # 자료가 없을 때 커스텀 메시지와 함께 99를 반환한다 — NODATA로 취급해야 한다.
        payload = self._wrap(
            "99", "해당지수자료 제공기간이 아닙니다! [자료제공기간 3월 ~ 6월]"
        )
        result = _parse_typ02_items(payload, "test")
        assert result == []

    def test_invalid_json_raises(self):
        with pytest.raises(KmaApiError):
            _parse_typ02_items("not-json", "test")

    def test_success_no_items_returns_empty(self):
        payload = self._wrap("00", "OK", items=None)
        result = _parse_typ02_items(payload, "test")
        assert result == []

    def test_single_item_wrapped_in_list(self):
        # item 이 dict 하나(리스트 아님)인 경우
        single = {"category": "T1H", "obsrValue": "20.0"}
        payload = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "OK"},
                    "body": {"items": {"item": single}},
                }
            }
        )
        result = _parse_typ02_items(payload, "test")
        assert len(result) == 1
        assert result[0]["category"] == "T1H"


# ---------------------------------------------------------------------------
# _raise_for_error_payload
# ---------------------------------------------------------------------------
class TestRaiseForErrorPayload:
    def _body(self, status: int, message: str) -> str:
        return json.dumps({"result": {"status": status, "message": message}})

    def test_403_raises_activation_required(self):
        with pytest.raises(KmaActivationRequiredError):
            _raise_for_error_payload(403, self._body(403, "활용신청 필요"), "ep")

    def test_401_raises_auth_error(self):
        with pytest.raises(KmaAuthError):
            _raise_for_error_payload(401, self._body(401, "인증 오류"), "ep")

    def test_400_raises_auth_error(self):
        with pytest.raises(KmaAuthError):
            _raise_for_error_payload(400, self._body(400, "유효하지 않은 키"), "ep")

    def test_500_raises_api_error(self):
        with pytest.raises(KmaApiError):
            _raise_for_error_payload(500, self._body(500, "서버 오류"), "ep")

    def test_504_raises_transient_error(self):
        with pytest.raises(KmaTransientError):
            _raise_for_error_payload(504, self._body(504, "Gateway Timeout"), "ep")

    def test_invalid_json_raises_api_error(self):
        with pytest.raises(KmaApiError):
            _raise_for_error_payload(403, "not-json", "ep")

    def test_activation_error_has_endpoint(self):
        try:
            _raise_for_error_payload(403, self._body(403, "활용신청"), "my_endpoint")
        except KmaActivationRequiredError as exc:
            assert "my_endpoint" in str(exc)

    def test_auth_error_is_subclass_of_api_error(self):
        with pytest.raises(KmaApiError):
            _raise_for_error_payload(401, self._body(401, "인증 오류"), "ep")

    def test_json_list_body_is_not_an_error(self):
        # 자료가 없을 때 빈 배열을 돌려주는 엔드포인트(wrn_inf_rpt.php 등)
        _raise_for_error_payload(200, "[]", "ep")

    def test_json_list_body_with_error_status_raises(self):
        with pytest.raises(KmaApiError):
            _raise_for_error_payload(500, "[]", "ep")


# ---------------------------------------------------------------------------
# _parse_pm10_line (kma_pm10.php)
# ---------------------------------------------------------------------------
class TestParsePm10Line:
    def test_normal_line(self):
        obs = _parse_pm10_line("202607011800,   108,   39,000000,,=")
        assert obs == Pm10Observation(
            stn="108",
            tm="202607011800",
            pm10=pytest.approx(39.0),
            raw="202607011800,   108,   39,000000,,=",
        )

    def test_zero_reading(self):
        obs = _parse_pm10_line("202607012230,   100,    0,000000,,=")
        assert obs.pm10 == pytest.approx(0.0)

    def test_trailing_equals_stripped(self):
        # 트레일링 '=' 은 값이 아니라 종료 마커이므로 필드로 세면 안 됨
        obs = _parse_pm10_line("202607011800, 108, 39, 000000,,=")
        assert obs.tm == "202607011800"
        assert obs.stn == "108"

    def test_too_few_fields_returns_none(self):
        assert _parse_pm10_line("202607011800,108") is None

    def test_empty_line_returns_none(self):
        assert _parse_pm10_line("") is None

    def test_raw_preserved(self):
        line = "202607011800,   108,   39,000000,,="
        obs = _parse_pm10_line(line)
        assert obs.raw == line


# ---------------------------------------------------------------------------
# _hourly_current (getUVIdxV3 / getAirDiffusionIdxV3)
# ---------------------------------------------------------------------------
class TestHourlyCurrent:
    def test_h0_present(self):
        item = {"h0": "1", "h3": "7", "h6": "6"}
        assert _hourly_current(item) == pytest.approx(1.0)

    def test_h0_missing_falls_back_to_h3(self):
        item = {"h3": "75", "h6": "50"}
        assert _hourly_current(item) == pytest.approx(75.0)

    def test_h0_empty_string_falls_back(self):
        # UV 응답은 예보 끝자락에서 빈 문자열 슬롯이 나올 수 있음
        item = {"h0": "", "h3": "2"}
        assert _hourly_current(item) == pytest.approx(2.0)

    def test_all_empty_returns_none(self):
        item = {"h0": "", "h3": "", "h6": ""}
        assert _hourly_current(item) is None

    def test_no_hourly_keys_returns_none(self):
        assert _hourly_current({"date": "202607011200"}) is None


# ---------------------------------------------------------------------------
# _is_png (레이더/위성 이미지 게시 여부 판별)
# ---------------------------------------------------------------------------
class TestIsPng:
    def test_real_png_magic_bytes(self):
        assert _is_png(b"\x89PNG\r\n\x1a\n" + b"rest of file...") is True

    def test_euc_kr_error_text_is_not_png(self):
        # 아직 게시되지 않은 경우 "# file not exist" 같은 EUC-KR 텍스트가
        # HTTP 200으로 오는 것이 확인됨 — 실제 PNG가 아님.
        assert (
            _is_png("# file not exist (RDR_CMB_202607012320.png)".encode("euc-kr"))
            is False
        )

    def test_empty_bytes_is_not_png(self):
        assert _is_png(b"") is False

    def test_json_error_body_is_not_png(self):
        assert _is_png(b'{"result": {"status": 403}}') is False


# ---------------------------------------------------------------------------
# _parse_snow_line (kma_snow1.php)
# ---------------------------------------------------------------------------
class TestParseSnowLine:
    def test_normal_line(self):
        line = "202601151800,    93,           북춘천, 127.75443000,  37.94738000, 000-----,    0.5,="
        obs = _parse_snow_line(line)
        assert obs == SnowObservation(
            stn="93", tm="202601151800", depth=pytest.approx(0.5)
        )

    def test_zero_depth(self):
        line = "202607021900,   108,             서울, 126.96590000,  37.57140000, 000-----,    0.0,="
        obs = _parse_snow_line(line)
        assert obs.depth == pytest.approx(0.0)

    def test_too_few_fields_returns_none(self):
        assert _parse_snow_line("202601151800,93") is None

    def test_empty_line_returns_none(self):
        assert _parse_snow_line("") is None


# ---------------------------------------------------------------------------
# _parse_pm10_hourly_line (dst_pm10_hr.php)
# ---------------------------------------------------------------------------
class TestParsePm10HourlyLine:
    def test_normal_kma_line(self):
        line = "2026.07.02.17:00   kma     90     14(12)      6     22"
        stats = _parse_pm10_hourly_line(line)
        assert stats == Pm10HourlyStats(
            stn="90",
            tm="2026.07.02.17:00",
            avg=pytest.approx(14.0),
            min=pytest.approx(6.0),
            max=pytest.approx(22.0),
        )

    def test_non_kma_org_returns_none(self):
        # dst_pm10_hr.php는 org=cma(중국)/kcc/moe 데이터도 섞여 나오므로 제외해야 함
        line = "2026.07.02.17:00   cma  52203     78( 1)     78     78"
        assert _parse_pm10_hourly_line(line) is None

    def test_too_few_fields_returns_none(self):
        assert _parse_pm10_hourly_line("2026.07.02.17:00 kma") is None


# ---------------------------------------------------------------------------
# _parse_station_bulletins (wrn_inf_rpt.php / wthr_cmt_rpt.php 공용)
# ---------------------------------------------------------------------------
class TestParseStationBulletins:
    def test_single_bulletin(self):
        text = (
            "#START7777\n"
            "$0#109#202606280010#143#202606280012#2#김준형#tjwjdrnr#99#"
            "오늘까지 서해중부해상 바다 안개, 해상 안전사고 유의#\n"
            "$1#\n"
            "<안개 현황 및 전망>\n"
            "본문 내용 첫째줄\n"
            "본문 내용 둘째줄#\n"
            "=\n"
            "#7777END"
        )
        bulletins = _parse_station_bulletins(text)
        assert len(bulletins) == 1
        b = bulletins[0]
        assert b == StationBulletin(
            stn="109",
            issued_at="202606280010",
            title="오늘까지 서해중부해상 바다 안개, 해상 안전사고 유의",
            body="<안개 현황 및 전망>\n본문 내용 첫째줄\n본문 내용 둘째줄",
        )

    def test_multiple_bulletins(self):
        text = (
            "$0#109#202606280010#143#202606280012#2#김준형#tjwjdrnr#99#제목1#\n"
            "$1#\n본문1#\n=\n"
            "$0#156#202606280040#77#202606280045#2#송영철#2yeji#99#제목2#\n"
            "$1#\n본문2#\n=\n"
        )
        bulletins = _parse_station_bulletins(text)
        assert len(bulletins) == 2
        assert bulletins[0].stn == "109"
        assert bulletins[0].title == "제목1"
        assert bulletins[1].stn == "156"
        assert bulletins[1].title == "제목2"

    def test_empty_text_returns_empty_list(self):
        assert _parse_station_bulletins("") == []

    def test_no_header_returns_empty_list(self):
        assert _parse_station_bulletins("그냥 텍스트\n더 텍스트") == []


# ---------------------------------------------------------------------------
# split_bulletin_sections (기상정보/날씨해설 본문 → 섹션별 dict)
# ---------------------------------------------------------------------------
class TestSplitBulletinSections:
    def test_multiple_sections(self):
        body = "<중점 사항>\n오늘 소나기 예보\n\n<기온 및 하늘상태>\n낮 기온 30도 안팎"
        sections = split_bulletin_sections(body)
        assert sections == {
            "중점 사항": "오늘 소나기 예보",
            "기온 및 하늘상태": "낮 기온 30도 안팎",
        }

    def test_text_before_first_header_becomes_preamble(self):
        body = "머리말 텍스트\n<유의 사항>\n본문"
        sections = split_bulletin_sections(body)
        assert sections["머리말"] == "머리말 텍스트"
        assert sections["유의 사항"] == "본문"

    def test_no_headers_becomes_single_preamble_section(self):
        sections = split_bulletin_sections("소제목 없는 그냥 텍스트")
        assert sections == {"머리말": "소제목 없는 그냥 텍스트"}

    def test_empty_body_returns_empty_dict(self):
        assert split_bulletin_sections("") == {}

    def test_whitespace_only_body_returns_empty_dict(self):
        assert split_bulletin_sections("   \n   ") == {}

    def test_empty_section_is_dropped(self):
        body = "<빈 섹션>\n\n<실제 섹션>\n내용"
        sections = split_bulletin_sections(body)
        assert "빈 섹션" not in sections
        assert sections["실제 섹션"] == "내용"


# ---------------------------------------------------------------------------
# bulletin_section (고정 개수 "섹션 N" 슬롯 조회)
# ---------------------------------------------------------------------------
class TestBulletinSection:
    def _body(self, n: int) -> str:
        return "".join(f"<섹션{i}>\n내용{i}\n\n" for i in range(1, n + 1))

    def test_fewer_sections_than_slots(self):
        body = self._body(2)
        assert bulletin_section(body, slot=1, total_slots=5) == ("섹션1", "내용1")
        assert bulletin_section(body, slot=2, total_slots=5) == ("섹션2", "내용2")
        assert bulletin_section(body, slot=3, total_slots=5) is None

    def test_exact_match(self):
        body = self._body(3)
        assert bulletin_section(body, slot=3, total_slots=3) == ("섹션3", "내용3")

    def test_overflow_merges_into_last_slot(self):
        body = self._body(5)
        result = bulletin_section(body, slot=3, total_slots=3)
        assert result is not None
        heading, text = result
        assert heading == "섹션3 외 2건"
        assert "섹션3" in text and "섹션4" in text and "섹션5" in text
        assert "내용3" in text and "내용4" in text and "내용5" in text

    def test_overflow_single_remaining_section_keeps_own_heading(self):
        body = self._body(3)
        result = bulletin_section(body, slot=3, total_slots=3)
        assert result == ("섹션3", "내용3")

    def test_empty_body_returns_none(self):
        assert bulletin_section("", slot=1, total_slots=3) is None

    def test_slot_below_one_returns_none(self):
        assert bulletin_section(self._body(3), slot=0, total_slots=3) is None


# ---------------------------------------------------------------------------
# 공개 이미지 URL 검증 및 보안 (_is_allowed_public_url, _normalize_public_url)
# ---------------------------------------------------------------------------
class TestPublicUrlValidation:
    def test_allowed_kma_domains(self):
        assert _is_allowed_public_url("https://apihub.kma.go.kr/img.png") is True
        assert _is_allowed_public_url("https://nmsc.kma.go.kr/sat.png") is True
        assert _is_allowed_public_url("https://www.kma.go.kr/weather/image.png") is True
        assert _is_allowed_public_url("https://kma.go.kr/test.png") is True

    def test_allowed_weather_domains(self):
        assert _is_allowed_public_url("https://www.weather.go.kr/w/image.png") is True
        assert _is_allowed_public_url("https://weather.go.kr/sat.png") is True

    def test_allowed_data_go_kr_domains(self):
        assert _is_allowed_public_url("https://apis.data.go.kr/image.png") is True
        assert _is_allowed_public_url("https://data.go.kr/image.png") is True

    def test_normalizes_http_to_https_case_insensitive(self):
        assert (
            _normalize_public_url("http://nmsc.kma.go.kr/sat.png")
            == "https://nmsc.kma.go.kr/sat.png"
        )
        assert (
            _normalize_public_url("HTTP://nmsc.kma.go.kr/sat.png")
            == "https://nmsc.kma.go.kr/sat.png"
        )
        assert (
            _normalize_public_url("Http://nmsc.kma.go.kr/sat.png")
            == "https://nmsc.kma.go.kr/sat.png"
        )
        assert (
            _normalize_public_url("HTTPS://nmsc.kma.go.kr/sat.png")
            == "https://nmsc.kma.go.kr/sat.png"
        )

    def test_disallowed_domains_rejected(self):
        assert _is_allowed_public_url("https://evil-kma.go.kr/img.png") is False
        assert _is_allowed_public_url("https://attacker.com/img.png") is False
        assert _is_allowed_public_url("https://example.com/kma.go.kr") is False
        assert _is_allowed_public_url("https://192.168.1.1/img.png") is False
        assert _normalize_public_url("https://attacker.com/img.png") is None

    def test_userinfo_rejected(self):
        # https://nmsc.kma.go.kr@evil.com 등 사용자 정보 포함 URL 차단
        assert (
            _is_allowed_public_url("https://nmsc.kma.go.kr@evil.com/img.png") is False
        )
        assert (
            _is_allowed_public_url("https://user:pass@nmsc.kma.go.kr/img.png") is False
        )
        assert _normalize_public_url("https://nmsc.kma.go.kr@evil.com/img.png") is None
        assert _normalize_public_url("https://user:pass@nmsc.kma.go.kr/img.png") is None

    def test_invalid_schemes_rejected(self):
        assert _is_allowed_public_url("ftp://nmsc.kma.go.kr/img.png") is False
        assert _is_allowed_public_url("file:///etc/passwd") is False
        assert _is_allowed_public_url("javascript:alert(1)") is False
        assert _is_allowed_public_url("") is False
        assert _normalize_public_url("") is None


# ---------------------------------------------------------------------------
# API 요청 보안 단위 테스트 (_do_request, _request_public_binary, async_get_dust_satellite_image)
# ---------------------------------------------------------------------------
class _MockStreamReader:
    def __init__(self, data: bytes, chunk_size: int = 1024):
        self._data = data
        self._chunk_size = chunk_size

    async def iter_chunked(self, n: int):
        for i in range(0, len(self._data), n):
            yield self._data[i : i + n]

    async def read(self, n: int = -1) -> bytes:
        if n == -1 or n >= len(self._data):
            res = self._data
            self._data = b""
            return res
        chunk_len = min(n, self._chunk_size, len(self._data))
        res = self._data[:chunk_len]
        self._data = self._data[chunk_len:]
        return res


class _MockResponse:
    def __init__(
        self,
        raw: bytes,
        status: int = 200,
        content_type: str = "image/png",
        url: str = "https://nmsc.kma.go.kr/img.png",
        history: list | None = None,
        content_length: int | None = None,
        headers: dict[str, str] | None = None,
        stream_chunk_size: int = 1024,
    ):
        self._raw = raw
        self.status = status
        self.content_type = content_type
        self.url = url
        self.history = history or []
        self.content_length = content_length if content_length is not None else len(raw)
        self.headers = headers or {}
        self.content = _MockStreamReader(raw, chunk_size=stream_chunk_size)

    async def read(self) -> bytes:
        return self._raw

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class _MockSession:
    def __init__(self, handler=None):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if self.handler:
            return self.handler(url, **kwargs)
        return _MockResponse(b"OK", 200, "text/plain", url=url)


class TestDoRequestSecurity:
    async def test_allows_relative_apihub_endpoint(self):
        session = _MockSession()
        client = KmaApiClient(session, "secret-key")
        raw, status, ct = await client._do_request("kma_sfctm3.php", {"stn": 108})
        assert len(session.calls) == 1
        url, kwargs = session.calls[0]
        assert url == "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php"
        assert kwargs["params"] == {"stn": 108, "authKey": "secret-key"}

    async def test_allows_full_apihub_https_endpoint(self):
        session = _MockSession()
        client = KmaApiClient(session, "secret-key")
        endpoint = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-aws2_min"
        await client._do_request(endpoint, {"stn": 108})
        assert len(session.calls) == 1
        url, kwargs = session.calls[0]
        assert url == endpoint
        assert kwargs["params"] == {"stn": 108, "authKey": "secret-key"}

    async def test_rejects_plain_http_endpoint_without_sending_key(self):
        session = _MockSession()
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(KmaApiError, match="apihub.kma.go.kr"):
            await client._do_request("http://apihub.kma.go.kr/api/test", {})
        # 안전하지 않은 요청은 아예 네트워크 전송을 하지 않음
        assert len(session.calls) == 0

    async def test_rejects_uppercase_http_endpoint(self):
        session = _MockSession()
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(KmaApiError, match="apihub.kma.go.kr"):
            await client._do_request("HTTP://apihub.kma.go.kr/api/test", {})
        assert len(session.calls) == 0

    async def test_rejects_external_host_endpoint_without_sending_key(self):
        session = _MockSession()
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(KmaApiError, match="apihub.kma.go.kr"):
            await client._do_request("https://evil.com/api/test", {})
        assert len(session.calls) == 0

    async def test_rejects_userinfo_endpoint(self):
        session = _MockSession()
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(KmaApiError, match="apihub.kma.go.kr"):
            await client._do_request("https://user:pass@apihub.kma.go.kr/api/test", {})
        assert len(session.calls) == 0


class TestRequestPublicBinary:
    async def test_fetches_without_authkey(self):
        session = _MockSession(
            lambda url, **kw: _MockResponse(
                b"\x89PNG\r\n\x1a\nfake", 200, "image/png", url=url
            )
        )
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary("https://nmsc.kma.go.kr/img.png")
        assert result is not None
        raw, ct = result
        assert raw == b"\x89PNG\r\n\x1a\nfake"
        assert len(session.calls) == 1
        url, kwargs = session.calls[0]
        assert url == "https://nmsc.kma.go.kr/img.png"
        # params 가 전달되지 않고 authKey 가 노출되지 않음
        assert "params" not in kwargs

    async def test_upgrades_http_and_fetches(self):
        session = _MockSession(
            lambda url, **kw: _MockResponse(
                b"\x89PNG\r\n\x1a\nfake", 200, "image/png", url=url
            )
        )
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary("http://nmsc.kma.go.kr/img.png")
        assert result is not None
        assert session.calls[0][0] == "https://nmsc.kma.go.kr/img.png"

    async def test_skips_disallowed_host_without_request(self):
        session = _MockSession()
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(
            KmaSecurityPolicyError, match="허용되지 않은 공개 이미지 URL"
        ):
            await client._request_public_binary("https://attacker.com/img.png")
        assert len(session.calls) == 0

    async def test_handles_http_errors_gracefully(self):
        session = _MockSession(
            lambda url, **kw: _MockResponse(b"404 Not Found", 404, "text/html", url=url)
        )
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary(
            "https://nmsc.kma.go.kr/missing.png"
        )
        assert result is None

    async def test_reads_large_multi_chunk_image_completely(self):
        # 128 KiB 크기 데이터가 1024바이트 청크로 쪼개져 전달되더라도
        # iter_chunked를 통해 잘리지 않고 끝까지 온전히 읽힘을 검증
        large_png = b"\x89PNG\r\n\x1a\n" + b"X" * (128 * 1024)
        resp = _MockResponse(large_png, 200, "image/png", stream_chunk_size=1024)
        session = _MockSession(lambda url, **kw: resp)
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary("https://nmsc.kma.go.kr/img.png")
        assert result is not None
        assert result[0] == large_png

    async def test_rejects_redirect_to_untrusted_host(self):
        # 비인가 호스트로 리다이렉트 시 2번째 요청을 보내기 전에 사전 차단됨 검증
        resp = _MockResponse(
            b"",
            302,
            "text/html",
            headers={"Location": "https://attacker.com/evil.png"},
        )
        session = _MockSession(lambda url, **kw: resp)
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(
            KmaSecurityPolicyError, match="허용되지 않은 공개 이미지 리다이렉트 대상"
        ):
            await client._request_public_binary("https://nmsc.kma.go.kr/img.png")
        assert len(session.calls) == 1

    async def test_rejects_redirect_to_plain_http(self):
        # 비보안 HTTP로 리다이렉트 시 2번째 요청을 보내기 전에 사전 차단됨 검증
        resp = _MockResponse(
            b"",
            302,
            "text/html",
            headers={"Location": "http://nmsc.kma.go.kr/insecure.png"},
        )
        session = _MockSession(lambda url, **kw: resp)
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(
            KmaSecurityPolicyError, match="허용되지 않은 공개 이미지 리다이렉트 대상"
        ):
            await client._request_public_binary("https://nmsc.kma.go.kr/img.png")
        assert len(session.calls) == 1

    async def test_allows_relative_path_redirect(self):
        def handler(url: str, **kwargs):
            if "/old_path.png" in url:
                return _MockResponse(
                    b"",
                    302,
                    "text/html",
                    headers={"Location": "/new_path.png"},
                    url=url,
                )
            return _MockResponse(
                b"\x89PNG\r\n\x1a\nvalid",
                200,
                "image/png",
                url=url,
            )

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary(
            "https://nmsc.kma.go.kr/old_path.png"
        )
        assert result is not None
        assert result[0] == b"\x89PNG\r\n\x1a\nvalid"
        assert len(session.calls) == 2
        assert session.calls[1][0] == "https://nmsc.kma.go.kr/new_path.png"

    async def test_handles_redirect_missing_location_gracefully(self):
        resp = _MockResponse(b"", 302, "text/html", headers={})
        session = _MockSession(lambda url, **kw: resp)
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary("https://nmsc.kma.go.kr/img.png")
        assert result is None
        assert len(session.calls) == 1

    async def test_allows_redirect_within_trusted_hosts(self):
        def handler(url: str, **kwargs):
            if "weather.go.kr" in url:
                return _MockResponse(
                    b"",
                    302,
                    "text/html",
                    headers={"Location": "https://nmsc.kma.go.kr/img.png"},
                    url=url,
                )
            return _MockResponse(
                b"\x89PNG\r\n\x1a\nvalid",
                200,
                "image/png",
                url=url,
            )

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary("https://weather.go.kr/img.png")
        assert result is not None
        assert result[0] == b"\x89PNG\r\n\x1a\nvalid"
        assert len(session.calls) == 2
        assert session.calls[0][1]["allow_redirects"] is False
        assert session.calls[1][1]["allow_redirects"] is False

    async def test_rejects_redirect_exceeding_max_hops(self):
        loop_resp = _MockResponse(
            b"",
            302,
            "text/html",
            headers={"Location": "https://nmsc.kma.go.kr/loop.png"},
        )
        session = _MockSession(lambda url, **kw: loop_resp)
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary(
            "https://nmsc.kma.go.kr/start.png", max_redirects=3
        )
        assert result is None
        assert len(session.calls) == 4

    async def test_rejects_oversized_content_length(self):
        resp = _MockResponse(b"huge", 200, "image/png", content_length=15 * 1024 * 1024)
        session = _MockSession(lambda url, **kw: resp)
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary("https://nmsc.kma.go.kr/huge.png")
        assert result is None

    async def test_rejects_oversized_stream_data(self):
        large_data = b"x" * (11 * 1024 * 1024)
        resp = _MockResponse(large_data, 200, "image/png")
        session = _MockSession(lambda url, **kw: resp)
        client = KmaApiClient(session, "secret-key")
        result = await client._request_public_binary("https://nmsc.kma.go.kr/huge.png")
        assert result is None

    async def test_raises_transient_error_on_connection_failure(self):
        def raise_client_error(url, **kw):
            raise aiohttp.ClientConnectionError("Connection refused")

        session = _MockSession(raise_client_error)
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(KmaTransientError, match="공개 이미지 연결 오류"):
            await client._request_public_binary("https://nmsc.kma.go.kr/img.png")

    async def test_raises_transient_error_on_timeout(self):
        def raise_timeout(url, **kw):
            raise asyncio.TimeoutError()

        session = _MockSession(raise_timeout)
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(KmaTransientError, match="공개 이미지 연결 오류"):
            await client._request_public_binary("https://nmsc.kma.go.kr/img.png")


class TestAsyncGetDustSatelliteImage:
    async def test_fetches_public_image_without_authkey(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "satImgC-file-Sate": "[http://nmsc.kma.go.kr/dust1.png, https://nmsc.kma.go.kr/dust2.png]"
                                }
                            ]
                        }
                    },
                }
            }
        )

        def handler(url: str, **kwargs):
            if "YdstInfoService" in url:
                return _MockResponse(
                    json_resp.encode("utf-8"), 200, "application/json", url=url
                )
            if "dust2.png" in url:
                return _MockResponse(
                    b"\x89PNG\r\n\x1a\nvalid_png_2", 200, "image/png", url=url
                )
            return _MockResponse(b"error", 404, "text/html", url=url)

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        img = await client.async_get_dust_satellite_image()

        assert img is not None
        assert img.filename == "dust2.png"
        assert img.data == b"\x89PNG\r\n\x1a\nvalid_png_2"
        # 1. 이미지 요청 시 authKey가 전달되지 않음
        image_calls = [c for c in session.calls if "dust2.png" in c[0]]
        assert len(image_calls) == 1
        assert "params" not in image_calls[0][1]

        # 2. 역방향 검증: typ02 메타데이터 목록 요청 시에는 authKey가 정상 포함됨
        meta_calls = [c for c in session.calls if "YdstInfoService" in c[0]]
        assert len(meta_calls) == 1
        assert meta_calls[0][1]["params"]["authKey"] == "secret-key"

    async def test_falls_back_to_previous_published_image(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "satImgC-file-Sate": "[https://nmsc.kma.go.kr/dust1.png, https://nmsc.kma.go.kr/dust2.png]"
                                }
                            ]
                        }
                    },
                }
            }
        )

        def handler(url: str, **kwargs):
            if "YdstInfoService" in url:
                return _MockResponse(
                    json_resp.encode("utf-8"), 200, "application/json", url=url
                )
            if "dust2.png" in url:
                # 아직 게시되지 않아 200이지만 HTML 에러가 오는 경우
                return _MockResponse(
                    b"<html>not ready</html>", 200, "text/html", url=url
                )
            if "dust1.png" in url:
                return _MockResponse(
                    b"\x89PNG\r\n\x1a\nvalid_png_1", 200, "image/png", url=url
                )
            return _MockResponse(b"404", 404, "text/html", url=url)

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        img = await client.async_get_dust_satellite_image()

        assert img is not None
        assert img.filename == "dust1.png"
        assert img.data == b"\x89PNG\r\n\x1a\nvalid_png_1"

    async def test_raises_transient_error_after_two_consecutive_failures(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "satImgC-file-Sate": "[https://nmsc.kma.go.kr/dust1.png, https://nmsc.kma.go.kr/dust2.png, https://nmsc.kma.go.kr/dust3.png]"
                                }
                            ]
                        }
                    },
                }
            }
        )

        call_count = 0

        def handler(url: str, **kwargs):
            nonlocal call_count
            if "YdstInfoService" in url:
                return _MockResponse(
                    json_resp.encode("utf-8"), 200, "application/json", url=url
                )
            call_count += 1
            raise aiohttp.ClientConnectionError("Server unreachable")

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(KmaTransientError, match="공개 이미지 연결 오류"):
            await client.async_get_dust_satellite_image()

        # 2회 연속 실패 시 12개를 전부 대기하지 않고 즉시 전파됨 확인
        assert call_count == 2

    async def test_recovers_from_single_transient_error_to_previous_candidate(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "satImgC-file-Sate": "[https://nmsc.kma.go.kr/dust1.png, https://nmsc.kma.go.kr/dust2.png]"
                                }
                            ]
                        }
                    },
                }
            }
        )

        def handler(url: str, **kwargs):
            if "YdstInfoService" in url:
                return _MockResponse(
                    json_resp.encode("utf-8"), 200, "application/json", url=url
                )
            if "dust2.png" in url:
                # 최신 이미지가 일시적 전송 오류를 낸 경우
                raise aiohttp.ClientConnectionError("Socket reset")
            if "dust1.png" in url:
                # 이전 이미지는 정상 제공되는 경우
                return _MockResponse(
                    b"\x89PNG\r\n\x1a\nvalid_png_1", 200, "image/png", url=url
                )
            return _MockResponse(b"404", 404, "text/html", url=url)

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        img = await client.async_get_dust_satellite_image()
        assert img is not None
        assert img.filename == "dust1.png"
        assert img.data == b"\x89PNG\r\n\x1a\nvalid_png_1"

    async def test_returns_none_if_no_items(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "03", "resultMsg": "NO DATA"},
                    "body": {},
                }
            }
        )
        session = _MockSession(
            lambda url, **kw: _MockResponse(
                json_resp.encode("utf-8"), 200, "application/json", url=url
            )
        )
        client = KmaApiClient(session, "secret-key")
        img = await client.async_get_dust_satellite_image()
        assert img is None

    async def test_raises_kma_security_policy_error_when_all_candidates_rejected(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "satImgC-file-Sate": "[https://attacker.com/1.png, https://evil.com/2.png]"
                                }
                            ]
                        }
                    },
                }
            }
        )
        session = _MockSession(
            lambda url, **kw: _MockResponse(
                json_resp.encode("utf-8"), 200, "application/json", url=url
            )
        )
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(
            KmaSecurityPolicyError, match="허용되지 않은 공개 이미지 URL"
        ):
            await client.async_get_dust_satellite_image()

    async def test_raises_kma_security_policy_error_when_redirect_target_rejected(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "satImgC-file-Sate": "[https://nmsc.kma.go.kr/redirect.png]"
                                }
                            ]
                        }
                    },
                }
            }
        )

        def handler(url: str, **kwargs):
            if "YdstInfoService" in url:
                return _MockResponse(
                    json_resp.encode("utf-8"), 200, "application/json", url=url
                )
            return _MockResponse(
                b"",
                302,
                "text/html",
                headers={"Location": "https://untrusted-cdn.com/dust.png"},
                url=url,
            )

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        with pytest.raises(
            KmaSecurityPolicyError, match="허용되지 않은 공개 이미지 리다이렉트 대상"
        ):
            await client.async_get_dust_satellite_image()

    async def test_succeeds_when_mixed_with_disallowed_and_valid_candidates(self):
        json_resp = json.dumps(
            {
                "response": {
                    "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
                    "body": {
                        "items": {
                            "item": [
                                {
                                    "satImgC-file-Sate": "[https://nmsc.kma.go.kr/valid.png, https://attacker.com/evil.png]"
                                }
                            ]
                        }
                    },
                }
            }
        )

        def handler(url: str, **kwargs):
            if "YdstInfoService" in url:
                return _MockResponse(
                    json_resp.encode("utf-8"), 200, "application/json", url=url
                )
            if "valid.png" in url:
                return _MockResponse(
                    b"\x89PNG\r\n\x1a\nvalid_mixed", 200, "image/png", url=url
                )
            return _MockResponse(b"error", 404, "text/html", url=url)

        session = _MockSession(handler)
        client = KmaApiClient(session, "secret-key")
        img = await client.async_get_dust_satellite_image()
        assert img is not None
        assert img.filename == "valid.png"
        assert img.data == b"\x89PNG\r\n\x1a\nvalid_mixed"
