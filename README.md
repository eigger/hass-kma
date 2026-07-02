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
    *   `WthrRadarInfoService/getCompCappiQcdArea`(행정구역별 조회)를 사용해 Zone별 레이더 반사도(dBZ) 숫자 센서를 제공합니다. 자동화 조건식 등에 활용하기 좋습니다.
    *   ⚠️ 특정 지역(광주)은 2026년 행정구역 통합으로 대체된 구코드를 여전히 쓰고 있어 간헐적으로 오류가 발생할 수 있습니다 — 실패 시 이전 값을 유지합니다.
*   **레이더/위성/강수예측 이미지 (`image.kma_radar_image`, `image.kma_satellite_image`, `image.kma_precipitation_forecast_image`, `image.kma_satellite_visible_image`, `image.kma_satellite_shortwave_ir_image`, `image.kma_satellite_water_vapor_image`)** ✅ 실제 authKey로 동작 검증 완료(2026-07-01, 강수예측·위성 3채널 추가는 2026-07-02):
    *   레이더 합성영상 PNG(강수 분포도, 범례·시각 포함), 천리안위성(GK2A) 적외영상 PNG, 레이더 관측 기반 60분 뒤 강수 분포 예측(초단기 강수예측/QPF, MAPLE 블렌딩 모델) PNG, 그리고 위성 가시광선(vi006)·단파적외(sw038)·수증기(wv069) 채널 PNG를 최신 스냅샷으로 제공합니다.
    *   실제 API 호출은 Zone과 무관하게 딱 1세트만 발생하지만(한반도 전체 이미지라 Zone별로 다를 이유가 없음), 같은 캐시 이미지를 가리키는 엔티티를 **각 Zone 디바이스에** 배치합니다(허브/API Hub 디바이스에는 진단성 엔티티만 남기고 이미지는 두지 않음).
    *   약 10분 주기로 갱신되며, 대시보드의 Picture Entity 카드 등으로 바로 표시할 수 있습니다.
    *   처음 시도했던 `nph-rdr_cmp1_api`(원시 반사도 격자 데이터만 제공)와 `nph-gk2a_img`(잘못된 경로) 대신, 실제 PNG를 반환하는 별도 엔드포인트(레이더: `typ04/rdr_cmp_file.php?data=img`, 위성: `typ03/nph-gk2a_img`, 강수예측: `typ03/nph-qpf_ana_img`)를 찾아 사용합니다.
    *   ⚠️ 레이더/강수예측은 게시 지연(~15~20분)이 있어 아직 게시되지 않은 시각을 요청하면 이미지 대신 텍스트 오류가 200 OK로 오는 경우가 있어, PNG 매직바이트로 실제 이미지 여부를 확인합니다.
    *   ⚠️ 위성 가시광선(vi006)은 야간에는 관측되지 않아 검은 화면이 됩니다. 같은 `nph-gk2a_img` 엔드포인트에 `obs=cld`/`fog`/`dst`/`rgb-*` 등도 시도해봤으나 전부 1KB 안팎의 "미지원" 플레이스홀더 PNG만 반환되어(2026-07-02 실측) 구현하지 않았습니다 — 실제 값이 오는 채널은 ir105/vi006/sw038/wv069 4개뿐입니다.
*   **고해상도 지상관측 / 영향예보(폭염·한파) / 실측 적설 / 미세먼지 시간통계** ✅ 실제 authKey로 동작 검증 완료(2026-07-02):
    *   **실측 체감온도 (`apparent_temperature_observed`)**: 위경도 기반 고해상도 지상관측(`sfc_nc_var.php`)에서 받은 실측 체감온도. 기존 `apparent_temperature`(Steadman 공식 계산값)를 보완하는 실측치입니다.
    *   **폭염/한파 영향예보 (`heat_wave_risk`/`cold_wave_risk`)**: 기상청 공식 영향예보(`ifs_fct_pstt.php`) 위험수준을 그대로 등급(ENUM: 영향없음/관심/주의/경고/위험)으로 제공합니다. 로컬 계산이 아닌 기상청이 직접 발표하는 공식 지표입니다.
    *   **실측 적설 (`snow_depth_observed`)**: 관측소 실측 적설(`kma_snow1.php`). 기존 `snowfall`(예보값)을 보완합니다.
    *   **미세먼지 시간평균 (`pm10_hourly_avg`)**: 5분 원시값(`pm10`)과 별개로 해당 시간의 평균/최소/최대를 제공하는 시간통계(`dst_pm10_hr.php`)입니다.
