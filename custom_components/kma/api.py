"""기상청 API허브(apihub.kma.go.kr) 비동기 클라이언트 및 응답 파서.

공통 사항 (실측 검증 2026-06-19):
- 베이스 URL: https://apihub.kma.go.kr/api/typ01/url/
- 모든 요청에 authKey 필수.
- 정상 응답은 EUC-KR 인코딩 고정폭/공백구분 텍스트.
  주석/마커 라인은 '#'로 시작(#START7777 ... #7777END), 데이터 라인은 비-'#'.
- 미활용신청 엔드포인트는 HTTP 403 + JSON 본문으로 응답:
  {"result": {"status": 403, "message": "활용신청이 필요한 API 입니다..."}}

활용신청 현황(이 키 기준):
- 사용 가능: fct_shrt_reg.php
- 활용신청 필요(403): getVilageFcst, getUltraSrtNcst, fct_afs_ds/dl/do,
  wrn_now_data, wrn_met_data, kma_sfctm2.php, 지진정보 API 등
→ 403 엔드포인트의 상세 파서는 활용신청 후 실제 샘플로 확정(아래 TODO).
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from dataclasses import dataclass
from typing import Any, Iterator

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://apihub.kma.go.kr/api/typ01/url"
DEFAULT_TIMEOUT = 30
ENCODING = "euc-kr"


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------
class KmaApiError(Exception):
    """KMA API 호출 일반 오류."""


class KmaAuthError(KmaApiError):
    """authKey가 유효하지 않음."""


class KmaActivationRequiredError(KmaApiError):
    """해당 엔드포인트에 활용신청이 필요함(HTTP 403)."""

    def __init__(self, endpoint: str, message: str) -> None:
        self.endpoint = endpoint
        super().__init__(f"활용신청 필요: {endpoint} ({message})")


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ForecastRegion:
    """단기 예보구역 (fct_shrt_reg.php)."""

    reg_id: str       # 예보구역코드
    tm_st: str        # 시작시각 YYYYMMDDHHMM
    tm_ed: str        # 종료시각 YYYYMMDDHHMM
    reg_sp: str       # 특성코드 (A 육상광역, B 육상국지, C 도시, ...)
    reg_name: str     # 예보구역명


@dataclass(frozen=True)
class LandForecast:
    """단기 육상예보 1구간 (fct_afs_dl.php).

    원시 17컬럼: REG_ID TM_FC TM_EF MOD NE STN C MAN_ID MAN_FC
                 W1 T W2 TA ST SKY PREP WF
    """

    reg_id: str          # 예보구역코드
    tm_fc: str           # 발표시각 YYYYMMDDHHMM
    tm_ef: str           # 발효시각 YYYYMMDDHHMM
    mod: str             # 구간 (A01=24h, A02=12h)
    ne: str              # 발효번호
    stn: str             # 발표관서
    wind_dir1: str       # 풍향1 (16방위)
    wind_dir2: str       # 풍향2 (16방위)
    ta: int | None       # 기온(℃), -99 → None
    pop: int | None      # 강수확률(%), -99 → None
    sky: str             # 하늘상태코드 (DB01~DB04)
    prep: str            # 강수유무코드 (0~4)
    wf: str              # 예보 문구

    @property
    def sky_text(self) -> str:
        return SKY_CODES.get(self.sky, self.sky)

    @property
    def prep_text(self) -> str:
        return PREP_CODES.get(self.prep, self.prep)


@dataclass(frozen=True)
class MarineForecast:
    """단기 해상예보 1구간 (fct_afs_do.php).

    원시 19컬럼: REG_ID TM_FC TM_EF MOD NE STN C MAN_ID MAN_FC
                 W1 T W2 S1 S2 WH1 WH2 SKY PREP WF
    """

    reg_id: str          # 예보구역코드
    tm_fc: str           # 발표시각 YYYYMMDDHHMM
    tm_ef: str           # 발효시각 YYYYMMDDHHMM
    mod: str             # 구간 (A01=24h, A02=12h)
    ne: str              # 발효번호
    stn: str             # 발표관서
    wind_dir1: str       # 풍향1 (16방위)
    wind_dir2: str       # 풍향2 (16방위)
    wind_speed1: float | None # 풍속1 (m/s), -99 -> None
    wind_speed2: float | None # 풍속2 (m/s), -99 -> None
    wh_min: float | None # 최소 파고(m), -99 -> None
    wh_max: float | None # 최대 파고(m), -99 -> None
    sky: str             # 하늘상태코드 (DB01~DB04)
    prep: str            # 강수유무코드 (0~4)
    wf: str              # 예보 문구

    @property
    def sky_text(self) -> str:
        return SKY_CODES.get(self.sky, self.sky)

    @property
    def prep_text(self) -> str:
        return PREP_CODES.get(self.prep, self.prep)


@dataclass(frozen=True)
class VillageForecast:
    """동네예보 지점 예보값 (getVilageFcst)."""

    fcst_date: str       # 예보일자 YYYYMMDD
    fcst_time: str       # 예보시각 HHMM
    tmp: float | None    # 1시간 기온 (℃)
    uuu: float | None    # 동서풍속 (m/s)
    vvv: float | None    # 남북풍속 (m/s)
    vec: float | None    # 풍향 (deg)
    wsd: float | None    # 풍속 (m/s)
    sky: str | None      # 하늘상태 (1:맑음, 3:구름많음, 4:흐림)
    pty: str | None      # 강수형태 (0:없음, 1:비, 2:비/눈, 3:눈, 4:소나기)
    pop: float | None    # 강수확률 (%)
    pcp: str | None      # 1시간 강수량
    sno: str | None      # 1시간 신적설
    reh: float | None    # 습도 (%)


@dataclass(frozen=True)
class UltraNcst:
    """초단기실황 (getUltraSrtNcst) — 실제 관측값."""

    base_date: str
    base_time: str
    t1h: float | None    # 기온 (℃)
    rn1: float | None    # 1시간 강수량 (mm)
    reh: float | None    # 습도 (%)
    pty: str | None      # 강수형태 (0:없음,1:비,2:비/눈,3:눈,5:빗방울,6:빗방울눈날림,7:눈날림)
    wsd: float | None    # 풍속 (m/s)
    vec: float | None    # 풍향 (deg)
    uuu: float | None    # 동서풍속
    vvv: float | None    # 남북풍속


@dataclass(frozen=True)
class UltraFcst:
    """초단기예보 (getUltraSrtFcst) — 6시간 이내 단기 예보 (SKY 포함)."""

    fcst_date: str
    fcst_time: str
    t1h: float | None    # 기온 (℃)
    sky: str | None      # 하늘상태 (1:맑음,3:구름많음,4:흐림)
    pty: str | None      # 강수형태
    reh: float | None    # 습도 (%)
    wsd: float | None    # 풍속 (m/s)
    vec: float | None    # 풍향 (deg)
    rn1: str | None      # 1시간 강수량 (범주 문자열, 예 "강수없음"/"1.0mm")


# 하늘상태코드
SKY_CODES: dict[str, str] = {
    "DB01": "맑음",
    "DB02": "구름조금",
    "DB03": "구름많음",
    "DB04": "흐림",
}

# 강수유무코드
PREP_CODES: dict[str, str] = {
    "0": "없음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "4": "소나기",
}


# REG_SP 특성코드 의미 (헤더 주석에서 추출)
REG_SP_MEANINGS: dict[str, str] = {
    "A": "육상광역",
    "B": "육상국지",
    "C": "도시",
    "D": "산악",
    "E": "고속도로",
    "H": "해상광역",
    "I": "해상국지",
    "J": "연안바다",
    "K": "해수욕장",
    "L": "연안항로",
    "M": "먼항로",
    "P": "산악",
}


# ---------------------------------------------------------------------------
# 파싱 헬퍼
# ---------------------------------------------------------------------------
def iter_data_lines(text: str) -> Iterator[str]:
    """주석('#')/공백 라인을 제외한 데이터 라인만 순회."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        yield line


