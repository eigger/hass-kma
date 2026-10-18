# 기상청 APIhub 연동 홈어시스턴트 구성요소

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-kma?style=flat)](https://github.com/eigger/hass-kma/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat)](#설치)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202026.9.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-kma/tests.yml?branch=main&style=flat&label=Tests)](https://github.com/eigger/hass-kma/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-kma/validate.yml?branch=main&style=flat&label=Validate)](https://github.com/eigger/hass-kma/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-kma?style=flat)](LICENSE)
[![Analytics reporting installs](https://img.shields.io/badge/dynamic/json?style=flat&color=41BDF5&label=Usage&query=%24.kma.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)](https://analytics.home-assistant.io/)
<!-- hass-standards:badges:end -->

[English](README.md) | 한국어

기상청 APIhub(apihub.kma.go.kr) 공식 개방형 API를 연동하여 홈어시스턴트(Home Assistant)에 실시간 기상 상태, 상세 관측값, 동네예보(단기/중기), 생활기상지수, 레이더/위성 영상 및 재난 기상특보를 제공하는 통합 구성요소입니다.

## 주요 기능

- **표준 날씨 엔티티**: 시간별 예보(3일간) 및 일별 예보(최대 10일간).
- **상세 기상 및 환경 센서**: 기온, 습도, 풍속, 강수확률, 1시간 강수량, 미세먼지(PM10), 자외선지수, 불쾌지수, 식중독지수.
- **재난 기상특보 안전 센서**: 호우, 대설, 강풍, 폭염, 한파, 태풍 등 특보 발효 시 즉시 `on` 상태 전환.
- **영상 엔티티**: 레이더 합성 강수영상 및 GK2A 천리안 2A호 위성 적외/가시광선 영상.
- **상태 진단**: API 활용신청 여부 및 호출 오류 누적 카운터 제공.

## 빠른 시작

1. [기상청 APIhub](https://apihub.kma.go.kr/)에서 인증키를 발급받습니다.
2. 홈어시스턴트에서 **설정 → 기기 및 서비스 → 통합구성요소 추가**로 이동합니다.
3. **기상청 APIhub**를 검색하여 선택합니다.
4. 발급받은 인증키를 입력하고 원하는 Zone을 구성합니다.

## 설치

### HACS 설치 (권장)

1. [HACS](https://hacs.xyz/)가 설치되어 있는지 확인합니다.
2. HACS의 사용자 지정 저장소(Custom repository)에 본 저장소 URL을 `Integration` 범주로 추가합니다.
3. `기상청 APIhub`를 검색하여 **다운로드**합니다.
4. 홈어시스턴트를 재시작합니다.

### 수동 설치

1. 최신 릴리스 압축 파일을 다운로드합니다.
2. `custom_components/kma` 폴더를 홈어시스턴트 설정 디렉토리의 `custom_components/` 아래로 복사합니다.
3. 홈어시스턴트를 재시작합니다.

## 문서

- [상세 사용자 가이드](docs/ko/user-guide.md)
- [문제 해결 가이드](docs/ko/troubleshooting.md)
- [개발 및 테스트 안내](docs/development.md)

## 문의 및 라이선스

- 버그 신고 및 기능 제안은 [GitHub Issues](https://github.com/eigger/hass-kma/issues)에 등록해 주세요.
- 본 프로젝트는 [MIT 라이선스](LICENSE)를 따릅니다.
