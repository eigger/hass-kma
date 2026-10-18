# 사용자 가이드

기상청 APIhub 연동 홈어시스턴트 구성요소(`hass-kma`)의 상세 사용 설명서입니다.

## 아키텍처 개요

기상청 APIhub(apihub.kma.go.kr) 공식 개방형 API를 연동하여 기상 상태, 상세 관측값, 동네예보(단기/중기), 생활기상지수, 레이더/위성 영상 및 재난 기상특보를 제공합니다.

### 기기 구조

- **기상청 APIhub (Hub)**: API 연동 및 클라이언트 세션을 관리합니다. 전체 API에 대한 활용신청 상태(`binary_sensor.kma_activation_*`), 누적 에러 카운터(`sensor.kma_error_count_*`), 위성/레이더 이미지 엔티티 및 지진/태풍 센서가 등록됩니다.
- **Zone 기기**: 홈어시스턴트의 각 Zone(`zone.*`)별로 격자좌표(nx, ny)와 예보구역을 매핑하여 날씨(`weather.<zone_slug>`), 기상 관측/예보 센서(`sensor.<zone_slug>_*`), 지수 센서, 재난 특보 안전 센서(`binary_sensor.<zone_slug>_warning`)가 등록됩니다.
- **AWS 기기**: 지상관측 지점(AWS)을 추가 등록하여 초정밀 국지 1분 실측값(`sensor.aws_<지점번호>_*`)을 모니터링할 수 있습니다.

---

## 기상청 APIhub 활용신청 안내