*   **기상정보 / 날씨해설 텍스트 (`hazard_info`, `weather_commentary`)** ✅ 활용신청 불필요(2026-07-02 검증):
    *   관서(지방기상청)별로 예보관이 직접 작성하는 위험기상 실시간 속보(안개·소나기·뇌전 등)와 일일 날씨 해설문을 그대로 제공합니다. 로컬 계산 요약(`one_line_summary`)과 달리 기상청 예보관이 쓴 실제 문장입니다.
*   **지진정보 / 태풍정보 (`sensor.kma_*_recent_earthquake`, `sensor.kma_*_typhoon_status`)** ✅ 실제 authKey로 동작 검증 완료(2026-07-02):
    *   지진정보는 국내외 최신 지진 통보문(규모, 위치, 발생시각)을, 태풍정보는 현재 활성 태풍의 위치·중심기압·최대풍속·이동방향을 제공합니다(활성 태풍이 없으면 정상적으로 "없음" 상태).
    *   Zone과 무관한 전국 단위 데이터라 실제 API 호출은 1세트만 발생하지만, 레이더/위성 이미지와 같은 이유로 **각 Zone 디바이스에** 복제 배치합니다.
*   **황사위성영상 (`image.kma_dust_satellite_image`)** ✅ 실제 authKey로 동작 검증 완료(2026-07-02):
    *   GK2A 위성 기반 실제 황사지수(IDI) 이미지(`YdstInfoService/getYdstSatlitImg`)를 제공합니다. 나머지 위성 이미지들과 마찬가지로 각 Zone 디바이스에 배치됩니다.
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
| 기상청 날씨 | `sensor.kma_<지역>_apparent_temperature_observed` | 실측 체감온도 | `sfc_nc_var.php` (고해상도 지상관측) ✅검증됨 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_heat_wave_risk` | 폭염 영향예보 위험수준 | `ifs_fct_pstt.php` (ifpar=hw) ✅검증됨 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_cold_wave_risk` | 한파 영향예보 위험수준 | `ifs_fct_pstt.php` (ifpar=cw) ✅검증됨 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_hazard_info` | 기상정보 | `wrn_inf_rpt.php` ✅검증됨. 활용신청 불필요 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_weather_commentary` | 날씨해설 | `wthr_cmt_rpt.php` ✅검증됨. 활용신청 불필요 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_snow_depth_observed` | 실측 적설 | `kma_snow1.php` ✅검증됨 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pm10_hourly_avg` | 미세먼지 시간평균 | `dst_pm10_hr.php` ✅검증됨 | 10분 |
| 기상청 날씨 | `binary_sensor.kma_<지역>_warning` | 기상특보 안전 센서 | 기상특보현황 (`wrn_now_data`) | 10분 |
| 각 Zone | `sensor.kma_recent_earthquake` | 최근 지진정보 | `typ09/eqk/urlNewNotiEqk.do` ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `sensor.kma_typhoon_status` | 태풍 상태 | `typ_now.php` ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `image.kma_radar_image` | 레이더 합성영상 | `typ04/rdr_cmp_file.php` (data=img) ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `image.kma_satellite_image` | 위성(GK2A) 적외영상 | `typ03/nph-gk2a_img` ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `image.kma_precipitation_forecast_image` | 초단기 강수예측(60분 뒤) 영상 | `typ03/nph-qpf_ana_img` ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `image.kma_satellite_visible_image` | 위성(GK2A) 가시광선 영상 | `typ03/nph-gk2a_img?obs=vi006` ✅검증됨. 야간 미관측. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `image.kma_satellite_shortwave_ir_image` | 위성(GK2A) 단파적외 영상 | `typ03/nph-gk2a_img?obs=sw038` ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `image.kma_satellite_water_vapor_image` | 위성(GK2A) 수증기 영상 | `typ03/nph-gk2a_img?obs=wv069` ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |
| 각 Zone | `image.kma_dust_satellite_image` | 황사위성영상(IDI) | `YdstInfoService/getYdstSatlitImg` ✅검증됨. Zone마다 배치(허브에는 없음), 실제 호출은 1세트만 | 10분 |

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

