"""기상청(KMA) 통합 구성요소 상수 정의."""

DOMAIN = "kma"

# 허브 단위 활용신청 상태(binary_sensor.activation_*)/에러 카운트(sensor.error_count_*)
# 진단 센서를 자동 생성하는 데 쓰는 단일 소스. 새 API를 추가할 때 이 목록에만
# key를 추가하면(+해당 코디네이터의 _async_update_data에서 status 딕셔너리에
# 같은 key로 "ok"/"not_applied"/"error: ..."를 채우면) binary_sensor.py와
# sensor.py가 활용신청 상태/에러 카운트 센서를 자동으로 만들어 준다
# (coordinator.py의 _ApiStatusMixin 참고). translations(entity.binary_sensor.
# activation_<key>, entity.sensor.error_count_<key>)에 이름만 추가하면 된다.
#
# Zone별 예·특보/생활기상지수 API — KmaForecastCoordinator가 관리.
API_STATUS_ZONE_KEYS = [
    "village_forecast", "land_forecast", "marine_forecast", "warning_now", "pm10",
    "uv_index", "air_stagnation", "oak_pollen", "pine_pollen", "weed_pollen",
    "radar_precipitation", "sfc_observation", "heat_wave_risk", "cold_wave_risk",
    "hazard_info", "weather_commentary", "snow_depth", "pm10_hourly",
]

# 허브 단위(Zone 무관, 전국 단일 세트) 레이더/위성 이미지 API — KmaImageCoordinator가 관리.
API_STATUS_IMAGE_KEYS = [
    "radar", "satellite", "precipitation_forecast",
    "satellite_visible", "satellite_shortwave_ir", "satellite_water_vapor",
    "dust_satellite",
]

# 허브 단위(Zone 무관, 전국 단일 세트) 비-이미지 데이터 API — KmaHubCoordinator가 관리.
API_STATUS_HUB_KEYS = ["earthquake", "typhoon"]

# 대표 육상 예보구역 위경도 좌표 테이블
# 포맷: { "대표예보구역코드": (위도, 경도) }
REPRESENTATIVE_LAND_ZONES = {
    "11B10101": (37.5665, 126.9780),  # 서울
    "11B20201": (37.4563, 126.7052),  # 인천
    "11B20601": (37.2636, 127.0286),  # 수원 (경기남부)
    "11D10301": (37.8813, 127.7300),  # 춘천 (강원영서)
    "11D20501": (37.7519, 128.8761),  # 강릉 (강원영동)
    "11C10301": (36.6372, 127.4897),  # 청주 (충북)
    "11C20401": (36.3504, 127.3845),  # 대전 (세종/충남)
    "11F10201": (35.8242, 127.1480),  # 전주 (전북)
    "11F20501": (35.1595, 126.8526),  # 광주 (전남)
    "11H10701": (35.8714, 128.6014),  # 대구 (대구/경북)
    "11H20201": (35.1796, 129.0756),  # 부산 (울산/경남)
    "11G00201": (33.4996, 126.5312),  # 제주
}

# 대표 해상 예보구역 위경도 좌표 테이블
# 포맷: { "대표해상예보구역코드": (위도, 경도) }
REPRESENTATIVE_MARINE_ZONES = {
    "12A10100": (37.50, 125.50),  # 서해북부앞바다
    "12A20100": (36.50, 125.80),  # 서해중부앞바다
    "12A30100": (35.00, 125.50),  # 서해남부앞바다
    "12B20100": (34.80, 128.80),  # 남해동부앞바다
    "12B10100": (34.20, 126.80),  # 남해서부앞바다
    "12C20100": (35.80, 129.80),  # 동해남부앞바다
    "12C10100": (37.80, 129.50),  # 동해중부앞바다
    "12D00000": (33.00, 126.50),  # 제주도해상
}

