"""기상청 API허브(apihub.kma.go.kr) 비동기 클라이언트 및 응답 파서.

공통 사항 (실측 검증 2026-06-19):
- 베이스 URL: https://apihub.kma.go.kr/api/typ01/url/
- 모든 요청에 authKey 필수.
- 정상 응답은 EUC-KR 인코딩 고정폭/공백구분 텍스트.
  주석/마커 라인은 '#'로 시작(#START7777 ... #7777END), 데이터 라인은 비-'#'.
- 미활용신청 엔드포인트는 HTTP 403 + JSON 본문으로 응답:
  {"result": {"status": 403, "message": "활용신청이 필요한 API 입니다..."}}

활용신청 현황(2026-06-19 키 기준):
- 사용 가능: fct_shrt_reg.php
- 활용신청 필요(403): getVilageFcst, getUltraSrtNcst, fct_afs_ds/dl/do,
  wrn_now_data, wrn_met_data, kma_sfctm2.php, 지진정보 API 등
→ 403 엔드포인트의 상세 파서는 활용신청 후 실제 샘플로 확정(아래 TODO).

PM10(미세먼지) — 실측 검증 완료(2026-07-01, 별도 키로 실제 authKey 호출):
- kma_pm10.php (seqApi=2 지상관측 > 황사관측(PM10)). 주의: stn_pm10_inf.php는
  관측"자료"가 아니라 관측소 메타데이터(지점정보)만 반환하므로 사용하지 않는다.
- 파라미터: tm1, tm2(YYYYMMDDHHMM), stn(지점번호, 0=전체). 5분 간격.
- 원시 포맷(쉼표구분, 트레일링 '='): TM,STN,PM10,FLAG,MQC,=

레이더/위성 이미지 — 엔드포인트명은 apihub 문서로 확인했으나(2026-07-01),
테스트 키 기준 활용신청 필요(403). 실제 응답 포맷은 활용신청 후 확정 필요:
- 레이더(seqApi=5): rdr_cmp_file_list.php(합성 파일목록), nph-rdr_cmp1_api(합성 이미지)
- 위성(seqApi=6): sat_file_list.php(파일목록), nph-gk2a_img(분포도 이미지)

생활기상지수/보건기상지수 — 실측 검증 완료(2026-07-01, 실제 authKey 호출 성공).
서비스명은 V4가 아니라 V3/V2이며, apihub.kma.go.kr에 동일 authKey로 미러링되어 있음
(처음에 LivingWthrIdxServiceV4/HealthWthrIdxServiceV2로 잘못 추정해 404를 받았던
것은 버전 번호 오류였음 — 실제로는 LivingWthrIdxServiceV3):
- 자외선지수: LivingWthrIdxServiceV3/getUVIdxV3
- 대기정체지수: LivingWthrIdxServiceV3/getAirDiffusionIdxV3
- 꽃가루농도위험지수: HealthWthrIdxServiceV2/getOakPollenRiskIdxV2(참나무)/
  getPinePollenRiskIdxV2(소나무)/getWeedsPollenRiskndxV2(잡초류)
- areaNo(지역코드)는 표준 행정구역코드와 다름 — 강원/전북은 2023~2024년 특별자치도
  개편 이후 코드(51/52)를 쓴다(표준코드 42/45로는 검색결과 없음). const.py의
  LAND_ZONE_TO_AREA_NO 12개 전부 실측 검증함.
- 대상환경별 체감온도(getSenTaIdxV3, 대상=노인/어린이/농촌/비닐하우스/취약거주환경/
  도로/건설현장/조선소)는 문서상 "~'26.5.10." 종료 표시가 있고 실제로도 계속
  NO_DATA만 응답하여(2026-07-01 확인) 서비스 종료로 추정, 미구현.
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


@dataclass(frozen=True)
class Pm10Observation:
    """PM10(미세먼지) 관측값 (kma_pm10.php). [실측 검증 2026-07-01]

    5분 간격 관측. 원시 컬럼(쉼표구분, 트레일링 '='): TM,STN,PM10,FLAG,MQC,=
    """

    stn: str
    tm: str
    pm10: float | None   # PM10 농도 (㎍/㎥)
    raw: str


@dataclass(frozen=True)
class UVIndexForecast:
    """자외선지수 예보 (LivingWthrIdxServiceV3/getUVIdxV3). [실측 검증 2026-07-01]

    3시간 간격 예보(h0~h75, 매일 06/18시 발표). current는 가장 이른 예측 슬롯 값.
    """

    area_no: str
    date: str
    current: float | None
    hourly: dict[str, str]  # 원시 h0,h3,h6... 슬롯(문자열, 빈 값 포함)


@dataclass(frozen=True)
class AirStagnationForecast:
    """대기정체지수 예보 (LivingWthrIdxServiceV3/getAirDiffusionIdxV3). [실측 검증 2026-07-01]

    지수값은 25/50/75/100 중 하나로 이미 등급화되어 있다(낮음/보통/높음/매우높음).
    """

    area_no: str
    date: str
    current: float | None
    hourly: dict[str, str]


@dataclass(frozen=True)
class PollenRiskForecast:
    """꽃가루농도위험지수 예보 (HealthWthrIdxServiceV2). [실측 검증 2026-07-01]

    지수값 0~3 = 낮음/보통/높음/매우높음. 서비스 기간(참나무·소나무 3~6월,
    잡초류 8~10월) 외에는 NODATA로 응답 — 정상 동작(계절적 공백).
    """

    area_no: str
    date: str
    today: float | None
    tomorrow: float | None
    day_after_tomorrow: float | None


@dataclass(frozen=True)
class RadarPrecipitation:
    """행정구역별 레이더합성장 조회 (WthrRadarInfoService/getCompCappiQcdArea).

    [실측 검증 2026-07-01] value는 dBZ(반사도) 단위. 레이더 관측영역 밖이거나
    에코 미탐지 시 -250.0(문서 기준 무에코 센티널) 근방 값이 나온다.
    """

    dong_code: str
    date_time: str
    lon: float | None
    lat: float | None
    unit: str | None
    value: float | None


@dataclass(frozen=True)
class SatelliteFileInfo:
    """위성(GK2A) 산출물 파일 목록 1건. [활용신청 필요 — 미검증]"""

    filename: str
    tm: str | None
    raw: str


@dataclass(frozen=True)
class ImageBinary:
    """레이더/위성 바이너리 이미지 응답 공통 래퍼."""

    data: bytes
    content_type: str
    filename: str | None = None


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


def _hourly_current(item: dict[str, Any]) -> float | None:
    """h0,h3,h6,... 3시간 간격 예보 슬롯 중 값이 있는 가장 이른 것을 '현재값'으로 취급.

    getUVIdxV3/getAirDiffusionIdxV3 응답이 이 형태(h0~h75 또는 h3~h78, 빈 문자열 포함)이다.
    """
    for h in range(0, 100, 3):
        val = item.get(f"h{h}")
        if val not in (None, ""):
            return _to_float(val)
    return None


def _parse_pm10_line(line: str) -> Pm10Observation | None:
    """kma_pm10.php 원시 라인(쉼표구분, 트레일링 '=') 1건을 파싱.

    포맷: "TM, STN, PM10, FLAG, MQC, =". 필드가 3개 미만이면 None.
    """
    parts = [p.strip() for p in line.split(",")]
    if parts and parts[-1] == "=":
        parts = parts[:-1]
    if len(parts) < 3:
        return None
    tm, stn_id, pm10_raw = parts[0], parts[1], parts[2]
    return Pm10Observation(stn=stn_id, tm=tm, pm10=_to_float(pm10_raw), raw=line)


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

    NODATA(03/04)는 빈 리스트. 생활/보건기상지수 API는 서비스 기간이 아니거나
    지역코드에 해당 자료가 없을 때 99(커스텀 메시지)를 쓰므로 이 역시 NODATA로 취급.
    인증/기타 오류는 예외.
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
        if code in ("03", "04", "99"):
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

    async def _do_request(
        self, endpoint: str, params: dict[str, Any]
    ) -> tuple[bytes, int, str]:
        """공통 HTTP GET 수행. (raw_bytes, status, content_type)을 그대로 반환.

        디코딩/오류 변환은 호출자(_request/_request_binary)의 몫이다.
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
                return raw, resp.status, (resp.content_type or "")
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise KmaApiError(f"{endpoint}: 연결 오류: {err}") from err

    async def _request_binary(
        self, endpoint: str, params: dict[str, Any]
    ) -> tuple[bytes, str]:
        """바이너리(PNG 등) 응답을 반환. (raw_bytes, content_type).

        오류 응답(403/기타)은 typ01 텍스트 API와 동일하게 JSON(UTF-8) 본문으로
        온다고 가정하고 감지하여 예외로 변환한다. [미검증: 실제 신호 방식 확인 필요]
        """
        raw, status, content_type = await self._do_request(endpoint, params)
        if "json" in content_type:
            body_str = raw.decode("utf-8", errors="replace")
            _raise_for_error_payload(status, body_str, endpoint)
        if status != 200:
            raise KmaApiError(f"{endpoint}: HTTP {status}")
        return raw, content_type

    async def _request(
        self, endpoint: str, params: dict[str, Any], *, is_json_api: bool = False
    ) -> str:
        """엔드포인트를 호출하고 디코딩된 텍스트를 반환.

        endpoint 예: "fct_shrt_reg.php". authKey는 자동 부착.
        오류 응답(403/인증 등)은 예외로 변환.
        """
        raw, status, content_type = await self._do_request(endpoint, params)

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

    # -- PM10(미세먼지) ------------------------------------------------------

    async def async_get_pm10_now(
        self,
        *,
        stn: str | int,
        tm1: str | None = None,
        tm2: str | None = None,
    ) -> Pm10Observation | None:
        """PM10(미세먼지) 관측 조회 (kma_pm10.php). [실측 검증 2026-07-01]

        5분 간격 관측. tm1~tm2 없으면 최근 30분 구간을 조회해 가장 최신(마지막) 레코드를 반환.
        원시 라인 포맷: "TM, STN, PM10, FLAG, MQC, =" (쉼표구분, 트레일링 '=').
        """
        now = _now_kst()
        tm2 = tm2 or now.strftime("%Y%m%d%H%M")
        tm1 = tm1 or (now - datetime.timedelta(minutes=30)).strftime("%Y%m%d%H%M")

        text = await self._request(
            "kma_pm10.php", {"tm1": tm1, "tm2": tm2, "stn": stn}
        )
        lines = list(iter_data_lines(text))
        if not lines:
            return None
        return _parse_pm10_line(lines[-1])

    # -- 생활기상지수/보건기상지수 ---------------------------------------------

    async def async_get_uv_index(
        self, *, area_no: str, time: str | None = None
    ) -> UVIndexForecast | None:
        """자외선지수 조회 (LivingWthrIdxServiceV3/getUVIdxV3). [실측 검증 2026-07-01]

        매일 06/18시 발표, 3시간 간격 예보(h0~h75).
        """
        time = time or _now_kst().strftime("%Y%m%d%H")
        text = await self._request(
            "api/typ02/openApi/LivingWthrIdxServiceV3/getUVIdxV3",
            {
                "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
                "areaNo": area_no, "time": time,
            },
            is_json_api=True,
        )
        items = _parse_typ02_items(text, "getUVIdxV3")
        if not items:
            return None
        item = items[0]
        hourly = {k: v for k, v in item.items() if k.startswith("h")}
        return UVIndexForecast(
            area_no=area_no, date=item.get("date", ""),
            current=_hourly_current(item), hourly=hourly,
        )

    async def async_get_air_stagnation_index(
        self, *, area_no: str, time: str | None = None
    ) -> AirStagnationForecast | None:
        """대기정체지수 조회 (LivingWthrIdxServiceV3/getAirDiffusionIdxV3). [실측 검증 2026-07-01]

        매일 06/18시 발표, 3시간 간격 예보(h3~h78 등). 지수값은 25/50/75/100 중 하나.
        """
        time = time or _now_kst().strftime("%Y%m%d%H")
        text = await self._request(
            "api/typ02/openApi/LivingWthrIdxServiceV3/getAirDiffusionIdxV3",
            {
                "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
                "areaNo": area_no, "time": time,
            },
            is_json_api=True,
        )
        items = _parse_typ02_items(text, "getAirDiffusionIdxV3")
        if not items:
            return None
        item = items[0]
        hourly = {k: v for k, v in item.items() if k.startswith("h")}
        return AirStagnationForecast(
            area_no=area_no, date=item.get("date", ""),
            current=_hourly_current(item), hourly=hourly,
        )

    async def _async_get_pollen_risk(
        self, operation: str, *, area_no: str, time: str | None = None
    ) -> PollenRiskForecast | None:
        """꽃가루농도위험지수 공통 조회 (HealthWthrIdxServiceV2). [실측 검증 2026-07-01]

        일 2회(06/18시) 발표. 서비스 기간 외에는 NODATA(resultCode 99, 정상 동작).
        """
        time = time or _now_kst().strftime("%Y%m%d%H")
        text = await self._request(
            f"api/typ02/openApi/HealthWthrIdxServiceV2/{operation}",
            {
                "numOfRows": 10, "pageNo": 1, "dataType": "JSON",
                "areaNo": area_no, "time": time,
            },
            is_json_api=True,
        )
        items = _parse_typ02_items(text, operation)
        if not items:
            return None
        item = items[0]
        return PollenRiskForecast(
            area_no=area_no,
            date=item.get("date", ""),
            today=_to_float(item.get("today")),
            tomorrow=_to_float(item.get("tomorrow")),
            day_after_tomorrow=_to_float(item.get("todayaftertomorrow")),
        )

    async def async_get_oak_pollen_risk(
        self, *, area_no: str, time: str | None = None
    ) -> PollenRiskForecast | None:
        """꽃가루농도위험지수(참나무) 조회 (getOakPollenRiskIdxV2). 서비스 기간: 3~6월."""
        return await self._async_get_pollen_risk(
            "getOakPollenRiskIdxV2", area_no=area_no, time=time
        )

    async def async_get_pine_pollen_risk(
        self, *, area_no: str, time: str | None = None
    ) -> PollenRiskForecast | None:
        """꽃가루농도위험지수(소나무) 조회 (getPinePollenRiskIdxV2). 서비스 기간: 3~6월."""
        return await self._async_get_pollen_risk(
            "getPinePollenRiskIdxV2", area_no=area_no, time=time
        )

    async def async_get_weed_pollen_risk(
        self, *, area_no: str, time: str | None = None
    ) -> PollenRiskForecast | None:
        """꽃가루농도위험지수(잡초류) 조회 (getWeedsPollenRiskndxV2). 서비스 기간: 8~10월.

        엔드포인트명의 "Riskndx"는 오타가 아니라 기상청 API의 실제 표기(원본 유지).
        """
        return await self._async_get_pollen_risk(
            "getWeedsPollenRiskndxV2", area_no=area_no, time=time
        )

    # -- 레이더(행정구역별) / 위성 이미지 ---------------------------------------

    async def async_get_radar_precipitation(
        self,
        *,
        dong_code: str,
        date_time: str | None = None,
        comp_type: str = "CPP",
        data_type_cd: str = "RN",
    ) -> RadarPrecipitation | None:
        """행정구역별 레이더합성장 조회 (WthrRadarInfoService/getCompCappiQcdArea). [실측 검증 2026-07-01]

        레이더 원시 반사도 격자(nph-rdr_cmp1_api)는 PNG가 아니라 수백만 셀의 raw
        데이터 덤프라 이미지로 쓸 수 없어, 대신 행정구역 단위로 값 하나를 받는
        이 API를 사용한다. dateTime은 5분 간격(최근 2일 이내만 조회 가능).

        실측 결과 최신 시각은 아직 게시되지 않아 NODATA가 되므로(2026-07-01 확인,
        22:35 실패/22:30 성공 — 약 20분 지연), 기본값은 25분 전을 5분 단위로
        내림(round down)한 시각을 사용한다.
        """
        if date_time is None:
            backoff = _now_kst() - datetime.timedelta(minutes=25)
            rounded = backoff - datetime.timedelta(
                minutes=backoff.minute % 5, seconds=backoff.second, microseconds=backoff.microsecond
            )
            date_time = rounded.strftime("%Y%m%d%H%M")
        text = await self._request(
            "api/typ02/openApi/WthrRadarInfoService/getCompCappiQcdArea",
            {
                "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
                "dateTime": date_time, "compType": comp_type,
                "dataTypeCd": data_type_cd, "dongCode": dong_code,
            },
            is_json_api=True,
        )
        items = _parse_typ02_items(text, "getCompCappiQcdArea")
        if not items:
            return None
        item = items[0]
        return RadarPrecipitation(
            dong_code=dong_code,
            date_time=item.get("dateTime", date_time),
            lon=_to_float(item.get("lon")),
            lat=_to_float(item.get("lat")),
            unit=item.get("unit"),
            value=_to_float(item.get("value")),
        )

    async def async_get_satellite_file_list(
        self, *, tm: str | None = None, channel: str | None = None
    ) -> list[SatelliteFileInfo]:
        """위성(GK2A) 산출물 파일 목록 조회 (sat_file_list.php). [활용신청 필요 — 미검증]

        TODO: 활용신청 후 실제 파라미터/응답 포맷 확정. rdr_cmp_file_list.php와 같은
        "url" 계열 텍스트 API라 쉼표구분 포맷일 가능성이 높아 그 형식으로 우선 파싱한다.
        """
        text = await self._request(
            "sat_file_list.php", {"tm": tm, "channel": channel}
        )
        out: list[SatelliteFileInfo] = []
        for line in iter_data_lines(text):
            parts = [p.strip() for p in line.split(",")]
            if parts and parts[-1] == "=":
                parts = parts[:-1]
            if not parts or not parts[0]:
                continue
            out.append(SatelliteFileInfo(filename=parts[0], tm=tm, raw=line))
        return out

    async def async_get_satellite_image(
        self, *, tm: str | None = None, obs: str = "vi006", map: str = "HB"
    ) -> ImageBinary:
        """위성(GK2A) 분포도 이미지 조회 (nph-gk2a_img). [활용신청 필요 — 미검증]

        TODO: 2026-07-01 기준 이 경로는 404(유효하지 않은 API)를 반환 — 정확한
        엔드포인트명/파라미터는 활용신청 후(혹은 apihub 문서 재확인 후) 확정 필요.
        """
        tm = tm or _now_kst().strftime("%Y%m%d%H%M")
        raw, content_type = await self._request_binary(
            "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-gk2a_img",
            {"tm": tm, "obs": obs, "map": map},
        )
        return ImageBinary(data=raw, content_type=content_type or "image/png", filename=None)

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