### 4. 레이더 강수강도(`radar_precipitation`) / 레이더·위성·강수예측 이미지(`image.kma_radar_image`, `image.kma_satellite_image`, `image.kma_precipitation_forecast_image`, `image.kma_satellite_visible_image`, `image.kma_satellite_shortwave_ir_image`, `image.kma_satellite_water_vapor_image`)
처음 활용신청했던 레이더 합성영상 API(`nph-rdr_cmp1_api`, typ01)를 실제로 호출해보니 PNG 이미지가 아니라 **2305×2881 셀짜리 원시 dBZ(반사도) 격자 데이터**(ASCII 47MB 또는 바이너리 13MB)였습니다. 문서에도 "disp=A면 dbz*100 정수값 출력"이라고 명시되어 있어, 그 자체로는 이미지로 쓸 수 없었습니다.

이후 두 갈래로 해결했습니다:
1. **행정구역별 숫자값**: `WthrRadarInfoService/getCompCappiQcdArea`(typ02/openApi, 같은 authKey)로 Zone의 지역코드(`areaNo`, 위 자외선지수와 동일)만 넘기면 그 지역의 반사도 값 하나(dBZ)를 받아 `sensor.kma_<지역>_radar_precipitation`으로 제공합니다. 최신 데이터는 약 20분 지연 후 게시됨을 확인해(2026-07-01) 기본 조회 시각을 25분 전으로 설정합니다.
   *   ⚠️ 광주(구코드 2900000000 — 2026년 통합특별시 개편으로 대체된 레거시 코드)는 이 API에서 간헐적으로 오류가 발생함을 확인했습니다. 실패 시 이전 값을 유지합니다.
2. **실제 PNG 이미지**: 별도로 문서를 더 확인한 결과, `typ04/rdr_cmp_file.php?data=img&cmp=cmb`(레이더)와 `typ03/nph-gk2a_img?obs=ir105`(위성)가 범례·시각이 포함된 완성된 PNG를 반환함을 실제로 확인했습니다(2026-07-01, 시각적으로도 검증). 각각 `image.kma_radar_image`, `image.kma_satellite_image`로 제공합니다.
   *   레이더는 게시 지연(~15~20분)이 있고, 아직 게시되지 않은 시각을 요청하면 PNG 대신 EUC-KR 오류 텍스트("# file not exist")가 HTTP 200으로 오면서 Content-Type도 신뢰할 수 없는 값(`application/x-zip-compressed` 등)이 오는 경우가 있어, PNG 매직바이트(`\x89PNG...`)로 실제 이미지 여부를 판별합니다.
3. **강수예측(QPF) 이미지**: 레이더/위성 이미지 확인 과정에서 사용자가 신청한 나머지 API들을 추가로 검토한 결과, `typ03/nph-qpf_ana_img?qpf=M&ef=60`(레이더 관측 기반 MAPLE 블렌딩 모델로 60분 뒤 강수 분포를 예측)도 범례·시각이 포함된 완성된 PNG를 반환함을 확인했습니다(2026-07-02). `image.kma_precipitation_forecast_image`로 제공하며, 현재 레이더 이미지와 자연스럽게 짝을 이뤄 "지금"과 "60분 뒤"를 함께 볼 수 있습니다. 레이더 합성영상과 마찬가지로 게시 지연(~15~20분)이 있어 같은 백오프와 PNG 매직바이트 검증을 사용합니다.
   *   위성은 게시 지연이 거의 없음을 확인했습니다. 기본 채널은 적외(`ir105`, 주야간 모두 관측 가능)로 설정했습니다.
4. **위성 채널 추가**: 같은 `nph-gk2a_img` 엔드포인트에 `obs` 값만 바꿔 가시광선(`vi006`), 단파적외(`sw038`), 수증기(`wv069`) 채널도 실제 60~100KB 크기의 진짜 PNG로 응답함을 확인해(2026-07-02) 각각 `image.kma_satellite_visible_image`, `image.kma_satellite_shortwave_ir_image`, `image.kma_satellite_water_vapor_image`로 추가했습니다.
   *   ⚠️ 가시광선(`vi006`)은 야간에는 검은 화면입니다(빛이 없어 관측 불가).
   *   ⚠️ 같은 방식으로 `obs=cld`(구름탐지)/`fog`(안개)/`dst`(황사)/`rgb-true`/`rgb-natural` 등도 시도해봤으나 시각·`tm` 값과 무관하게 항상 1KB 안팎의 "미지원" 플레이스홀더 PNG만 돌아와(2026-07-02 실측) 구현하지 않았습니다. 이 산출물들은 별도의 처리된(Level 2) 데이터 형식(HDF5/바이너리 등)으로 제공되는 것으로 보이며, 간단한 PNG 조회로는 얻을 수 없습니다.

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