# PM10(미세먼지) 관측지점 매핑 (REPRESENTATIVE_LAND_ZONES와 1:1 대응).
# 주의: 일반 ASOS 지점번호가 아니라 kma_pm10.php가 실제로 서비스하는 PM10 전용
# 관측망(stn_pm10_inf.php로 조회되는 지점 목록) 중 각 대표구역과 가장 가까운 지점.
# 실측 검증 2026-07-01: 아래 모든 지점이 실제 authKey로 정상 응답을 반환함을 확인.
# (11B20201/11B20601/11D10301/11F10201/11F20501/11H10701은 KMA FCT_ID 완전 일치,
#  나머지는 PM10 관측망 내 최근접 지점으로 대체 — 해당 권역에 정확히 일치하는
#  지점이 없음. 특히 11C10301/11C20401은 둘 다 천안(232)으로 수렴함.)
LAND_ZONE_TO_PM10_STN: dict[str, int] = {
    "11B10101": 108,  # 서울 (FCT_ID 일치, 1.2km)
    "11B20201": 201,  # 인천 → 강화 (FCT_ID 일치, 36km)
    "11B20601": 119,  # 수원 (FCT_ID 일치, 4.0km)
    "11D10301": 93,   # 춘천 → 북춘천 (FCT_ID 일치, 7.7km)
    "11D20501": 100,  # 강릉 → 대관령 (최근접, 16.2km)
    "11C10301": 232,  # 청주 → 천안 (최근접, 22.4km)
    "11C20401": 232,  # 대전 → 천안 (최근접, 46.5km)
    "11F10201": 146,  # 전주 (FCT_ID 일치, 0.7km)
    "11F20501": 156,  # 광주 (FCT_ID 일치, 3.8km)
    "11H10701": 143,  # 대구 (FCT_ID 일치, 2.2km)
    "11H20201": 160,  # 부산 → 구덕산 (최근접, 9.6km)
    "11G00201": 185,  # 제주 → 고산 (최근접, 41.1km)
}

# PM10/적설관측/미세먼지 시간통계(kma_pm10.php, kma_snow1.php, dst_pm10_hr.php)가
# 공유하는 관측지점(stn) 번호 → 지점명. LAND_ZONE_TO_PM10_STN 주석에서 추출.
PM10_STN_NAMES: dict[int, str] = {
    108: "서울",
    201: "강화",
    119: "수원",
    93: "북춘천",
    100: "대관령",
    232: "천안",
    146: "전주",
    156: "광주",
    143: "대구",
    160: "구덕산",
    185: "고산",
}

# PM10(미세먼지) 등급 기준 (환경부 기준, ㎍/㎥)
PM10_GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (30, "good"),
    (80, "moderate"),
    (150, "unhealthy"),
]
PM10_GRADE_VERY_UNHEALTHY = "very_unhealthy"  # 151 이상

# 생활기상지수(LivingWthrIdxServiceV3)/보건기상지수(HealthWthrIdxServiceV2)용 지역코드(areaNo).
# REPRESENTATIVE_LAND_ZONES와 1:1 대응. 공식 "행정구역코드정보" 자료(기상청 API허브 제공,
# 최종 업데이트 2026-07-01)와 실제 authKey 호출로 12개 전체 교차 검증함(2026-07-01).
# 가능한 곳은 시/군 단위(더 정밀)로, 시/군 코드가 없는 광역시는 시도 단위를 쓴다.
LAND_ZONE_TO_AREA_NO: dict[str, str] = {
    "11B10101": "1100000000",  # 서울특별시
    "11B20201": "2800000000",  # 인천광역시
    "11B20601": "4111100000",  # 경기도 수원시장안구
    "11D10301": "5111000000",  # 강원특별자치도 춘천시 — 표준코드 42가 아니라 51
    "11D20501": "5115000000",  # 강원특별자치도 강릉시 — 표준코드 42가 아니라 51
    "11C10301": "4311100000",  # 충청북도 청주시상당구
    "11C20401": "3000000000",  # 대전광역시
    "11F10201": "5211100000",  # 전북특별자치도 전주시완산구 — 표준코드 45가 아니라 52
    "11F20501": "2900000000",  # 광주광역시(구코드). 2026년 "전남광주통합특별시"(1200000000)로
                                # 개편되었으나 이 API는 아직 신코드를 인식하지 못해(2026-07-01
                                # 확인, 신코드 조회 시 99/검색결과없음) 구코드를 그대로 사용한다.
                                # API가 갱신되면 재확인 필요.
    "11H10701": "2700000000",  # 대구광역시
    "11H20201": "2600000000",  # 부산광역시
    "11G00201": "5000000000",  # 제주특별자치도
}

# 자외선지수(getUVIdxV3) 등급 기준 (WHO/기상청 표준 UV Index 스케일)
UV_INDEX_GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (2, "low"),
    (5, "moderate"),
    (7, "high"),
    (10, "very_high"),
]
UV_INDEX_GRADE_EXTREME = "extreme"  # 11 이상

