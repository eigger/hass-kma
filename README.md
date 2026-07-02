# 기상청 APIhub 연동 홈어시스턴트 통합 구성요소 (hass-kma)

[![GitHub Release](https://img.shields.io/github/v/release/eigger/hass-kma?style=flat-square)](https://github.com/eigger/hass-kma/releases)
[![License](https://img.shields.io/github/license/eigger/hass-kma?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&query=%24.kma.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)

기상청 APIhub(apihub.kma.go.kr) 공식 텍스트 및 개방형 API를 연동하여 홈어시스턴트(Home Assistant)에 실시간 기상 상태, 상세 관측값, 중단기 예보, 생활기상지수·미세먼지·자외선지수·대기정체지수·꽃가루위험지수 및 재난 기상특보 경보를 제공하는 통합 구성요소입니다.

---

## 🌟 주요 기능

* **표준 날씨 엔티티 (`weather.kma_*`)**
  * 현재 날씨 상태 및 기온·습도·풍향·풍속.
  * **시간별 예보**: 향후 3일간의 시간별 동네예보.
  * **일별 예보**: 3일간 동네예보를 일 단위로 집계하고, 4~10일차는 육상예보(`fct_afs_dl`)와 병합하여 최대 10일간의 연속 일별 예보를 제공합니다.
  * 예보 요약 문구(`land_forecast_summary`, `marine_forecast_summary`) 및 발효된 기상특보 목록을 엔티티 속성으로 제공합니다.
* **상세 기상 센서 (`sensor.kma_*`)**
  * 기온, 습도, 풍속, 강수확률, 1시간 강수량.
  * **육상/해상 예보 요약**: 대시보드에 바로 표시 가능한 한국어 예보 문구.
  * **오늘 최저/최고기온**: 동네예보 극값 스캔.
  * **비/눈 예보 탐색**: 향후 24시간 이내 강수를 감시하며, 3/6/12시간 이내 강수 여부를 속성으로 제공.
  * **한 줄 기상 요약**: 현재 상태·기온·오늘 극값·가장 가까운 강수 예보를 하나의 문자열로 요약 (전자라벨/E-Paper 연동에 적합).
  * **체감온도 / 이슬점 / 불쾌지수**: Steadman/Magnus-Tetens 공식 기반 실시간 계산. 불쾌지수는 등급 ENUM 센서(`discomfort_grade`)를 함께 제공합니다.
* **생활기상지수 4종**
  * 빨래 건조 지수, 세차 지수, 동파 가능 지수, 식중독 지수 — 각각 0~100 수치 센서와 등급 ENUM 센서(`*_grade`) 쌍으로 제공됩니다. 등급 상태값은 홈어시스턴트 시스템 언어에 맞춰 자동 번역됩니다.
* **미세먼지(PM10)**
  * 지상관측 PM10 자료(5분 간격)로 가장 가까운 관측지점의 농도(`pm10`)와 환경부 기준 등급(`pm10_grade`)을 제공합니다. 시간 평균/최소/최대 통계(`pm10_hourly_avg`)도 별도로 제공됩니다.
* **자외선지수 / 대기정체지수 / 꽃가루농도위험지수**
  * 기상청 생활기상지수·보건기상지수 API를 사용하며 기존 authKey로 동작합니다.
  * 자외선지수, 대기정체지수는 3시간 간격, 꽃가루위험지수(참나무/소나무/잡초류)는 일 2회 갱신되며 계절 서비스 기간 외에는 정상적으로 "데이터 없음" 상태가 됩니다.
* **레이더 강수강도 및 레이더/위성/강수예측 이미지**
  * Zone 행정구역 기준 레이더 반사도(dBZ) 수치 센서.
  * 레이더 합성영상, 위성(적외/가시광선/단파적외/수증기) 영상, 60분 뒤 강수예측(QPF) 영상, 황사위성영상을 Picture Entity로 바로 표시할 수 있는 PNG 이미지 엔티티로 제공합니다.
* **고해상도 지상관측 / 영향예보 / 실측 적설**
  * 위경도 기반 실측 체감온도(`apparent_temperature_observed`).
  * 기상청 공식 폭염/한파 영향예보 위험수준(`heat_wave_risk`/`cold_wave_risk`, ENUM).
  * 관측소 실측 적설(`snow_depth_observed`).
* **기상정보 / 날씨해설 텍스트**
  * 지방기상청 예보관이 작성하는 위험기상 속보(`hazard_info`)와 일일 날씨 해설(`weather_commentary`)을 소제목 기준 섹션으로 나눠 제공합니다.
* **지진정보 / 태풍정보**
  * 최신 지진 통보문과 활성 태풍의 위치·중심기압·최대풍속·이동방향을 제공합니다(활성 태풍이 없으면 정상적으로 "없음" 상태).
* **재난 기상특보 안전 센서 (`binary_sensor.kma_*_warning`)**
  * 거주 지역(광역자치단체 기준)에 특보(호우, 대설, 강풍, 폭염, 한파, 태풍, 황사 등)가 발효되면 즉시 `on` 상태가 되며, 특보 개수·명칭·발효시간·상세 목록을 속성으로 제공합니다.
* **API 활용신청 상태 진단**
  * 이 통합이 호출하는 모든 API에 대해 활용신청 여부(`binary_sensor.kma_activation_*`)와 누적 에러 횟수(`sensor.kma_error_count_*`, 마지막 에러 시각 포함) 진단 센서를 자동 생성합니다.
* **간편한 설정 흐름**
  * 홈어시스턴트 Zone 엔티티(`zone.*`)를 선택하면 위경도로부터 기상청 격자좌표(nx, ny) 및 최적의 육상/해상 예보구역을 자동 매핑합니다.
  * 데이터 갱신 주기(기본 10분, 5~180분)를 옵션 화면에서 변경할 수 있습니다.

---

## 📋 센서 목록

| 기기 | 센서 ID | 센서 이름 | 사용 API | 갱신 주기 |
| --- | --- | --- | --- | --- |
| 기상청 날씨 | `weather.kma_<지역>` | 날씨 (Weather) | 동네예보 (`getVilageFcst`) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_temperature` | 기온 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_humidity` | 습도 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_wind_speed` | 풍속 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pop` | 강수확률 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pcp` | 1시간 강수량 | 동네예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_temp_min` | 오늘 최저기온 | 동네예보 극값 스캔 | 매시간 |
| 기상청 날씨 | `sensor.kma_<지역>_temp_max` | 오늘 최고기온 | 동네예보 극값 스캔 | 매시간 |
| 기상청 날씨 | `sensor.kma_<지역>_precipitation_forecast` | 비/눈 예보 탐색 | 동네예보 24시간 스캔 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_apparent_temperature` | 체감온도 | Steadman 공식 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_dew_point` | 이슬점 | Magnus-Tetens 공식 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_discomfort_index` / `_grade` | 불쾌지수 / 등급 | 기온·습도 기반 연산 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_laundry_index` / `_grade` | 빨래 건조 지수 / 등급 | 기온·습도·풍속·강수예보 종합 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_car_wash_index` / `_grade` | 세차 지수 / 등급 | 72시간 내 강수 예보 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_freeze_risk_index` / `_grade` | 동파 가능 지수 / 등급 | 48시간 내 최저 예보기온 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_food_poisoning_index` / `_grade` | 식중독 지수 / 등급 | 기온·습도 기반 예측 연산 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_one_line_summary` | 한 줄 기상 요약 | 현재 날씨·극값·강수·특보 종합 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_land_forecast_summary` | 육상 예보 요약 | 단기육상예보조회 (`fct_afs_dl`) | 매일 5시, 17시 |
| 기상청 날씨 | `sensor.kma_<지역>_marine_forecast_summary` | 해상 예보 요약 | 단기해상예보조회 (`fct_afs_do`) | 매일 5시, 17시 |
| 기상청 날씨 | `sensor.kma_<지역>_pm10` / `_grade` | 미세먼지(PM10) / 등급 | PM10 관측자료 (`kma_pm10.php`) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pm10_hourly_avg` | 미세먼지 시간평균 | `dst_pm10_hr.php` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_uv_index` / `_grade` | 자외선지수 / 등급 | `LivingWthrIdxServiceV3/getUVIdxV3` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_air_stagnation_index` / `_grade` | 대기정체지수 / 등급 | `LivingWthrIdxServiceV3/getAirDiffusionIdxV3` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_oak_pollen_risk` / `_grade` | 꽃가루위험지수(참나무) / 등급 | `HealthWthrIdxServiceV2/getOakPollenRiskIdxV2` (서비스기간 3~6월) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pine_pollen_risk` / `_grade` | 꽃가루위험지수(소나무) / 등급 | `HealthWthrIdxServiceV2/getPinePollenRiskIdxV2` (서비스기간 3~6월) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_weed_pollen_risk` / `_grade` | 꽃가루위험지수(잡초류) / 등급 | `HealthWthrIdxServiceV2/getWeedsPollenRiskndxV2` (서비스기간 8~10월) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_radar_precipitation` | 레이더 강수강도(dBZ) | `WthrRadarInfoService/getCompCappiQcdArea` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_radar_precipitation_grade` | 레이더 강수강도 등급 | dBZ 값 기반 강수강도 등급 분류 (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_apparent_temperature_observed` | 실측 체감온도 | `sfc_nc_var.php` (고해상도 지상관측) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_heat_wave_risk` / `_cold_wave_risk` | 폭염 / 한파 영향예보 위험수준 | `ifs_fct_pstt.php` (ENUM) | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_snow_depth_observed` | 실측 적설 | `kma_snow1.php` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_hazard_info` (+ `_section_1`~`_3`) | 기상정보 | `wrn_inf_rpt.php` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_weather_commentary` (+ `_section_1`~`_8`) | 날씨해설 | `wthr_cmt_rpt.php` | 10분 |
| 기상청 날씨 | `binary_sensor.kma_<지역>_warning` | 기상특보 안전 센서 | 기상특보현황 (`wrn_now_data`) | 10분 |
| 각 Zone | `sensor.kma_recent_earthquake` | 최근 지진정보 | `typ09/eqk/urlNewNotiEqk.do` | 10분 |
| 각 Zone | `sensor.kma_typhoon_number` | 태풍 번호 | `typ_now.php` | 10분 |
| 각 Zone | `image.kma_radar_image` | 레이더 합성영상 | `typ04/rdr_cmp_file.php` | 10분 |
| 각 Zone | `image.kma_satellite_image` | 위성(GK2A) 적외영상 | `typ03/nph-gk2a_img` | 10분 |
| 각 Zone | `image.kma_precipitation_forecast_image` | 초단기 강수예측(60분 뒤) 영상 | `typ03/nph-qpf_ana_img` | 10분 |
| 각 Zone | `image.kma_satellite_visible_image` | 위성(GK2A) 가시광선 영상 | `typ03/nph-gk2a_img?obs=vi006` | 10분 |
| 각 Zone | `image.kma_satellite_shortwave_ir_image` | 위성(GK2A) 단파적외 영상 | `typ03/nph-gk2a_img?obs=sw038` | 10분 |
| 각 Zone | `image.kma_satellite_water_vapor_image` | 위성(GK2A) 수증기 영상 | `typ03/nph-gk2a_img?obs=wv069` | 10분 |
| 각 Zone | `image.kma_dust_satellite_image` | 황사위성영상(IDI) | `YdstInfoService/getYdstSatlitImg` | 10분 |

> 지진정보·태풍정보·레이더/위성/강수예측/황사위성 이미지는 Zone과 무관한 전국 단위 자료라 실제 API 호출은 1세트만 발생하지만, 각 Zone 디바이스에서 동일하게 조회할 수 있도록 Zone별로 엔티티를 배치합니다(허브 디바이스에는 진단 센서만 있습니다).

---

## 🔍 주요 센서 상세 정보

### 한 줄 기상 요약 (`one_line_summary`)
전자라벨(ESL), E-Paper 등 제한된 공간의 디스플레이에 기상 상황을 직관적으로 노출하기 위한 텍스트 센서입니다. 홈어시스턴트 시스템 언어 설정에 맞춰 메시지가 구성됩니다.

* 출력 예시: `맑음, 19.5°C (11.0°C/26.0°C)`, `흐림, 15.0°C (12.0°C/18.0°C), 16시경 비 예보`, `맑음, 29.0°C (20.0°C/31.0°C) [폭염주의보]`

### 생활기상지수 4종
각 지수는 0~100 수치 센서(`_index`)와 등급 ENUM 센서(`_grade`) 쌍으로 제공됩니다. 추천 가이드라인(`recommendation`)은 자유 텍스트라 `_index` 센서의 속성으로 제공됩니다.

* **빨래 건조 지수**: 매우 좋음/좋음/보통/비추천
* **세차 지수**: 매우 좋음/보류 권장/세차 비추/세차 금지
* **동파 가능 지수**: 낮음/보통/높음/매우 높음
* **식중독 지수**: 관심/주의/경고/위험

### 미세먼지(PM10)
지상관측 PM10 관측자료(5분 간격)를 사용하며, Zone에서 가장 가까운 관측지점의 값을 가져옵니다. 관측망이 ASOS보다 지점 수가 적어 일부 지역은 인접 지점 값으로 대체됩니다(청주·대전은 천안 지점을 공유). PM2.5(초미세먼지)는 이 API에서 제공되지 않아 지원 범위 밖입니다.

* `pm10`: 농도 수치 (㎍/㎥)
* `pm10_grade`: 환경부 기준 등급 (좋음 0~30 / 보통 31~80 / 나쁨 81~150 / 매우나쁨 151~)
* `pm10_hourly_avg`: 5분 원시값과 별개로 시간 단위 평균/최소/최대 통계 제공
* `pm10`/`pm10_hourly_avg` 모두 실제로 어느 관측소 값인지 알 수 있도록 `station_id`(지점번호)와 `station_name`(지점명, 예: "서울"/"강화"/"천안") 속성을 함께 제공합니다.

### 레이더 강수강도 / 레이더·위성·강수예측 이미지
* **레이더 강수강도**: Zone 행정구역코드로 조회하는 반사도(dBZ) 수치 센서입니다. 최신 데이터가 약 20분 지연 후 게시되므로 기본 조회 시각을 25분 전으로 설정합니다. dBZ 값은 강수량(mm)이 아니라 반사 에너지의 로그 스케일 지표라 그대로는 직관적이지 않으므로, 강수없음/안개비/약한비/보통비/강한비/장대비 6단계로 분류한 `radar_precipitation_grade`(ENUM) 센서를 함께 제공합니다. 무에코·관측범위밖 센티널 값(-250 근방)은 "강수없음"으로 처리됩니다.
* **이미지 엔티티**: 레이더 합성영상, 위성 적외/가시광선/단파적외/수증기 4채널, 60분 뒤 강수예측(QPF, MAPLE 블렌딩 모델), 황사위성(IDI) PNG를 Picture Entity 카드로 바로 표시할 수 있습니다. 약 10분 주기로 갱신됩니다.
* 레이더/강수예측 이미지는 게시 지연(~15~20분)이 있어 아직 게시되지 않은 시각을 요청하면 오류 응답이 올 수 있으므로 PNG 매직바이트로 실제 이미지 여부를 확인합니다.
* 위성 가시광선(`vi006`) 채널은 야간에는 관측되지 않아 검은 화면이 됩니다.

### 자외선지수 / 대기정체지수 / 꽃가루농도위험지수
기상청 생활기상지수(`LivingWthrIdxServiceV3`)·보건기상지수(`HealthWthrIdxServiceV2`) API를 사용하며, 기존 authKey 그대로 동작합니다.

* `uv_index`(3시간 간격) + `uv_index_grade`(낮음/보통/높음/매우높음/위험, WHO 표준)
* `air_stagnation_index`(3시간 간격) + `air_stagnation_grade` — 지수값(25/50/75/100)이 그대로 등급에 대응
* `oak_pollen_risk`/`pine_pollen_risk`/`weed_pollen_risk`(일 2회) + 각 `*_grade` — 지수값(0~3)이 그대로 등급에 대응. `tomorrow`/`day_after_tomorrow` 속성으로 내일·모레 예보도 제공
* 꽃가루 3종은 계절 서비스입니다(참나무·소나무 3~6월, 잡초류 8~10월). 서비스 기간이 아니면 정상적으로 "데이터 없음" 상태가 되며 이전 시즌 값을 이어붙이지 않습니다
* 가능한 지역은 시/군 단위로 조회해 정밀도를 높였으며, 광주는 행정구역 개편 이전 코드를 사용합니다(API가 신코드를 지원하지 않는 동안 유지)

### 고해상도 지상관측 / 영향예보 / 실측 적설 / 미세먼지 시간평균
* **실측 체감온도**(`apparent_temperature_observed`): 위경도 기반 특정지점 다중요소 관측(`sfc_nc_var.php`)에서 받은 실측 체감온도로, 계산값인 `apparent_temperature`를 보완합니다. 관측소가 아니라 Zone의 위경도를 직접 조회하는 방식이라, 조회에 쓰인 좌표를 `lat`/`lon` 속성으로 그대로 제공합니다.
* **영향예보**(`heat_wave_risk`/`cold_wave_risk`): 기상청이 직접 발표하는 폭염/한파 위험수준(ENUM)입니다. Zone은 관할 지방기상청 코드로 매핑되며, 비시즌에는 정상적으로 "영향없음" 상태가 됩니다.
* **실측 적설**(`snow_depth_observed`): 관측소 실측 적설로, 예보값인 `snowfall`을 보완합니다. PM10과 같은 관측지점 체계를 공유하여 `station_id`/`station_name` 속성을 제공합니다.
* **미세먼지 시간평균**(`pm10_hourly_avg`): 5분 원시값과 별개로 해당 시간의 평균/최소/최대 통계를 제공합니다.

### 기상정보 / 날씨해설
지방기상청 예보관이 직접 작성하는 텍스트 속보입니다. 별도 활용신청 없이 바로 사용할 수 있습니다.

* **기상정보**(`hazard_info`): 안개·소나기·뇌전 등 위험기상 실시간 안내문.
* **날씨해설**(`weather_commentary`): 예보관이 작성한 일일 날씨 해설(기온/하늘상태/유의사항 등).
* 대표 센서의 상태값은 제목만 담고, 전문은 `sections` 속성에 소제목 기준 딕셔너리로 제공됩니다. 이와 별도로 `_section_1`~`_8`(날씨해설)/`_section_1`~`_3`(기상정보) 고정 슬롯 센서를 제공하여, 발표할 때마다 달라지는 소제목이 있어도 엔티티 개수가 고정되도록 설계했습니다.
* 관측소 지점이 아니라 **관할 지방기상청(관서) 단위**로 발표되는 정보라, 소속 관서를 `office_code`/`office_name`(예: "서울지방기상청") 속성으로 함께 제공합니다. 섹션 슬롯 센서에도 동일하게 포함됩니다. 폭염/한파 영향예보(`heat_wave_risk`/`cold_wave_risk`)도 같은 관서 체계를 공유합니다.

### 지진정보 / 태풍정보
Zone과 무관한 전국 단위 데이터입니다.

* **지진정보**(`sensor.kma_recent_earthquake`): 국내외 최신 지진 통보문(규모, 위치, 발생시각).
* **태풍정보**(`sensor.kma_typhoon_number`): 현재 활성 태풍의 위치·중심기압·최대풍속·이동방향(활성 태풍이 없으면 "없음" 상태).

### 황사위성영상
GK2A 위성 기반 황사지수(IDI) 이미지를 제공합니다(`image.kma_dust_satellite_image`).

---

## 🔑 필수 사전 작업 (기상청 API 신청)

통합 구성요소를 사용하려면 **기상청 APIhub** 계정 및 활용 신청이 완료된 인증키가 필요합니다.

1. [기상청 APIhub 공식 웹사이트](https://apihub.kma.go.kr/)에 회원가입 및 로그인합니다.
2. 마이페이지 또는 API 목록에서 아래 API들을 검색하여 **활용신청**을 진행하고 승인을 받습니다:
    * 동네예보(단기예보) 지점자료 조회 (`getVilageFcst`)
    * 단기육상예보조회 (`fct_afs_dl.php`)
    * 단기해상예보조회 (`fct_afs_do.php`)
    * 기상특보현황 (`wrn_now_data.php`)
    * 예보구역 정보 (`fct_shrt_reg.php`) — API 키 정상 여부 검증용
    * PM10(미세먼지) 관측자료 조회 (`kma_pm10.php`, 지상관측 > 황사관측(PM10))
    * 황사(PM10) 시간통계자료 조회 (`dst_pm10_hr.php`)
    * 생활기상지수 조회서비스 (`LivingWthrIdxServiceV3` — `getUVIdxV3`, `getAirDiffusionIdxV3`)
    * 보건기상지수 조회서비스 (`HealthWthrIdxServiceV2` — `getOakPollenRiskIdxV2`, `getPinePollenRiskIdxV2`, `getWeedsPollenRiskndxV2`)
    * 레이더영상 조회서비스 (`WthrRadarInfoService/getCompCappiQcdArea`)
    * 레이더 합성자료 다운로드 (`typ04/rdr_cmp_file.php`)
    * 천리안 2A호 위성 분포도 조회 (`typ03/nph-gk2a_img`) — 위성 적외/가시광선/단파적외/수증기 4종 공통
    * 초단기 강수예측 그래픽 조회 (`typ03/nph-qpf_ana_img`)
    * 고해상도 지상관측 (`sfc_nc_var.php`, 특정지점 다중요소)
    * 영향예보(발표현황) 조회 (`ifs_fct_pstt.php`)
    * 적설관측자료 조회 (`kma_snow1.php`)
    * 지진정보(최근 발표 정보·속보) 조회 (`typ09/eqk/urlNewNotiEqk.do`)
    * 태풍정보(기상청 발표) 조회 (`typ_now.php`)
    * 황사정보(위성영상) 조회서비스 (`YdstInfoService/getYdstSatlitImg`)
    * 기상정보(`wrn_inf_rpt.php`)/날씨해설(`wthr_cmt_rpt.php`)은 별도 활용신청 없이 바로 동작합니다.
3. 신청 완료 후 발급받은 **인증키(authKey)**를 준비합니다.

### API 활용신청 상태를 확인하려면?

각 API마다 활용신청을 깜빡했거나 승인 대기 중인지 확인할 수 있도록, **기상청 APIhub** 허브 디바이스에 이 통합이 사용하는 API 전체에 대해 진단 센서를 자동으로 생성합니다.

* **`binary_sensor.kma_activation_<api>`**: 활용신청 완료 + 정상 응답이면 `on`, 미신청(403)이거나 오류면 `off`. `status` 속성에 `ok`/`not_applied`/`error: ...` 상세 상태가 표시됩니다.
* **`sensor.kma_error_count_<api>`**: 해당 API의 누적 에러 횟수(진단 카테고리). `last_error_time`, `current_status` 속성도 함께 제공합니다.

새로운 API가 추가되어도 코드 수정 없이 진단 센서가 자동으로 생성되도록 `const.py`의 `API_STATUS_ZONE_KEYS`/`API_STATUS_IMAGE_KEYS`/`API_STATUS_HUB_KEYS` 목록에서 단일 관리됩니다.

---

## ⚙️ 설치 방법

### 방법 1: HACS를 통한 설치 (추천)
1. 홈어시스턴트에서 **HACS** 메뉴로 이동합니다.
2. 우측 상단의 점 3개 메뉴를 누르고 **사용자 지정 저장소 (Custom Repositories)**를 선택합니다.
3. 저장소 URL `https://github.com/eigger/hass-kma`를 입력하고 카테고리를 **통합 구성요소 (Integration)**로 설정한 뒤 추가합니다.
4. 목록에 추가된 **기상청 APIhub** 통합 구성요소를 찾아 다운로드합니다.
5. 홈어시스턴트를 재부팅합니다.

### 방법 2: 수동 설치
1. 본 저장소의 `custom_components/kma` 폴더 전체를 다운로드합니다.
2. 홈어시스턴트 설정 디렉토리 내부의 `custom_components` 폴더 아래에 `kma` 폴더를 복사합니다.
   * 경로 구조: `<config_dir>/custom_components/kma/__init__.py`, `manifest.json` 등
3. 홈어시스턴트를 재부팅합니다.

---

## 🛠️ 설정 및 사용 방법

1. 홈어시스턴트의 **설정 → 기기 및 서비스 → 통합 구성요소 추가**로 이동합니다.
2. 검색창에 `기상청` 또는 `KMA`를 입력해 선택합니다.
3. **인증키(authKey)**를 입력합니다.
4. 설정 완료 후 통합 구성요소 카드에서 **지역(Zone) 추가**를 눌러 날씨를 받을 위치를 하나 이상 등록합니다. 등록된 Zone의 위경도로부터 기상청 격자좌표 및 예보구역이 자동 매핑됩니다.
5. **옵션 변경**: 통합 구성요소 카드에서 `설정(Configure)`을 누르면 데이터 갱신 주기를 자유롭게 변경할 수 있습니다.

---

## 🤖 자동화(Automation) 작성 예제

거주 지역에 **기상특보가 발효되었을 때 스마트폰으로 경고 푸시 알림**을 보내는 자동화 예제입니다.

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

## 🛠️ 향후 로드맵

검토했지만 아직 구현하지 않은 후보입니다.

1. **해양관측(부이+연안) 연동**: `kma_buoy2.php`/`sea_obs.php`로 파고·수온·기압 실측치를 해상 Zone에 제공.
2. **해구별 예측 정보**: `marine_small_zone.php`/`marine_large_zone.php`로 유의파고·최대파주기·파향 등 +75시간 예측. 대/소해구 번호를 해상 Zone에 매핑하는 참조 자료가 추가로 필요합니다.
3. **영향예보 폭염/한파 위험수준 분포도 이미지**: `ifs_ilvl_dmap.php` — 전국 분포도 PNG를 이미지 엔티티로 추가할 수 있습니다.

---

## 📄 라이선스
This project is licensed under the MIT License - see the LICENSE file for details.