### 6. 고해상도 지상관측(`apparent_temperature_observed`) / 영향예보(`heat_wave_risk`, `cold_wave_risk`) / 실측 적설(`snow_depth_observed`) / 미세먼지 시간평균(`pm10_hourly_avg`)
사용자가 여러 차례에 걸쳐 공유한 API 문서를 실측 검증(2026-07-02)하며 추가한 4종입니다. 전부 Zone별 위경도 또는 지점코드를 그대로 재사용합니다.
*   **고해상도 지상관측** (`sfc_nc_var.php`, typ01): Zone의 위경도를 직접 넘겨 조회하는 특정지점 다중요소 관측입니다. ASOS(`kma_sfctm2.php`, 지점코드 기반)보다 이 API를 우선 채택했는데, 지점코드 매핑표가 필요 없고 실측 체감온도(`ta_chi`)를 제공하기 때문입니다 — 서울 좌표로 `기온 25.5℃, 체감온도 27.0℃`처럼 실제 값을 확인했습니다. 너무 최근 시각을 요청하면 미게시(0.0) 값이 오므로 15~25분 전 구간을 조회합니다.
*   **영향예보** (`ifs_fct_pstt.php`, typ01): 폭염(`ifpar=hw`)/한파(`ifpar=cw`) 위험수준(0~4, ENUM)을 관서(지방기상청) 코드로 조회합니다. Zone은 관서코드 매핑표(`LAND_ZONE_TO_OFFICE_STN`, 서울/인천/경기=109, 강원=105, 청주=131, 대전=133, 전주=146, 광주=156, 대구=143, 부산=159, 제주=184 — 실측으로 역추정한 9개 지방기상청 체계)로 변환되며, 관서 관할 내 여러 세부구역 중 최댓값을 대표값으로 씁니다. 비시즌(위험구역 없음)에는 정상적으로 "영향없음" 상태가 됩니다.
*   **실측 적설** (`kma_snow1.php`, typ01): PM10과 같은 지점코드 체계(`LAND_ZONE_TO_PM10_STN`)를 재사용합니다.
*   **미세먼지 시간평균** (`dst_pm10_hr.php`, typ01): 같은 PM10 지점코드를 재사용하되, 5분 원시값이 아니라 해당 시간의 평균/최소/최대 통계를 제공합니다. 이 엔드포인트는 `org` 파라미터로 중국기상청(CMA)/환경부(MOE) 데이터도 함께 제공함을 확인했으나(실측: 중국 10개 지점 수신 확인), Zone과 지리적으로 대응되는 관측망이 아니라서 이번 구현에서는 기상청(KMA) 데이터만 사용합니다.

### 7. 기상정보(`hazard_info`) / 날씨해설(`weather_commentary`)
관서(지방기상청)별 예보관이 직접 작성하는 텍스트 속보입니다(`wrn_inf_rpt.php`/`wthr_cmt_rpt.php`, typ01) — **활용신청이 필요 없어 바로 사용 가능**함을 실측 확인했습니다(2026-07-02). 두 API 모두 `"$0 헤더 + $1 본문"` 포맷을 공유해 같은 파서로 처리합니다.
*   **기상정보**: 안개·소나기·뇌전 등 특정 현상에 대한 실시간 위험기상 안내문.
*   **날씨해설**: 예보관이 쓴 일일 날씨 해설(수천 자 분량 — 기온/하늘상태/유의사항 등). `one_line_summary`(로컬 계산)를 보완하는 실제 예보관 문장입니다.
*   상태값은 제목(255자 이내)만 담고, 전문은 `body` 속성으로 제공됩니다(HA 센서 state 길이 제한).