def _to_int(value: str) -> int | None:
    """정수 변환. 결측값(-99)이나 비정상은 None."""
    try:
        num = int(value)
    except (ValueError, TypeError):
        return None
    return None if num == -99 else num


def _to_float(value: str) -> float | None:
    """실수 변환. 결측값(-99, -99.0)이나 비정상은 None."""
    try:
        num = float(value)
    except (ValueError, TypeError):
        return None
    return None if num in (-99.0, -99) else num


def _split_with_trailing_quoted(line: str, head_count: int) -> tuple[list[str], str]:
    """앞쪽 공백구분 필드 + 큰따옴표로 감싼 마지막 필드를 분리.

    예: '... DB04    0 "흐리고 한때 비 곳"'
    → (['...', 'DB04', '0'], '흐리고 한때 비 곳')
    따옴표가 없으면 마지막 토큰을 trailing으로 감주(폴백).
    """
    quote_idx = line.find('"')
    if quote_idx != -1:
        head = line[:quote_idx].split()
        tail = line[quote_idx:].strip().strip('"')
    else:
        parts = line.split()
        head = parts[:head_count]
        tail = parts[head_count] if len(parts) > head_count else ""
    return head, tail


def parse_header_columns(text: str) -> list[str]:
    """텍스트의 `#` 주석 라인 중에서 필드 목록을 정의한 라인을 찾아 컬럼 이름 리스트를 반환."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") and not line.startswith("#START") and not line.startswith("#7777"):
            parts = line[1:].strip().split()
            # 도움말 정의 라인(콜론 포함) 및 필드가 아주 적은 라인은 제외
            if parts and len(parts) > 5 and ":" not in "".join(parts):
                if any(k in parts for k in ("REG_ID", "STN", "STN_ID", "REG_UP")):
                    # 특수 문자(대시 등) 제거하여 컬럼명 정제
                    cleaned_parts = [p.split("-")[0].strip() for p in parts]
                    return cleaned_parts
    return []


def _raise_for_error_payload(status: int, body: str, endpoint: str) -> None:
    """JSON 오류 본문(UTF-8)을 파싱해 적절한 예외를 발생.

    이 함수는 content-type이 JSON일 때만 호출된다(typ01 텍스트 API에서
    JSON 본문은 항상 오류 응답).
    """
    try:
        payload: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError:
        raise KmaApiError(f"{endpoint}: HTTP {status}: {body[:200]}")

    result = payload.get("result", payload)
    code = result.get("status", status)
    message = result.get("message", "")

    if code == 403:
        raise KmaActivationRequiredError(endpoint, message)
    if code in (401, 400) or "인증" in message or "유효하지 않은" in message:
        # 잘못된 키 / 유효하지 않은 API 등
        raise KmaAuthError(f"{endpoint}: {message or code}")
    raise KmaApiError(f"{endpoint}: status={code} {message}")


_KST = datetime.timezone(datetime.timedelta(hours=9))


def _now_kst() -> datetime.datetime:
    """KST(UTC+9, DST 없음) 현재시각(naive). 프로세스 타임존과 무관하게 안전."""
    return datetime.datetime.now(_KST).replace(tzinfo=None)


def _parse_typ02_items(text: str, name: str) -> list[dict[str, Any]]:
    """typ02 openApi(JSON) 응답에서 item 리스트를 추출.

    NODATA(03/04)는 빈 리스트, 인증/기타 오류는 예외.
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as err:
        raise KmaApiError(f"{name}: JSON 디코딩 실패: {err}") from err

    response = payload.get("response", {})
    header = response.get("header", {})
    code = header.get("resultCode")
    msg = header.get("resultMsg", "")
    if code != "00":
        if code in ("03", "04"):
            return []
        if "SERVICE_KEY" in msg or "인증" in msg:
            raise KmaAuthError(f"{name}: {msg} ({code})")
        raise KmaApiError(f"{name}: {msg} ({code})")

    items = response.get("body", {}).get("items", {})
    if not items or "item" not in items:
        return []
    item = items["item"]
    return item if isinstance(item, list) else [item]


