"""api.py 순수 함수 단위 테스트 — 네트워크 호출 없음."""
import json

import pytest

from custom_components.kma.api import (
    KmaActivationRequiredError,
    KmaApiError,
    KmaAuthError,
    _parse_typ02_items,
    _raise_for_error_payload,
    _split_with_trailing_quoted,
    _to_float,
    _to_int,
    iter_data_lines,
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
        return json.dumps({
            "response": {
                "header": {"resultCode": result_code, "resultMsg": result_msg},
                "body": body,
            }
        })

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
        payload = self._wrap("99", "SYSTEM_ERROR_REASON")
        with pytest.raises(KmaApiError):
            _parse_typ02_items(payload, "test")

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
        payload = json.dumps({
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"items": {"item": single}},
            }
        })
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