### 8. 지진정보(`sensor.kma_recent_earthquake`) / 태풍정보(`sensor.kma_typhoon_status`)
Zone과 무관한 전국 단위 데이터라 실제 페칭은 허브 코디네이터(`KmaHubCoordinator`) 하나뿐이며, 레이더/위성 이미지와 같은 이유로 각 Zone 디바이스에 복제 배치합니다.
*   **지진정보** (`typ09/eqk/urlNewNotiEqk.do`): 국내외 지진 통보문(조기경보/속보/정보 구분)을 조회합니다. 실측(2026-07-02) 결과 실제 최근 지진(일본 혼슈 미야기현 앞바다 M6.0)을 정상 수신했습니다. 다른 typ01 API와 달리 이 typ09 응답은 EUC-KR이 아니라 UTF-8입니다(실측으로 확인 — EUC-KR로 디코딩하면 한글이 깨짐).
*   **태풍정보** (`typ_now.php`): 현재 활성 태풍의 위치·중심기압·최대풍속·이동방향을 조회합니다(`mode=2`, 최근 분석+예측). 활성 태풍이 없으면 데이터 라인이 없어 정상적으로 "없음"(태풍번호 0) 상태가 됩니다 — 태풍철 여름~가을에 값이 채워집니다.

### 9. 황사위성영상(`image.kma_dust_satellite_image`)
`YdstInfoService/getYdstSatlitImg`(typ02/openApi)를 사용합니다. 이 API 자체는 이미지 바이너리가 아니라 그날 하루치(5분 간격) 썸네일 PNG URL 목록(JSON)을 반환하는데, 목록에는 아직 게시되지 않은 뒤쪽 시각의 URL도 미리 나열되어 있어(다운로드하면 HTML 오류 페이지가 옴, 실측 확인) 뒤에서부터 순회하며 실제 PNG가 나오는 첫 URL을 사용합니다. 공개 저장소 URL이라 이미지 다운로드 자체에는 authKey가 필요 없음을 확인했습니다. `nph-gk2a_img?obs=dst`가 가짜 플레이스홀더였던 것의 정식 대체 경로입니다.

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
    *   **레이더 합성자료 다운로드** (텍스트/이미지 API `typ04/rdr_cmp_file.php`) - *레이더 이미지 엔티티용, 신규, ✅검증됨*
    *   **천리안 2A호 위성 분포도 조회** (그래픽 API `typ03/nph-gk2a_img`) - *위성 적외/가시광선/단파적외/수증기 이미지 엔티티 4종 공통, 신규, ✅검증됨*
    *   **초단기 강수예측 그래픽 조회** (그래픽 API `typ03/nph-qpf_ana_img`) - *강수예측(QPF) 이미지 엔티티용, 신규, ✅검증됨*
    *   **고해상도 지상관측** (텍스트 API `sfc_nc_var.php`, 특정지점 다중요소) - *실측 체감온도 센서용, 신규, ✅검증됨*
    *   **영향예보(발표현황) 조회** (텍스트 API `ifs_fct_pstt.php`) - *폭염/한파 위험수준 센서용, 신규, ✅검증됨*
    *   **적설관측자료 조회** (텍스트 API `kma_snow1.php`) - *실측 적설 센서용, 신규, ✅검증됨*
    *   **황사(PM10) 시간통계자료 조회** (텍스트 API `dst_pm10_hr.php`) - *미세먼지 시간평균 센서용, 신규, ✅검증됨*
    *   **지진정보(최근 발표 정보·속보) 조회** (텍스트 API `typ09/eqk/urlNewNotiEqk.do`) - *지진정보 센서용, 신규, ✅검증됨*
    *   **태풍정보(기상청 발표) 조회** (텍스트 API `typ_now.php`) - *태풍정보 센서용, 신규, ✅검증됨*
    *   **황사정보(위성영상) 조회서비스** (Open API `YdstInfoService` — `getYdstSatlitImg`) - *황사위성영상 엔티티용, 신규, ✅검증됨*
    *   기상정보(`wrn_inf_rpt.php`)/날씨해설(`wthr_cmt_rpt.php`)은 별도 활용신청 없이 바로 동작함을 확인했습니다 — 신청 목록에 없어도 됩니다.
3. 신청 완료 후 발급받은 **인증키(authKey)**를 준비합니다.

> ⚠️ **참고**: PM10, 생활기상지수/보건기상지수(자외선지수·대기정체지수·꽃가루위험지수), 레이더 강수강도, 레이더·위성·강수예측·황사위성 이미지, 고해상도 지상관측, 영향예보(폭염/한파), 실측 적설, 미세먼지 시간평균, 지진정보, 태풍정보 모두 실제 authKey로 정상 동작을 확인했습니다 — 활용신청만 완료하면 바로 사용 가능합니다.