# 대기정체지수(getAirDiffusionIdxV3) 등급 기준 — 지수값 자체가 25/50/75/100 중 하나로 이미 등급화됨.
AIR_STAGNATION_GRADE_MAP: dict[int, str] = {
    25: "low",
    50: "moderate",
    75: "high",
    100: "very_high",
}

# 꽃가루농도위험지수(HealthWthrIdxServiceV2) 등급 기준 — 지수값 0~3이 그대로 등급.
POLLEN_RISK_GRADE_MAP: dict[int, str] = {
    0: "low",
    1: "moderate",
    2: "high",
    3: "very_high",
}

# 레이더 강수강도(dBZ) 등급 기준. 0 이하는 무에코/관측범위밖 센티널(-250 근방)을 포함해
# "강수없음"으로 묶는다.
RADAR_PRECIPITATION_GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (0, "no_rain"),
    (20, "very_light"),
    (30, "light"),
    (40, "moderate"),
    (50, "heavy"),
]
RADAR_PRECIPITATION_GRADE_VERY_HEAVY = "very_heavy"  # 50 초과


# 지방기상청 관서코드(STN) — 영향예보(ifs_fct_pstt.php)/기상정보(wrn_inf_rpt.php)/
# 날씨해설(wthr_cmt_rpt.php)에서 쓰는 지역 단위. REPRESENTATIVE_LAND_ZONES와 1:1 대응.
# 실측 검증 2026-07-02: ifs_fct_pstt.php(폭염) 전체 조회 결과에서 실제로 등장한 STN
# 값(105/109/131/133/143/146/159)과 wrn_inf_rpt.php 사례(STN=109→경기북부, STN=156→
# 광주전남)를 근거로 9개 지방기상청(서울/강원/청주/대전/전주/광주/대구/부산/제주)
# 체계로 매핑함. 일반 ASOS 지점번호(108 등)와는 다른 별도 코드 체계이므로 주의.
LAND_ZONE_TO_OFFICE_STN: dict[str, int] = {
    "11B10101": 109,  # 서울 (서울지방기상청)
    "11B20201": 109,  # 인천 (서울지방기상청 관할)
    "11B20601": 109,  # 수원 (서울지방기상청 관할)
    "11D10301": 105,  # 춘천 (강원지방기상청)
    "11D20501": 105,  # 강릉 (강원지방기상청)
    "11C10301": 131,  # 청주 (청주기상지청)
    "11C20401": 133,  # 대전 (대전지방기상청)
    "11F10201": 146,  # 전주 (전주지방기상청)
    "11F20501": 156,  # 광주 (광주지방기상청)
    "11H10701": 143,  # 대구 (대구지방기상청)
    "11H20201": 159,  # 부산 (부산지방기상청)
    "11G00201": 184,  # 제주 (제주지방기상청)
}

# 영향예보(ifs_fct_pstt.php)/기상정보(wrn_inf_rpt.php)/날씨해설(wthr_cmt_rpt.php)가
# 공유하는 관서(stn) 코드 → 관서명. LAND_ZONE_TO_OFFICE_STN 주석에서 추출.
OFFICE_STN_NAMES: dict[int, str] = {
    109: "서울지방기상청",
    105: "강원지방기상청",
    131: "청주기상지청",
    133: "대전지방기상청",
    146: "전주지방기상청",
    156: "광주지방기상청",
    143: "대구지방기상청",
    159: "부산지방기상청",
    184: "제주지방기상청",
}

# 영향예보(ifs_fct_pstt.php) 위험수준(ILVL) 등급 기준 — 0~4가 그대로 등급.
IMPACT_RISK_GRADE_MAP: dict[int, str] = {
    0: "none",
    1: "concern",
    2: "caution",
    3: "warning",
    4: "danger",
}

# 광역 매핑 기반 특보 필터링용 키워드 사전
PROVINCE_WARNING_KEYWORDS = {
    "11B10101": ["서울", "인천", "경기"],
    "11B20201": ["인천", "경기", "서울"],
    "11B20601": ["경기", "인천", "서울"],
    "11D10301": ["강원"],
    "11D20501": ["강원"],
    "11C10301": ["충북", "충청"],
    "11C20401": ["대전", "세종", "충남", "충청"],
    "11F10201": ["전북", "전라"],
    "11F20501": ["광주", "전남", "전라"],
    "11H10701": ["대구", "경북", "경상"],
    "11H20201": ["부산", "울산", "경남", "경상"],
    "11G00201": ["제주"],
}