통합 구성요소를 온전히 사용하려면 [기상청 APIhub 공식 웹사이트](https://apihub.kma.go.kr/)에 회원가입 후 아래 API들에 대해 **활용신청**을 승인받아야 합니다.

### 필수 및 권장 API 목록 (약 20종)

1. **동네예보(단기예보) 지점자료 조회** (`getVilageFcst`) — 시간별/일별 날씨 및 기본 기상 센서
2. **단기육상예보조회** (`fct_afs_dl.php`) — 중기 육상예보
3. **단기해상예보조회** (`fct_afs_do.php`) — 해상 날씨
4. **기상특보현황** (`wrn_now_data.php`) — 특보 발효 안전 센서
5. **예보구역 정보** (`fct_shrt_reg.php`) — API 키 정상 여부 검증용
6. **PM10(미세먼지) 관측자료 조회** (`kma_pm10.php`, 지상관측 > 황사관측(PM10))
7. **황사(PM10) 시간통계자료 조회** (`dst_pm10_hr.php`)
8. **생활기상지수 조회서비스** (`LivingWthrIdxServiceV3` — `getUVIdxV3`, `getAirDiffusionIdxV3`) — 자외선지수, 대기정체지수
9. **보건기상지수 조회서비스** (`HealthWthrIdxServiceV2` — `getOakPollenRiskIdxV2`, `getPinePollenRiskIdxV2`, `getWeedsPollenRiskndxV2`) — 꽃가루위험지수
10. **레이더영상 조회서비스** (`WthrRadarInfoService/getCompCappiQcdArea`) — 레이더 반사도 강수강도
11. **레이더 합성자료 다운로드** (`typ04/rdr_cmp_file.php`) — 레이더 이미지 엔티티
12. **천리안 2A호 위성 분포도 조회** (`typ03/nph-gk2a_img`) — 위성 적외/가시광선/단파적외/수증기 이미지 엔티티
13. **초단기 강수예측 그래픽 조회** (`typ03/nph-qpf_ana_img`) — 60분 강수예측 이미지 엔티티
14. **고해상도 지상관측** (`sfc_nc_var.php`, 특정지점 다중요소) — 실측 체감온도
15. **영향예보(발표현황) 조회** (`ifs_fct_pstt.php`) — 폭염/한파 영향예보
16. **적설관측자료 조회** (`kma_snow1.php`) — 실측 적설 센서
17. **지진정보(최근 발표 정보·속보) 조회** (`typ09/eqk/urlNewNotiEqk.do`) — 지진 통보 센서
18. **태풍정보(기상청 발표) 조회** (`typ_now.php`) — 태풍 정보 센서
19. **황사정보(위성영상) 조회서비스** (`YdstInfoService/getYdstSatlitImg`) — 위성 황사 영상
20. **[선택] 관측소 1분 자료 조회** (`typ01/cgi-bin/url/nph-aws2_min`) — AWS 관측소 서브엔트리 사용 시 필요 (미신청 시에도 예보 기능 정상 동작)

*기상정보(`wrn_inf_rpt.php`) 및 날씨해설(`wthr_cmt_rpt.php`)은 별도 활용신청 없이 기본 인증키로 조회됩니다.*

---

## 센서 상세 목록

| 기기 | 센서 ID (예시: Home 구역) | 센서 이름 | 사용 API | 예시 값 | 갱신 주기 |
| --- | --- | --- | --- | --- | --- |
| 날씨 | `weather.home` | 날씨 (Weather) | 동네예보 (`getVilageFcst`) | `sunny`(맑음) 등 HA 표준 condition | 10분 |
| Zone 기기 | `sensor.home_temperature` | 기온 | 동네예보 | `22.5` ℃ | 10분 |
| Zone 기기 | `sensor.home_humidity` | 습도 | 동네예보 | `65` % | 10분 |
| Zone 기기 | `sensor.home_wind_speed` | 풍속 | 동네예보 | `3.2` m/s | 10분 |
| Zone 기기 | `sensor.home_pop` | 강수확률 | 동네예보 | `30` % | 10분 |
| Zone 기기 | `sensor.home_precipitation` | 1시간 강수량 | 동네예보 | `0.0` / `5.0` mm | 10분 |
| Zone 기기 | `sensor.home_snowfall` | 1시간 예상 신적설 | 동네예보(SNO) | `0.0` / `2.0` cm | 10분 |
| Zone 기기 | `sensor.home_apparent_temperature` | 체감온도 | Steadman 공식 | `21.8` ℃ | 10분 |
| Zone 기기 | `sensor.home_dew_point` | 이슬점 | Magnus-Tetens 공식 | `15.2` ℃ | 10분 |
| Zone 기기 | `sensor.home_discomfort_index` | 불쾌지수 | 기온·습도 기반 | `72.3` | 10분 |
| Zone 기기 | `sensor.home_pm10` | 미세먼지(PM10) | PM10 관측자료 | `28` ㎍/㎥ | 10분 |
| Zone 기기 | `sensor.home_uv_index` | 자외선지수 | `LivingWthrIdxServiceV3` | `6` | 10분 |
| Zone 기기 | `binary_sensor.home_warning` | 기상특보 안전 센서 | 기상특보현황 | `off` / `on` | 10분 |
| Zone 기기 | `button.home_refresh` | 수동 새로고침 버튼 | 홈어시스턴트 동작 | 클릭 시 즉시 갱신 | 수동 |
| Hub 기기 | `image.kma_radar_image` | 레이더 합성 영상 | `typ04/rdr_cmp_file.php` | 상태=갱신시각, 화면=PNG | 10분 |
| Hub 기기 | `image.kma_satellite_image` | 위성(GK2A) 적외 영상 | `typ03/nph-gk2a_img` | 상태=갱신시각, 화면=PNG | 10분 |
| AWS 기기 | `sensor.aws_108_temperature` | 기온 (1분 실측) | 관측소 1분 자료 | `23.1` ℃ | 5분 (301초) |
| AWS 기기 | `sensor.aws_108_humidity` | 습도 (1분 실측) | 관측소 1분 자료 | `71.0` % | 5분 (301초) |

---

## 설정 옵션

**설정 → 기기 및 서비스 → 기상청 APIhub → 구성**에서 다음 옵션을 조정할 수 있습니다:

- **데이터 갱신 주기**: 기본 10분 (5분 ~ 180분 범위 설정 가능). AWS 관측소 실측값은 5분(301초) 고정입니다.
