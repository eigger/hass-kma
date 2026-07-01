# 기상청 APIhub 연동 홈어시스턴트 통합 구성요소 (hass-kma)

[![GitHub Release](https://img.shields.io/github/v/release/eigger/hass-kma?style=flat-square)](https://github.com/eigger/hass-kma/releases)
[![License](https://img.shields.io/github/license/eigger/hass-kma?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&query=%24.kma.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)

기상청 APIhub(apihub.kma.go.kr) 공식 텍스트 및 개방형 API를 연동하여 홈어시스턴트(Home Assistant)에 실시간 기상 상태, 상세 관측값, 중단기 예보, 생활기상지수·미세먼지·자외선지수·대기정체지수·꽃가루위험지수 및 재난 기상특보 경보를 연동해 주는 통합 구성요소입니다.

---

## 🌟 주요 기능

*   **표준 날씨 엔티티 (`weather.kma_*`)**:
    *   현재 날씨 상태 및 대기 지표(기온, 습도, 풍향, 풍속 등).
    *   **시간별 예보 (Hourly)**: 향후 3일간의 시간별 동네예보 상세 수집.
    *   **일별 예보 (Daily)**: 3일간의 상세 동네예보 자료를 일일 단위로 집계하고, 4~10일차 중기 예보는 육상예보(`fct_afs_dl`)와 유기적으로 병합하여 최대 10일간의 연속된 일별 예보를 생성합니다.
    *   **예보 요약 연동**: 한국어 예보 요약 문구(`land_forecast_summary`, `marine_forecast_summary`) 및 발효된 기상특보 목록을 엔티티 속성으로 함께 제공합니다.
*   **상세 예보 센서 (`sensor.kma_*`)**:
    *   기온, 습도, 풍속, 강수확률, 1시간 강수량 실시간 수집.
    *   글로 표기되는 **육상 예보 요약** 및 **해상 예보 요약** 센서를 제공하여 대시보드 가독성을 극대화합니다.
    *   오늘의 기온 극값인 **오늘 최저기온** 및 **오늘 최고기온** 센서.
    *   향후 24시간 이내 강수 소식을 감시하는 **비/눈 예보 탐색** 센서 (속성에서 예상 시간, 강수 형태 코드, 강수 확률 및 강수량과 더불어 3시간/6시간/12시간 이내 강수 예보 여부인 `rain_expected_3h`, `rain_expected_6h`, `rain_expected_12h` 제공).
    *   **한 줄 기상 요약 (One-line Weather Summary)**: 현재 기상 상태, 기온, 오늘의 최저/최고 기온 및 가장 가까운 강수 예보를 종합한 간결한 텍스트 문자열 제공 (전자라벨/E-Paper 디스플레이 연동에 최적화).
    *   기상청 데이터를 바탕으로 자동 연산되는 지수 센서:
        *   **체감온도 (Apparent Temperature)**: 기온, 습도, 풍속 데이터를 바탕으로 Steadman 공식을 사용하여 실시간 계산.
        *   **이슬점 (Dew Point)**: 기온, 습도 데이터를 바탕으로 Magnus-Tetens 공식을 사용하여 실시간 계산.
        *   **불쾌지수 (Discomfort Index)**: 기온, 습도 데이터를 바탕으로 실시간 계산. 등급은 별도 엔티티(`discomfort_grade`)로 제공됩니다: `낮음(Low)`, `보통(Normal)`, `높음(High)`, `매우높음(Very High)`.
*   **생활기상지수 4종 센서**:
    *   기상 정보와 각 지수별 계산 공식을 결합하여, 0~100 수치 센서와 함께 등급을 나타내는 전용 ENUM 센서(`*_grade`)를 짝으로 제공합니다. 등급 센서는 홈어시스턴트 시스템 언어에 맞춰 상태값이 자동 번역됩니다.
        *   **빨래 건조 지수 (Laundry Index / `laundry_grade`)**: 기온, 습도, 풍속, 하늘 상태 및 강수 예보를 종합하여 계산. 등급: 매우 좋음/좋음/보통/비추천.
        *   **세차 지수 (Car Wash Index / `car_wash_grade`)**: 향후 72시간 이내 비/눈 예보 상황을 스캔하여 세차 적합성 판별. 등급: 매우 좋음/보류 권장/세차 비추/세차 금지.
        *   **동파 가능 지수 (Freeze Risk Index / `freeze_risk_grade`)**: 향후 48시간 이내 최저 예보 기온을 바탕으로 동파 가능 단계 구분. 등급: 낮음/보통/높음/매우 높음.
        *   **식중독 지수 (Food Poisoning Index / `food_poisoning_grade`)**: 기온과 상대습도를 이용한 식중독 예측 공식을 근사화하여 연산. 등급: 관심/주의/경고/위험.
*   **미세먼지(PM10) 센서** ✅ 실제 authKey로 동작 검증 완료(2026-07-01):
    *   기상청 API허브 지상관측 PM10 관측자료(`kma_pm10.php`, 5분 간격)를 이용해 지역에서 가장 가까운 PM10 관측지점의 미세먼지 농도를 수집합니다.
    *   농도값(`pm10`, ㎍/㎥)과 환경부 기준 등급을 나타내는 전용 ENUM 센서(`pm10_grade`: 좋음/보통/나쁨/매우나쁨)를 함께 제공합니다.
*   **자외선지수 / 대기정체지수 / 꽃가루농도위험지수** ✅ 실제 authKey로 동작 검증 완료(2026-07-01):
    *   기상청 생활기상지수(`LivingWthrIdxServiceV3`)·보건기상지수(`HealthWthrIdxServiceV2`) API를 이용하며, 기존 authKey 그대로 사용합니다(가능한 곳은 시/군 단위 지역코드로 조회해 정밀도를 높였습니다).
    *   **자외선지수 (`uv_index` / `uv_index_grade`)**: 3시간 간격 예보, WHO/기상청 표준 등급(낮음/보통/높음/매우높음/위험).
    *   **대기정체지수 (`air_stagnation_index` / `air_stagnation_grade`)**: 3시간 간격 예보, 지수값(25/50/75/100)이 그대로 등급(낮음/보통/높음/매우높음)에 대응됩니다.
    *   **꽃가루농도위험지수 (참나무/소나무/잡초류, `oak_pollen_risk`/`pine_pollen_risk`/`weed_pollen_risk` + `*_grade`)**: 일 2회(06/18시) 예보, 오늘/내일/모레 값 제공. 참나무·소나무는 3~6월, 잡초류는 8~10월에만 데이터가 있으며, 그 외 기간에는 정상적으로 "데이터 없음" 상태가 됩니다(이전 값을 이어붙이지 않습니다).
    *   ⚠️ "대상환경별 체감온도"(`getSenTaIdxV3`)는 검토했으나 기상청 문서에 서비스 종료 표시(~2026-05-10)가 있고 실제로도 계속 데이터 없음으로 응답해 구현하지 않았습니다.
*   **레이더 강수강도 (`sensor.kma_<지역>_radar_precipitation`)** ✅ 실제 authKey로 동작 검증 완료(2026-07-01):
    *   레이더 합성영상 이미지(`nph-rdr_cmp1_api`)는 활용신청 후 실제로 받아보니 PNG가 아니라 **수백만 셀짜리 원시 반사도(dBZ) 격자 데이터**였습니다 — 화면에 표시하려면 색상표를 입혀 직접 렌더링해야 하는 수준이라 이미지 엔티티로는 적합하지 않다고 판단했습니다.
    *   대신 행정구역별로 값 하나만 주는 `WthrRadarInfoService/getCompCappiQcdArea`를 사용해, Zone별 레이더 반사도(dBZ) 숫자 센서로 제공합니다.
    *   ⚠️ 특정 지역(광주)은 2026년 행정구역 통합으로 대체된 구코드를 여전히 쓰고 있어 간헐적으로 오류가 발생할 수 있습니다 — 실패 시 이전 값을 유지합니다.
*   **위성 이미지 (`image.kma_satellite_image`)**:
    *   천리안위성(GK2A) 산출물을 최신 스냅샷 이미지로 제공합니다 (허브 단위 엔티티, Zone과 무관).
    *   약 10분 주기로 갱신되며, 대시보드의 Picture Entity 카드 등으로 바로 표시할 수 있습니다.
    *   ⚠️ 파일목록 API는 활용신청이 반영되었으나, 정확한 산출물 코드(`vars`) 체계를 아직 확인하지 못해 실제 이미지 다운로드는 미검증 상태입니다.
*   **재난 기상특보 안전 센서 (`binary_sensor.kma_*_warning`)**:
    *   선택된 거주 지역(광역자치단체 기준)에 기상 특보(호우, 대설, 강풍, 폭염, 한파, 태풍, 황사 등)가 발효되면 즉시 `on` 상태가 됩니다.
    *   발효된 특보의 개수, 특보 명칭(예: 폭염주의보, 호우경보 등), 발효 시간 및 상세 목록을 속성 값으로 지연 없이 노출합니다 (홈어시스턴트의 시스템 언어 설정에 맞춰 다국어 이름/등급 제공).
*   **간편한 설정 흐름 (Config Flow & Options Flow)**:
    *   홈어시스턴트에 등록된 지역 엔티티(`zone.*`)를 선택하면, 자동으로 위경도를 추출해 **기상청 격자좌표(nx, ny) 및 최적의 육상/해상 예보구역을 자동 매핑**합니다.
    *   데이터 갱신 주기(기본 10분, 최소 5분 ~ 최대 180분)를 설정 화면에서 실시간으로 변경 가능합니다.

---

## 📋 센서 목록

| 기기 | 센서 ID | 센서 이름 | 사용 API / 계산 공식 | 갱신 주기 |
| --- | --- | --- | --- | --- |
| 기상청 날씨 | `weather.kma_<지역>` | 날씨 (Weather) | 동네예보 (`getVilageFcst`) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_temperature` | 기온 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_humidity` | 습도 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_wind_speed` | 풍속 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pop` | 강수확률 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pcp` | 1시간 강수량 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_temp_min` | 오늘 최저기온 | 동네예보 24시간 극값 스캔 | 매시간 |
| 기상청 날씨 | `sensor.kma_<지역>_temp_max` | 오늘 최고기온 | 동네예보 24시간 극값 스캔 | 매시간 |
| 기상청 날씨 | `sensor.kma_<지역>_precipitation_forecast` | 비/눈 예보 탐색 | 동네예보 24시간 예보 스캔 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_apparent_temperature` | 체감온도 | Steadman 공식 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_dew_point` | 이슬점 | Magnus-Tetens 공식 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_discomfort_index` | 불쾌지수 | 온도 및 상대습도 기반 연산 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_discomfort_grade` | 불쾌지수 등급 | 불쾌지수 값 기반 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_laundry_index` | 빨래 건조 지수 | 온도, 습도, 풍속, 강수예보 종합 연산 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_laundry_grade` | 빨래 건조 지수 등급 | 빨래 건조 지수 값 기반 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_car_wash_index` | 세차 지수 | 72시간 내 강수 예보 분석 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_car_wash_grade` | 세차 지수 등급 | 세차 지수 값 기반 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_freeze_risk_index` | 동파 가능 지수 | 48시간 내 최저 예보기온 분석 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_freeze_risk_grade` | 동파 가능 지수 등급 | 동파 가능 지수 값 기반 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_food_poisoning_index` | 식중독 지수 | 온도 및 상대습도 기반 예측 연산 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_food_poisoning_grade` | 식중독 지수 등급 | 식중독 지수 값 기반 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_one_line_summary` | 한 줄 기상 요약 | 현재 날씨, 온도 극값, 강수 및 특보 정보 종합 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_land_forecast_summary` | 육상 예보 요약 | 단기육상예보조회 (`fct_afs_dl`) | 매일 5시, 17시 |
| 기상청 날씨 | `sensor.kma_<지역>_marine_forecast_summary` | 해상 예보 요약 | 단기해상예보조회 (`fct_afs_do`) | 매일 5시, 17시 |
| 기상청 날씨 | `sensor.kma_<지역>_pm10` | 미세먼지(PM10) | PM10 관측자료 조회 (`kma_pm10.php`) ✅검증됨 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pm10_grade` | 미세먼지 등급 | PM10 값 기반 환경부 등급 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_uv_index` | 자외선지수 | `LivingWthrIdxServiceV3/getUVIdxV3` ✅검증됨 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_uv_index_grade` | 자외선지수 등급 | UV지수 값 기반 WHO 표준 등급 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_air_stagnation_index` | 대기정체지수 | `LivingWthrIdxServiceV3/getAirDiffusionIdxV3` ✅검증됨 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_air_stagnation_grade` | 대기정체지수 등급 | 지수값(25/50/75/100) 그대로 등급 매핑 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_oak_pollen_risk` | 꽃가루위험지수(참나무) | `HealthWthrIdxServiceV2/getOakPollenRiskIdxV2` ✅검증됨, 서비스기간 3~6월 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_oak_pollen_risk_grade` | 꽃가루위험지수(참나무) 등급 | 지수값(0~3) 그대로 등급 매핑 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pine_pollen_risk` | 꽃가루위험지수(소나무) | `HealthWthrIdxServiceV2/getPinePollenRiskIdxV2` ✅검증됨, 서비스기간 3~6월 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pine_pollen_risk_grade` | 꽃가루위험지수(소나무) 등급 | 지수값(0~3) 그대로 등급 매핑 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_weed_pollen_risk` | 꽃가루위험지수(잡초류) | `HealthWthrIdxServiceV2/getWeedsPollenRiskndxV2` ✅검증됨, 서비스기간 8~10월 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_weed_pollen_risk_grade` | 꽃가루위험지수(잡초류) 등급 | 지수값(0~3) 그대로 등급 매핑 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_radar_precipitation` | 레이더 강수강도 | `WthrRadarInfoService/getCompCappiQcdArea` ✅검증됨 | 10분 |
| 기상청 날씨 | `binary_sensor.kma_<지역>_warning` | 기상특보 안전 센서 | 기상특보현황 (`wrn_now_data`) | 10분 |
| 기상청 APIhub | `image.kma_satellite_image` | 위성(GK2A) 영상 | 위성 산출물 조회 ⚠️정확한 산출물 코드 미확인 | 10분 |

---

## 🔍 주요 센서 상세 정보

### 1. 한 줄 기상 요약 (`one_line_summary`)
전자라벨(ESL), E-Paper 등 제한된 공간을 가진 디스플레이에 기상 상황을 직관적으로 노출하기 위해 설계된 텍스트 센서입니다. 홈어시스턴트의 시스템 언어 설정(`ko`, `en` 등)에 맞춰 동적으로 메시지가 구성됩니다.
*   **출력 예시**:
    *   `맑음, 19.5°C (11.0°C/26.0°C)`
    *   `흐림, 15.0°C (12.0°C/18.0°C), 16시경 비 예보`
    *   `맑음, 29.0°C (20.0°C/31.0°C) [폭염주의보]`

### 2. 생활기상지수 4종 (`laundry`, `car_wash`, `freeze_risk`, `food_poisoning`)
각 지수는 두 개의 엔티티 쌍으로 제공됩니다: 0~100 사이의 수치를 반환하는 `_index` 센서와, 그 수치를 등급으로 분류해 상태값 자체가 홈어시스턴트 언어 설정에 맞춰 자동 번역되는 `_grade` ENUM 센서입니다. 자유 텍스트인 추천 가이드라인(`recommendation`)은 ENUM으로 표현할 수 없어 `_index` 센서의 속성(Attributes)으로 유지됩니다.
*   **빨래 건조 지수**: `laundry_index`(0~100) + `laundry_grade`(매우 좋음/좋음/보통/비추천)
    *   `laundry_index` 속성: `recommendation` (예: `야외 건조를 강력히 추천합니다.`)
*   **세차 지수**: `car_wash_index`(0~100) + `car_wash_grade`(매우 좋음/보류 권장/세차 비추/세차 금지)
    *   `car_wash_index` 속성: `recommendation`
*   **동파 가능 지수**: `freeze_risk_index`(0~100) + `freeze_risk_grade`(낮음/보통/높음/매우 높음)
    *   `freeze_risk_index` 속성: `recommendation`
*   **식중독 지수**: `food_poisoning_index`(0~100) + `food_poisoning_grade`(관심/주의/경고/위험)
    *   `food_poisoning_index` 속성: `recommendation`

### 3. 미세먼지(PM10) 센서 (`pm10`, `pm10_grade`)
기상청 API허브의 지상관측 PM10 관측자료(`kma_pm10.php`, seqApi=2, 5분 간격)를 사용합니다. 별도 서비스 키 없이 기존 기상청 authKey만으로 동작하며, Zone에서 가장 가까운 PM10 관측지점의 값을 가져옵니다. 실제 authKey로 12개 대표 지역 전체 응답을 확인했습니다(2026-07-01).
*   `pm10`: 농도 수치 (㎍/㎥)
*   `pm10_grade`: 환경부 기준 등급 ENUM (좋음 0~30 / 보통 31~80 / 나쁨 81~150 / 매우나쁨 151~)
*   지점 매핑: 서울/인천(강화)/수원/춘천(북춘천)/강릉(대관령)/청주·대전(천안)/전주/광주/대구/부산(구덕산)/제주(고산). PM10 관측망은 일반 ASOS보다 지점 수가 적어, 일부 지역(청주·대전·강릉·부산·제주)은 정확히 일치하는 지점이 없어 가장 가까운 지점으로 대체됩니다 — 특히 청주와 대전은 둘 다 천안 지점 값을 공유합니다.
*   ⚠️ PM2.5(초미세먼지)는 이 API에서 제공되지 않아 범위 밖입니다.

### 4. 레이더 강수강도 (`radar_precipitation`) / 위성 이미지 (`image.kma_satellite_image`)
활용신청 후 레이더 합성영상 API(`nph-rdr_cmp1_api`, seqApi=5)를 실제로 호출해보니 PNG 이미지가 아니라 **2305×2881 셀짜리 원시 dBZ(반사도) 격자 데이터**(ASCII 47MB 또는 바이너리 13MB)였습니다. 문서에도 "disp=A면 dbz*100 정수값 출력"이라고 명시되어 있어, 화면에 표시하려면 이 값들에 색상표를 입혀 직접 렌더링해야 하는데 이건 이미지 API 호출이 아니라 레이더 시각화 엔진을 새로 만드는 수준의 작업이라 이미지 엔티티로 구현하지 않기로 했습니다.
*   대신 같은 문서에 있던 **행정구역별 조회 API**(`WthrRadarInfoService/getCompCappiQcdArea`, typ02/openApi, 같은 authKey)를 사용합니다. Zone의 지역코드(`areaNo`, 위 자외선지수와 동일)만 넘기면 그 지역의 반사도 값 하나(dBZ)를 받을 수 있어, `sensor.kma_<지역>_radar_precipitation`으로 제공합니다.
*   최신 데이터는 약 20분 지연 후 게시됨을 확인해(2026-07-01), 기본 조회 시각을 25분 전으로 설정합니다.
*   ⚠️ 광주(구코드 2900000000 — 2026년 통합특별시 개편으로 대체된 레거시 코드)는 이 API에서 간헐적으로 오류가 발생함을 확인했습니다. 실패 시 이전 값을 유지합니다.
*   위성(GK2A) 이미지는 파일목록 API(`sat_file_list.php`, seqApi=6) 활용신청이 반영되어 403은 해결되었으나, 실제 산출물 코드(`vars=vi006` 등)로 조회하면 "디렉토리가 없습니다"가 나옵니다. GK2A는 기본관측자료(L1B)와 기상산출물(L2)이 분리되어 있는데 정확한 코드 체계를 아직 확인하지 못해 이미지 다운로드는 여전히 미검증 상태입니다.

### 5. 자외선지수 / 대기정체지수 / 꽃가루농도위험지수 (`uv_index`, `air_stagnation_index`, `oak_pollen_risk`, `pine_pollen_risk`, `weed_pollen_risk` + 각 `*_grade`)
기상청 생활기상지수(`LivingWthrIdxServiceV3`)·보건기상지수(`HealthWthrIdxServiceV2`) API를 사용합니다. 처음에는 (V4로 잘못 추정해) apihub에 없다고 판단했으나, 실제 서비스명이 V3/V2였고 기존 authKey로 정상 호출됨을 확인했습니다(2026-07-01). 별도 서비스키는 필요 없습니다.
*   `uv_index`(3시간 간격 예보) + `uv_index_grade`(낮음/보통/높음/매우높음/위험 — WHO 표준 UV Index 등급)
*   `air_stagnation_index`(3시간 간격 예보) + `air_stagnation_grade` — 지수값이 25/50/75/100 중 하나로 이미 등급화되어 있어 그대로 매핑(낮음/보통/높음/매우높음)
*   `oak_pollen_risk`/`pine_pollen_risk`/`weed_pollen_risk`(일 2회, 오늘 값이 상태값) + 각 `*_grade` — 지수값 0~3이 그대로 등급(낮음/보통/높음/매우높음). `tomorrow`/`day_after_tomorrow` 속성으로 내일·모레 예보도 제공.
*   ⚠️ 꽃가루 3종은 계절 서비스입니다(참나무·소나무 3~6월, 잡초류 8~10월). 서비스 기간이 아니면 API가 정상적으로 "데이터 없음"을 반환하며, 이 통합은 그 상태를 그대로 반영합니다(이전 시즌 값을 남겨두지 않음).
*   지역코드(`areaNo`)는 기상청 API허브가 제공하는 공식 "행정구역코드정보" 자료(최종 업데이트 2026-07-01)와 실제 authKey 호출로 12개 대표 지역 전체를 교차 검증했습니다. 가능한 지역은 시/군 단위(예: 수원시장안구, 춘천시, 강릉시, 청주시상당구, 전주시완산구)로 더 정밀하게 조회하고, 시/군 코드가 없는 광역시(서울/인천/대전/대구/부산/광주)와 제주는 시도 단위를 씁니다.
    *   **강원/전북은 2023~2024년 특별자치도 개편 이후 코드(51/52)를 씁니다** — 표준 구(舊)코드 42/45로 조회하면 검색결과 없음으로 응답합니다.
    *   **광주는 예외 상황입니다**: 2026년에 전라남도와 통합되어 "전남광주통합특별시"(신코드 1200000000)로 개편되었지만, 이 생활기상지수 API는 아직 신코드를 인식하지 못해(2026-07-01 확인, 조회 시 검색결과 없음) 광주광역시 구코드(2900000000)를 그대로 쓰고 있습니다. API가 갱신되면 재확인이 필요합니다.
*   ⚠️ "대상환경별 체감온도"(`getSenTaIdxV3`, 노인/어린이/농촌/비닐하우스/취약거주환경/도로/건설현장/조선소 8종 대상)는 검토했으나 제외했습니다 — 문서에 서비스 종료 예정 표시(~2026-05-10)가 있었고, 실제로 여러 시각·지역으로 호출해봐도 계속 "데이터 없음"만 응답해 서비스가 종료된 것으로 판단했습니다.

---

## 🔑 필수 사전 작업 (기상청 API 신청)

통합 구성요소를 사용하기 위해서는 **기상청 APIhub** 계정 및 활용 신청이 완료된 인증키가 필요합니다.

1. [기상청 APIhub 공식 웹사이트](https://apihub.kma.go.kr/)에 회원가입 및 로그인합니다.
2. 마이페이지 또는 API 목록에서 아래 API들을 검색하여 **활용신청**을 진행하고 승인을 받습니다:
    *   **동네예보(단기예보) 지점자료 조회** (Open API `getVilageFcst`)
    *   **단기육상예보조회** (텍스트 API `fct_afs_dl.php`)
    *   **단기해상예보조회** (텍스트 API `fct_afs_do.php`)
    *   **기상특보현황** (텍스트 API `wrn_now_data.php`)
    *   **예보구역 정보** (텍스트 API `fct_shrt_reg.php`) - *API 키의 정상 여부 검증용*
    *   **PM10(미세먼지) 관측자료 조회** (텍스트 API `kma_pm10.php`, 지상관측 > 황사관측(PM10) 카테고리) - *미세먼지 센서용, 신규, ✅검증됨*
    *   **생활기상지수 조회서비스** (Open API `LivingWthrIdxServiceV3` — `getUVIdxV3`, `getAirDiffusionIdxV3`) - *자외선지수/대기정체지수 센서용, 신규, ✅검증됨*
    *   **보건기상지수 조회서비스** (Open API `HealthWthrIdxServiceV2` — `getOakPollenRiskIdxV2`, `getPinePollenRiskIdxV2`, `getWeedsPollenRiskndxV2`) - *꽃가루위험지수 센서용, 신규, ✅검증됨*
    *   **레이더영상 조회서비스** (Open API `WthrRadarInfoService` — `getCompCappiQcdArea`) - *레이더 강수강도 센서용, 신규, ✅검증됨*
    *   **위성(GK2A) 기상산출물** (위성 카테고리, seqApi=6 — `sat_file_list.php`) - *위성 이미지 엔티티용, 신규, ⚠️활용신청은 반영됐으나 산출물 코드 미확인*
3. 신청 완료 후 발급받은 **인증키(authKey)**를 준비합니다.

> ⚠️ **참고**: PM10, 생활기상지수/보건기상지수(자외선지수·대기정체지수·꽃가루위험지수), 레이더 강수강도는 모두 실제 authKey로 정상 동작을 확인했습니다 — 활용신청만 완료하면 바로 사용 가능합니다. 위성 이미지는 파일목록 API 활용신청은 반영됐지만, 실제 이미지 다운로드에 필요한 정확한 산출물 코드를 아직 확인하지 못해 미검증 상태입니다.

---

## ⚙️ 설치 방법

### 방법 1: HACS를 통한 설치 (추천)
1. 홈어시스턴트에서 **HACS** 메뉴로 이동합니다.
2. 우측 상단의 점 3개 메뉴를 누르고 **사용자 지정 저장소 (Custom Repositories)**를 선택합니다.
3. 아래 정보를 입력하고 카테고리를 **통합 구성요소 (Integration)**로 설정한 뒤 추가합니다:
    *   저장소 URL: `https://github.com/eigger/hass-kma` (리포지토리 주소)
4. 목록에 추가된 **기상청 APIhub** 통합 구성요소를 찾아 다운로드합니다.
5. 홈어시스턴트를 재부팅합니다.

### 방법 2: 수동 설치
1. 본 저장소의 `custom_components/kma` 폴더 전체를 다운로드합니다.
2. 홈어시스턴트 설정 디렉토리 내부의 `custom_components` 폴더 아래에 다운로드한 `kma` 폴더를 복사합니다.
   *   경로 구조: `<config_dir>/custom_components/kma/__init__.py`, `manifest.json` 등
3. 홈어시스턴트를 재부팅합니다.

---

## 🛠️ 설정 및 사용 방법

1. 홈어시스턴트의 **설정 -> 기기 및 서비스 -> 통합 구성요소 추가**로 이동합니다.
2. 검색창에 `기상청` 또는 `KMA`를 입력해 선택합니다.
3. 설정 화면에서 다음 항목을 입력/선택합니다:
    *   **인증키 (authKey)**: 기상청 APIhub에서 발급받은 키를 입력합니다.
    *   **기준 지역 (Zone)**: 날씨를 측정할 기준이 될 홈어시스턴트 Zone 엔티티(예: `zone.home`)를 지정합니다.
4. 제출(Submit)을 완료하면 자동으로 기상 정보 수집이 시작됩니다.
5. **옵션 변경**: 통합 구성요소 카드에서 `설정(Configure)`을 누르면 데이터 수집 갱신 주기를 언제든지 자유롭게 변경할 수 있습니다.

---

## 🤖 자동화(Automation) 작성 예제

사용자 거주 지역에 **기상특보가 발효되었을 때 스마트폰으로 경고 푸시 알림**을 보내는 자동화 예제입니다.

```yaml
alias: "[기상] 우리 동네 특보 발효 시 스마트폰 경고"
description: "기상청 특보 바이너리 센서가 켜지면 발효된 특보 상세 내역을 스마트폰으로 알립니다."
trigger:
  - platform: state
    entity_id: binary_sensor.kma_home_warning  # 본인의 엔티티 ID에 맞게 수정하세요.
    from: "off"
    to: "on"
condition: []
action:
  - service: notify.notify
    data:
      title: "⚠️ 기상청 특보 발효 경보"
      message: >-
        현재 지역에 {{ state_attr('binary_sensor.kma_home_warning', 'warnings_count') }}건의 기상 특보가 발효되었습니다.
        
        세부 내역:
        {% for w in state_attr('binary_sensor.kma_home_warning', 'active_warnings') %}
        - {{ w.region }} {{ w.warning_name }}{{ w.level_name }} (발효시각: {{ w.effective_time }})
        {% endfor %}
mode: single
```

---

## 🛠️ 추가 필요 항목 (향후 로드맵)

다음 항목들은 기상청 APIhub의 미신청 엔드포인트에 대한 추가 활용 신청 및 승인이 완료된 후 확장하여 구현할 수 있는 후보 과제입니다:

1. **지상관측 실황 연동 (ASOS/AWS)**: `kma_sfctm2.php` 등의 API를 활용해 관측소 기준 실측 기온/습도/풍속/기압 데이터 수집 및 연동 확장.
2. **지진/화산 이벤트 알림**: 최근 지진 발생 정보 API를 활용하여 신속한 지진 경보 및 통보 전문 알림 확장.
3. **태풍 정보 연동**: 태풍 발생 및 이동 경로 예측 정보 연동 확장.

> ✅ 미세먼지(PM10), 자외선지수·대기정체지수·꽃가루농도위험지수(참나무/소나무/잡초류), 레이더 강수강도 센서는 모두 실제 authKey로 동작을 검증했습니다. 레이더 합성영상은 이미지가 아니라 원시 데이터만 제공됨을 확인해 숫자 센서로 전환했고, 위성 이미지는 활용신청은 반영됐지만 정확한 산출물 코드가 아직 미확인입니다. "대상환경별 체감온도"는 서비스 종료로 판단해 구현하지 않았습니다 (위 "주요 기능", "주요 센서 상세 정보", "필수 사전 작업" 참고).

---

## 📄 라이선스
This project is licensed under the MIT License - see the LICENSE file for details.