# ---------------------------------------------------------------------------
# 클라이언트
# ---------------------------------------------------------------------------
class KmaApiClient:
    """apihub typ01 텍스트 API 비동기 클라이언트."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth_key: str,
        *,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = session
        self._auth_key = auth_key
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _request(
        self, endpoint: str, params: dict[str, Any], *, is_json_api: bool = False
    ) -> str:
        """엔드포인트를 호출하고 디코딩된 텍스트를 반환.

        endpoint 예: "fct_shrt_reg.php". authKey는 자동 부착.
        오류 응답(403/인증 등)은 예외로 변환.
        """
        if endpoint.startswith("http"):
            url = endpoint
        elif "typ02" in endpoint or "openApi" in endpoint:
            url = f"https://apihub.kma.go.kr/{endpoint.lstrip('/')}"
        else:
            url = f"{self._base_url}/{endpoint}"

        query = {**params, "authKey": self._auth_key}
        # 값이 None인 파라미터는 제거
        query = {k: v for k, v in query.items() if v is not None}

        _LOGGER.debug("KMA GET %s params=%s", endpoint, params)
        try:
            async with self._session.get(
                url, params=query, timeout=self._timeout
            ) as resp:
                raw = await resp.read()
                status = resp.status
                content_type = resp.content_type or ""
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise KmaApiError(f"{endpoint}: 연결 오류: {err}") from err

        # 오류 응답은 JSON(UTF-8), 정상 데이터는 EUC-KR 텍스트.
        # 단, typ02 API는 정상 데이터도 JSON이므로 구분하여 처리해야 함.
        if "json" in content_type:
            body_str = raw.decode("utf-8", errors="replace")
            if is_json_api:
                # 에러 구조인지 먼저 체크
                try:
                    payload = json.loads(body_str)
                    if "result" in payload:
                        _raise_for_error_payload(status, body_str, endpoint)
                except json.JSONDecodeError:
                    pass
                return body_str
            else:
                _raise_for_error_payload(
                    status, body_str, endpoint
                )
                return body_str

        if status != 200:
            raise KmaApiError(f"{endpoint}: HTTP {status}")
        return raw.decode(ENCODING, errors="replace")

    # -- seqApi=10 예·특보 --------------------------------------------------

    async def async_get_forecast_regions(self) -> list[ForecastRegion]:
        """단기 예보구역 목록 조회 (fct_shrt_reg.php). [활용신청 완료, 검증됨]

        라인 포맷: REG_ID TM_ST TM_ED REG_SP REG_NAME (공백 구분, 5필드)
        REG_NAME에는 내부 공백이 없음(실측 확인).
        """
        text = await self._request("fct_shrt_reg.php", {"tmfc": 0, "help": 0})
        regions: list[ForecastRegion] = []
        for line in iter_data_lines(text):
            parts = line.split()
            if len(parts) < 5:
                _LOGGER.debug("예보구역 파싱 스킵(필드부족): %r", line)
                continue
            reg_id, tm_st, tm_ed, reg_sp = parts[:4]
            reg_name = " ".join(parts[4:])  # 혹시 모를 공백 대비
            regions.append(
                ForecastRegion(reg_id, tm_st, tm_ed, reg_sp, reg_name)
            )
        _LOGGER.debug("예보구역 %d건 파싱", len(regions))
        return regions

    async def async_get_land_forecast(
        self, reg: str, *, tmfc1: str | None = None, tmfc2: str | None = None
    ) -> list[LandForecast]:
        """단기 육상예보 조회 (fct_afs_dl.php). [활용신청 완료, 검증됨]

        reg: 예보구역코드(필수). tmfc1/tmfc2: 발표시각 범위(미지정 시 최신).
        17컬럼이며 마지막 WF는 큰따옴표로 감싸여 내부 공백 포함.
        """
        text = await self._request(
            "fct_afs_dl.php",
            {"reg": reg, "tmfc1": tmfc1, "tmfc2": tmfc2, "disp": 0, "help": 0},
        )
        out: list[LandForecast] = []
        for line in iter_data_lines(text):
            # WF 앞 16개 필드 + 따옴표 WF
            head, wf = _split_with_trailing_quoted(line, 16)
            if len(head) < 16:
                _LOGGER.debug("육상예보 파싱 스킵(필드부족): %r", line)
                continue
            (
                reg_id, tm_fc, tm_ef, mod, ne, stn, _c, _man_id, _man_fc,
                w1, _t, w2, ta, pop, sky, prep,
            ) = head[:16]
            out.append(
                LandForecast(
                    reg_id=reg_id, tm_fc=tm_fc, tm_ef=tm_ef, mod=mod, ne=ne,
                    stn=stn, wind_dir1=w1, wind_dir2=w2,
                    ta=_to_int(ta), pop=_to_int(pop), sky=sky, prep=prep, wf=wf,
                )
            )
        _LOGGER.debug("육상예보 %d구간 파싱(reg=%s)", len(out), reg)
        return out

    async def async_get_marine_forecast(
        self, reg: str, *, tmfc1: str | None = None, tmfc2: str | None = None
    ) -> list[MarineForecast]:
        """단기 해상예보 조회 (fct_afs_do.php). [활용신청 완료, 검증됨]

        reg: 예보구역코드(필수). tmfc1/tmfc2: 발표시각 범위(미지정 시 최신).
        19컬럼이며 마지막 WF는 큰따옴표로 감싸여 내부 공백 포함.
        """
        if not tmfc1:
            import datetime
            now = datetime.datetime.now()
            # 기상청 데이터 안정성을 위해 오늘 00:00 ~ 내일 23:00를 기본 범위로 설정
            tmfc1 = now.strftime("%Y%m%d0000")
            if not tmfc2:
                tomorrow = now + datetime.timedelta(days=1)
                tmfc2 = tomorrow.strftime("%Y%m%d2300")

        text = await self._request(
            "fct_afs_do.php",
            {"reg": reg, "tmfc1": tmfc1, "tmfc2": tmfc2, "disp": 0, "help": 0},
        )
        out: list[MarineForecast] = []
        for line in iter_data_lines(text):
            head, wf = _split_with_trailing_quoted(line, 18)
            if len(head) < 18:
                _LOGGER.debug("해상예보 파싱 스킵(필드부족): %r", line)
                continue
            (
                reg_id, tm_fc, tm_ef, mod, ne, stn, _c, _man_id, _man_fc,
                w1, _t1, w2, s1, s2, wh1, wh2, sky, prep,
            ) = head[:18]
            out.append(
                MarineForecast(
                    reg_id=reg_id, tm_fc=tm_fc, tm_ef=tm_ef, mod=mod, ne=ne,
                    stn=stn, wind_dir1=w1, wind_dir2=w2,
                    wind_speed1=_to_float(s1), wind_speed2=_to_float(s2),
                    wh_min=_to_float(wh1), wh_max=_to_float(wh2),
                    sky=sky, prep=prep, wf=wf,
                )
            )
        _LOGGER.debug("해상예보 %d건 파싱(reg=%s)", len(out), reg)
        return out

    async def async_get_village_forecast(
        self, nx: int, ny: int, *, base_date: str | None = None, base_time: str | None = None
    ) -> list[VillageForecast]:
        """동네예보(단기예보) 지점자료 조회 (getVilageFcst). [활용신청 완료, 검증됨]

        기본적으로 JSON 응답을 호출 및 디코딩하여 VillageForecast 리스트로 반환.
        """
        import datetime
        now = datetime.datetime.now()
        # base_date/base_time 미지정 시 가장 최근 기상청 단기예보 발표 시각 추정
        if not base_date or not base_time:
            base_date = base_date or now.strftime("%Y%m%d")
            base_time = base_time or "0500"

        text = await self._request(
            "api/typ02/openApi/VilageFcstInfoService_2.0/getVilageFcst",
            {
                "base_date": base_date,
                "base_time": base_time,
                "nx": nx,
                "ny": ny,
                "dataType": "JSON",
                "numOfRows": 1000,
                "pageNo": 1,
            },
            is_json_api=True,
        )

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as err:
            raise KmaApiError(f"getVilageFcst: JSON 디코딩 실패: {err}") from err

        response = payload.get("response", {})
        header = response.get("header", {})
        result_code = header.get("resultCode")
        result_msg = header.get("resultMsg", "")

        if result_code != "00":
            # NODATA(03)/NO_DATA(04): 해당 발표시각 자료가 아직 없음 → 빈 결과로 처리
            # (코디네이터가 이전 발표시각으로 backoff 재시도하도록 예외를 던지지 않음)
            if result_code in ("03", "04"):
                _LOGGER.debug(
                    "getVilageFcst NODATA: base=%s%s nx=%s ny=%s",
                    base_date, base_time, nx, ny,
                )
                return []
            if "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in result_msg or "인증" in result_msg:
                raise KmaAuthError(f"getVilageFcst: {result_msg} ({result_code})")
            raise KmaApiError(f"getVilageFcst: {result_msg} ({result_code})")

        items = response.get("body", {}).get("items", {})
        if not items or "item" not in items:
            return []

        item_list = items["item"]
        grouped: dict[str, dict[str, Any]] = {}
        for it in item_list:
            date = it.get("fcstDate")
            time = it.get("fcstTime")
            if not date or not time:
                continue
            key = f"{date}{time}"
            if key not in grouped:
                grouped[key] = {
                    "fcstDate": date,
                    "fcstTime": time,
                }
            category = it.get("category")
            value = it.get("fcstValue")
            grouped[key][category] = value

        out: list[VillageForecast] = []
        for key, data in sorted(grouped.items()):
            fcst_date = data["fcstDate"]
            fcst_time = data["fcstTime"]
            
            tmp = _to_float(data.get("TMP"))
            uuu = _to_float(data.get("UUU"))
            vvv = _to_float(data.get("VVV"))
            vec = _to_float(data.get("VEC"))
            wsd = _to_float(data.get("WSD"))
            sky = data.get("SKY")
            pty = data.get("PTY")
            pop = _to_float(data.get("POP"))
            pcp = data.get("PCP")
            sno = data.get("SNO")
            reh = _to_float(data.get("REH"))

            out.append(
                VillageForecast(
                    fcst_date=fcst_date,
                    fcst_time=fcst_time,
                    tmp=tmp,
                    uuu=uuu,
                    vvv=vvv,
                    vec=vec,
                    wsd=wsd,
                    sky=sky,
                    pty=pty,
                    pop=pop,
                    pcp=pcp,
                    sno=sno,
                    reh=reh,
                )
            )
        return out

    async def async_get_ultra_ncst(
        self, nx: int, ny: int, *, now: datetime.datetime | None = None
    ) -> UltraNcst | None:
        """초단기실황 조회 (getUltraSrtNcst). [검증됨]

        실황은 매시각 정시(HH00) 발표, 약 40분 후 제공 → 40분 전 기준 정시를 사용.
        """
        now = now or _now_kst()
        t = now - datetime.timedelta(minutes=40)
        base_date, base_time = t.strftime("%Y%m%d"), f"{t.hour:02d}00"

        text = await self._request(
            "api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst",
            {
                "base_date": base_date, "base_time": base_time,
                "nx": nx, "ny": ny, "dataType": "JSON",
                "numOfRows": 60, "pageNo": 1,
            },
            is_json_api=True,
        )
        items = _parse_typ02_items(text, "getUltraSrtNcst")
        if not items:
            return None
        obs = {it.get("category"): it.get("obsrValue") for it in items}
        return UltraNcst(
            base_date=base_date, base_time=base_time,
            t1h=_to_float(obs.get("T1H")), rn1=_to_float(obs.get("RN1")),
            reh=_to_float(obs.get("REH")), pty=obs.get("PTY"),
            wsd=_to_float(obs.get("WSD")), vec=_to_float(obs.get("VEC")),
            uuu=_to_float(obs.get("UUU")), vvv=_to_float(obs.get("VVV")),
        )

    async def async_get_ultra_fcst(
        self, nx: int, ny: int, *, now: datetime.datetime | None = None
    ) -> list[UltraFcst]:
        """초단기예보 조회 (getUltraSrtFcst). [검증됨]

        매시각 HH30 발표, 약 45분 후 제공 → 45분 전 기준 HH30을 사용.
        실황에 없는 하늘상태(SKY)를 보완하는 용도.
        """
        now = now or _now_kst()
        t = now - datetime.timedelta(minutes=45)
        base_date, base_time = t.strftime("%Y%m%d"), f"{t.hour:02d}30"

        text = await self._request(
            "api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtFcst",
            {
                "base_date": base_date, "base_time": base_time,
                "nx": nx, "ny": ny, "dataType": "JSON",
                "numOfRows": 300, "pageNo": 1,
            },
            is_json_api=True,
        )
        items = _parse_typ02_items(text, "getUltraSrtFcst")
        grouped: dict[str, dict[str, Any]] = {}
        for it in items:
            key = f"{it.get('fcstDate')}{it.get('fcstTime')}"
            grouped.setdefault(key, {"fcstDate": it.get("fcstDate"), "fcstTime": it.get("fcstTime")})
            grouped[key][it.get("category")] = it.get("fcstValue")

        out: list[UltraFcst] = []
        for _key, d in sorted(grouped.items()):
            out.append(
                UltraFcst(
                    fcst_date=d["fcstDate"], fcst_time=d["fcstTime"],
                    t1h=_to_float(d.get("T1H")), sky=d.get("SKY"), pty=d.get("PTY"),
                    reh=_to_float(d.get("REH")), wsd=_to_float(d.get("WSD")),
                    vec=_to_float(d.get("VEC")), rn1=d.get("RN1"),
                )
            )
        return out

    async def async_get_warning_now(self, *, fe: str = "e") -> list[dict[str, Any]]:
        """기상특보 현황 (wrn_now_data.php). [활용신청 완료, 검증됨]

        쉼표(,)로 구분된 특보 데이터를 파싱하여 반환합니다.
        """
        text = await self._request(
            "wrn_now_data.php", {"fe": fe, "disp": 0, "help": 0}
        )
        cols = parse_header_columns(text)
        if not cols:
            cols = ["REG_UP", "REG_UP_KO", "REG_ID", "REG_KO", "TM_FC", "TM_EF", "WRN", "LVL", "CMD", "ED_TM"]

        out: list[dict[str, Any]] = []
        for line in iter_data_lines(text):
            parts = [p.strip() for p in line.split(",")]
            if parts and parts[-1] == "=":
                parts = parts[:-1]
            if len(parts) > len(cols):
                parts = parts[:len(cols)]
            if len(parts) != len(cols):
                continue
            row_dict = {cols[i]: parts[i] for i in range(len(cols))}
            row_dict["raw"] = line
            row_dict["fields"] = parts
            out.append(row_dict)
        return out

    async def async_get_warning_message(
        self, *, wrn: str = "", reg: str = "", tmfc1: str | None = None
    ) -> str:
        """기상특보 통보문 (wrn_met_data.php). [활용신청 필요]

        통보문 원본 텍스트 반환. 승인 전(403)에는 KmaActivationRequiredError를 발생시킴.
        """
        return await self._request(
            "wrn_met_data.php",
            {"wrn": wrn, "reg": reg, "tmfc1": tmfc1, "disp": 0, "help": 0},
        )

    # -- seqApi=2 지상관측 --------------------------------------------------

    async def async_get_asos_now(
        self, *, stn: str | int = 0, tm: str | None = None
    ) -> list[dict[str, Any]]:
        """ASOS 시간자료 (kma_sfctm2.php). [활용신청 필요 — 미검증]

        TODO: 활용신청 후 컬럼(TA 기온, HM 습도, WS 풍속, PA 기압 등) 매핑 확정.
        stn=0 이면 전체 지점.
        """
        text = await self._request(
            "kma_sfctm2.php", {"tm": tm, "stn": stn, "help": 0}
        )
        return [{"raw": line, "fields": line.split()} for line in iter_data_lines(text)]

    # -- seqApi=7 지진 ------------------------------------------------------

    async def async_get_earthquake_recent(self) -> list[dict[str, Any]]:
        """최근 지진정보. [활용신청 필요 — 미검증]

        TODO: 정확한 엔드포인트/파라미터/컬럼 확정.
        """
        raise NotImplementedError("지진 API 활용신청 후 엔드포인트 확정 필요")

    # -- 헬스체크 -----------------------------------------------------------

    async def async_validate_auth(self) -> bool:
        """authKey 유효성 검증. 활용신청된 fct_shrt_reg.php로 테스트 호출.

        KmaAuthError 발생 시 키 자체가 무효.
        KmaActivationRequiredError는 키는 유효하나 해당 API 미신청이므로
        키 검증 목적상으로는 '유효'로 간주.
        """
        try:
            await self.async_get_forecast_regions()
        except KmaActivationRequiredError:
            return True  # 키는 유효, 해당 API만 미신청
        except KmaAuthError:
            return False
        return True


# ---------------------------------------------------------------------------
# 개발용 수동 테스트:  python api.py <authKey>
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import sys

    # Windows 콘솔(cp949)에서 한글 출력 깨짐 방지
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(level=logging.INFO)

    async def _main(key: str) -> None:
        async with aiohttp.ClientSession() as session:
            client = KmaApiClient(session, key)

            print("== authKey 검증 ==")
            print("valid:", await client.async_validate_auth())

            print("\n== 예보구역(fct_shrt_reg) ==")
            regions = await client.async_get_forecast_regions()
            print(f"총 {len(regions)}건. 예시 5건:")
            for r in regions[:5]:
                sp = REG_SP_MEANINGS.get(r.reg_sp, r.reg_sp)
                print(f"  {r.reg_id} [{sp}] {r.reg_name}")

            print("\n== 육상예보(fct_afs_dl, reg=11B10101 서울) ==")
            try:
                fcsts = await client.async_get_land_forecast("11B10101")
                print(f"  {len(fcsts)}구간. 예시 6건:")
                for f in fcsts[:6]:
                    ta = f.ta if f.ta is not None else "-"
                    print(
                        f"  {f.tm_ef} TA={ta}℃ POP={f.pop}% "
                        f"{f.sky_text}/{f.prep_text} → {f.wf}"
                    )
            except KmaApiError as err:
                print("  실패:", err)

            print("\n== 해상예보(fct_afs_do, reg=12A10100) ==")
            try:
                m_fcsts = await client.async_get_marine_forecast("12A10100")
                print(f"  {len(m_fcsts)}구간. 예시 3건:")
                for mf in m_fcsts[:3]:
                    print(
                        f"  {mf.tm_ef} WH={mf.wh_min}~{mf.wh_max}m WS={mf.wind_speed1}~{mf.wind_speed2}m/s "
                        f"{mf.sky_text}/{mf.prep_text} → {mf.wf}"
                    )
            except KmaApiError as err:
                print("  실패:", err)

            print("\n== 동네예보(getVilageFcst, nx=55, ny=127) ==")
            try:
                v_fcsts = await client.async_get_village_forecast(55, 127)
                print(f"  {len(v_fcsts)}건. 예시 3건:")
                for vf in v_fcsts[:3]:
                    print(
                        f"  {vf.fcst_date} {vf.fcst_time} TMP={vf.tmp}℃ REH={vf.reh}% WSD={vf.wsd}m/s"
                    )
            except KmaApiError as err:
                print("  실패:", err)

            print("\n== 특보현황(wrn_now_data) 시도 ==")
            try:
                rows = await client.async_get_warning_now()
                print(f"  {len(rows)}건")
                for row in rows[:3]:
                    print("  ", row)
            except KmaApiError as err:
                print("  실패:", err)

    if len(sys.argv) < 2:
        print("사용법: python api.py <authKey>")
        sys.exit(1)
    asyncio.run(_main(sys.argv[1]))
