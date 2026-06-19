# 기상청 APIhub 연동 홈어시스턴트 통합 구성요소 (hass-kma)

[![GitHub Release](https://img.shields.io/github/v/release/eigger/hass-kma?style=flat-square)](https://github.com/eigger/hass-kma/releases)
[![License](https://img.shields.io/github/license/eigger/hass-kma?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=usage&suffix=%20installs&cacheSeconds=15600&query=%24.kma.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)

기상청 APIhub(apihub.kma.go.kr) 공식 텍스트 및 개방형 API를 연동하여 홈어시스턴트(Home Assistant)에 실시간 기상 상태, 상세 관측값, 중단기 예보, 생활기상지수 4종 및 재난 기상특보 경보를 연동해 주는 통합 구성요소입니다.

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
        *   **불쾌지수 (Discomfort Index)**: 기온, 습도 데이터를 바탕으로 실시간 계산 (속성에서 다국어 등급 `grade` 제공: `낮음(Low)`, `보통(Normal)`, `높음(High)`, `매우높음(Very High)`).
*   **생활기상지수 4종 센서**:
    *   기상 정보와 각 지수별 계산 공식을 결합하여, 유용한 생활 팁과 단계별 상태 정보를 속성과 값으로 제공합니다.
        *   **빨래 건조 지수 (Laundry Index)**: 기온, 습도, 풍속, 하늘 상태 및 강수 예보를 종합하여 계산.
        *   **세차 지수 (Car Wash Index)**: 향후 72시간 이내 비/눈 예보 상황을 스캔하여 세차 적합성 판별.
        *   **동파 가능 지수 (Freeze Risk Index)**: 향후 48시간 이내 최저 예보 기온을 바탕으로 동파 가능 단계 구분.
        *   **식중독 지수 (Food Poisoning Index)**: 기온과 상대습도를 이용한 식중독 예측 공식을 근사화하여 연산.
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
| 기상청 날씨 | `sensor.kma_<지역>_laundry_index` | 빨래 건조 지수 | 온도, 습도, 풍속, 강수예보 종합 연산 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_car_wash_index` | 세차 지수 | 72시간 내 강수 예보 분석 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_freeze_risk_index` | 동파 가능 지수 | 48시간 내 최저 예보기온 분석 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_food_poisoning_index` | 식중독 지수 | 온도 및 상대습도 기반 예측 연산 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_one_line_summary` | 한 줄 기상 요약 | 현재 날씨, 온도 극값, 강수 및 특보 정보 종합 | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_land_forecast_summary` | 육상 예보 요약 | 단기육상예보조회 (`fct_afs_dl`) | 매일 5시, 17시 |
| 기상청 날씨 | `sensor.kma_<지역>_marine_forecast_summary` | 해상 예보 요약 | 단기해상예보조회 (`fct_afs_do`) | 매일 5시, 17시 |
| 기상청 날씨 | `binary_sensor.kma_<지역>_warning` | 기상특보 안전 센서 | 기상특보현황 (`wrn_now_data`) | 10분 |

---

## 🔍 주요 센서 상세 정보

### 1. 한 줄 기상 요약 (`one_line_summary`)
전자라벨(ESL), E-Paper 등 제한된 공간을 가진 디스플레이에 기상 상황을 직관적으로 노출하기 위해 설계된 텍스트 센서입니다. 홈어시스턴트의 시스템 언어 설정(`ko`, `en` 등)에 맞춰 동적으로 메시지가 구성됩니다.
*   **출력 예시**:
    *   `맑음, 19.5°C (11.0°C/26.0°C)`
    *   `흐림, 15.0°C (12.0°C/18.0°C), 16시경 비 예보`
    *   `맑음, 29.0°C (20.0°C/31.0°C) [폭염주의보]`

### 2. 생활기상지수 4종 (`laundry`, `car_wash`, `freeze_risk`, `food_poisoning`)
각 센서의 상태값(State)은 0~100 사이의 수치를 반환하며, 상세 속성(Attributes)을 통해 현재 단계의 문자열(`grade`) 및 추천 가이드라인(`recommendation`)을 다국어로 함께 제공합니다.
*   **빨래 건조 지수**:
    *   0~100 수치 (단계: 매우 좋음, 좋음, 보통, 비추천)
    *   속성: `grade` (예: `매우 좋음`), `recommendation` (예: `야외 건조를 강력히 추천합니다.`)
*   **세차 지수**:
    *   0~100 수치 (단계: 매우 좋음, 좋음, 보류 권장, 세차 비추, 세차 금지)
    *   속성: `grade`, `recommendation`
*   **동파 가능 지수**:
    *   0~100 수치 (단계: 낮음, 보통, 높음, 매우 높음)
    *   속성: `grade`, `recommendation`
*   **식중독 지수**:
    *   0~100 수치 (단계: 관심, 주의, 경고, 위험)
    *   속성: `grade`, `recommendation`

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
3. 신청 완료 후 발급받은 **인증키(authKey)**를 준비합니다.

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
4. **기타 레이더/위성 이미지 연동 (`camera`)**: 천리안 2A 위성 이미지나 비구름 레이더 영상을 홈어시스턴트에 카메라 엔티티로 매핑.

---

## 📄 라이선스
This project is licensed under the MIT License - see the LICENSE file for details.
