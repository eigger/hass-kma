# 사용자 가이드

기상청 APIhub 연동 홈어시스턴트 구성요소(`hass-kma`)의 상세 사용 설명서입니다.

## 아키텍처 개요

기상청 APIhub(apihub.kma.go.kr) 공식 개방형 API를 연동하여 기상 상태, 상세 관측값, 동네예보(단기/중기), 생활기상지수, 레이더/위성 영상 및 재난 기상특보를 제공합니다.

### 기기 구조

- **기상청 APIhub (Hub)**: API 연동 및 클라이언트 세션을 관리합니다. 전체 API에 대한 활용신청 상태(`binary_sensor.kma_activation_*`) 및 누적 에러 카운터(`sensor.kma_error_count_*`)가 등록됩니다.
- **Zone 기기**: 홈어시스턴트의 각 Zone(`zone.*`)별로 격자좌표(nx, ny)와 예보구역을 매핑하여 날씨(`weather`), 기상 관측/예보 센서, 지수 센서, 재난 특보 안전 센서가 등록됩니다.
- **AWS 기기**: 지상관측 지점(AWS)을 추가 등록하여 초정밀 국지 실측값을 모니터링할 수 있습니다.

## 센서 상세 목록

| 기기 | 센서 ID | 센서 이름 | 사용 API | 예시 값 | 갱신 주기 |
| --- | --- | --- | --- | --- | --- |
| 기상청 날씨 | `weather.kma_<지역>` | 날씨 (Weather) | 동네예보 (`getVilageFcst`) | `sunny`(맑음) 등 HA 표준 condition | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_temperature` | 기온 | 동네예보 | `22.5` ℃ | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_humidity` | 습도 | 동네예보 | `65` % | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_wind_speed` | 풍속 | 동네예보 | `3.2` m/s | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pop` | 강수확률 | 동네예보 | `30` % | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pcp` | 1시간 강수량 | 동네예보 | `0.0` / `5.0` mm | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_snowfall` | 1시간 예상 신적설 | 동네예보(SNO) | `0.0` / `2.0` cm | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_apparent_temperature` | 체감온도 | Steadman 공식 | `21.8` ℃ | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_dew_point` | 이슬점 | Magnus-Tetens 공식 | `15.2` ℃ | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_discomfort_index` / `_grade` | 불쾌지수 / 등급 | 기온·습도 기반 | `72.3` / `보통` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_pm10` / `_grade` | 미세먼지(PM10) / 등급 | PM10 관측자료 | `28` ㎍/㎥ / `좋음` | 10분 |
| 기상청 날씨 | `sensor.kma_<지역>_uv_index` / `_grade` | 자외선지수 / 등급 | `LivingWthrIdxServiceV3` | `6` / `높음` | 10분 |
| 기상청 날씨 | `binary_sensor.kma_<지역>_warning` | 기상특보 안전 센서 | 기상특보현황 | `on`/`off` | 10분 |
| 각 Zone | `button.kma_<지역>_refresh` | 수동 새로고침 버튼 | 홈어시스턴트 동작 | 클릭 시 즉시 갱신 | 수동 |
| 각 Zone | `image.kma_radar_image` | 레이더 합성 영상 | `typ04/rdr_cmp_file.php` | 상태=갱신시각, 화면=PNG | 10분 |
| 각 Zone | `image.kma_satellite_image` | 위성(GK2A) 적외 영상 | `typ03/nph-gk2a_img` | 상태=갱신시각, 화면=PNG | 10분 |

## 설정 옵션

**설정 → 기기 및 서비스 → 기상청 APIhub → 구성**에서 다음 옵션을 조정할 수 있습니다:

- **데이터 갱신 주기**: 기본 10분 (5분 ~ 180분 범위 설정 가능).