### API 활용신청 상태를 확인하려면?

각 API마다 활용신청을 깜빡했거나 아직 승인 대기 중인지 헷갈릴 수 있어, **기상청 APIhub** 허브 디바이스에 이 통합이 쓰는 API 전체(총 27개)에 대해 진단 센서를 하나씩 자동으로 만듭니다.

*   **`binary_sensor.kma_activation_<api>`**: 활용신청 완료 + 정상 응답이면 `on`, 미신청(403)이거나 오류면 `off`. `status` 속성에 `ok`/`not_applied`/`error: ...` 상세 상태가 표시되어, 403(미신청)인지 다른 오류인지 바로 구분할 수 있습니다.
*   **`sensor.kma_error_count_<api>`**: 해당 API의 누적 에러 횟수(진단 카테고리). `last_error_time`, `current_status` 속성도 함께 제공합니다.

`<api>`에는 Zone별 예·특보/생활기상지수 API 18종(`village_forecast`, `land_forecast`, `marine_forecast`, `warning_now`, `pm10`, `uv_index`, `air_stagnation`, `oak_pollen`, `pine_pollen`, `weed_pollen`, `radar_precipitation`, `sfc_observation`, `heat_wave_risk`, `cold_wave_risk`, `hazard_info`, `weather_commentary`, `snow_depth`, `pm10_hourly`), Zone 무관 레이더·위성 이미지 API 7종(`radar`, `satellite`, `precipitation_forecast`, `satellite_visible`, `satellite_shortwave_ir`, `satellite_water_vapor`, `dust_satellite`), Zone 무관 허브 데이터 API 2종(`earthquake`, `typhoon`)이 모두 포함됩니다 — 이 통합이 호출하는 API는 예외 없이 전부 진단 센서가 있습니다.

이 세 목록은 `const.py`의 `API_STATUS_ZONE_KEYS`/`API_STATUS_IMAGE_KEYS`/`API_STATUS_HUB_KEYS`에서 단일 소스로 관리됩니다. 새 센서가 새로운 API를 필요로 하게 되면, 해당 코디네이터의 데이터 조회 로직에서 상태 문자열("ok"/"not_applied"/"error: ...")을 채우고 이 세 목록 중 하나에 API key를 추가하기만 하면 활용신청 상태/에러 카운트 센서가 자동으로 생성됩니다(수동으로 센서 클래스를 새로 만들 필요 없음).

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

지상관측 실황(ASOS 대체 — 고해상도 지상관측), 지진정보, 태풍 정보는 2026-07-02에 모두 구현·검증 완료되어 이 로드맵에서 졸업했습니다(위 "주요 기능", "주요 센서 상세 정보" 참고). 다음은 검토했지만 아직 구현하지 않은 후보입니다:

1. **해양관측(부이+연안) 연동**: `kma_buoy2.php`/`sea_obs.php`로 파고·수온·기압 실측치를 해상 Zone에 제공. 활용신청 필요, 검증되지 않음.
2. **해구별 예측 정보**: `marine_small_zone.php`/`marine_large_zone.php`로 유의파고·최대파주기·파향 등 +75시간 예측. 대/소해구 번호를 해상 Zone에 매핑하는 참조 자료가 추가로 필요해 우선순위가 낮습니다.
3. **영향예보 폭염/한파 위험수준 분포도 이미지**: `ifs_ilvl_dmap.php` — 현재는 수치(ENUM)만 제공하는데, 전국 분포도 PNG도 실측으로 확인했으니 이미지 엔티티로 추가할 수 있습니다.

> ✅ 미세먼지(PM10, 5분 원시값+시간평균), 자외선지수·대기정체지수·꽃가루농도위험지수(참나무/소나무/잡초류), 레이더 강수강도, 레이더·위성(적외/가시광선/단파적외/수증기)·황사위성·강수예측 이미지, 고해상도 지상관측(실측 체감온도), 영향예보(폭염/한파), 기상정보·날씨해설, 실측 적설, 지진정보, 태풍정보 모두 실제 authKey로 동작을 검증했습니다. "대상환경별 체감온도"는 서비스 종료로 판단해 구현하지 않았습니다 (위 "주요 기능", "주요 센서 상세 정보", "필수 사전 작업" 참고).

---

## 📄 라이선스
This project is licensed under the MIT License - see the LICENSE file for details.
