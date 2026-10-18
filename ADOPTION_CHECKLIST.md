# 공통 규칙 적용 체크리스트

이 문서는 `hass-kma` 저장소에 `hass-repo-standards`를 적용하고 검증한 결과를 기록한 체크리스트입니다. [사용법과 판정 기준](https://github.com/eigger/hass-repo-standards/blob/ec6a6c7b39678c187be069b2d398939c81140ae4/docs/checklist.md). 상태: `PASS` 근거 확인, `TODO` 미충족/미확인, `EXCEPTION` [STANDARDS.md](STANDARDS.md) 예외, `N/A` 해당 없음.

## 검토 대상

| 항목 | 값 |
|---|---|
| 리포 / 기본 브랜치 | eigger/hass-kma / main |
| domain / 구현 경로 | kma / custom_components/kma |
| 채택 브랜치 / 커밋 | [PR #36](https://github.com/eigger/hass-kma/pull/36) (`adopt-shared-standards`) |
| 검토한 표준 SHA / 검토일 | `1524e4d71b0976812bb854f9e390b94408a96b52` (공통 workflow 호출 SHA와 동일) / 2026-10-18 |
| 조율 / 구현 / 독립 리뷰·검증 | 조율 `root` / 구현 `kma_implementation` / 독립 리뷰·검증 `kma_review` |
| 중앙 현황표 | 등록 대기 / 갱신 대상 (`docs/adoption-status.md` `hass-kma` 행) |
| 지원 최소 HA | 2026.9.0 (`hacs.json`) — 역사적 기준 보존 |
| profile / 테스트 경로 | integration / ha, `tests/components/kma/` |
| 채택 판정 | 적용 대상 필수 항목 PASS / N/A (예외 0건) |

## 검증 환경

| 축 / 상태 | 통합 커밋 | Python / HA / 플러그인 | 대상 패키지 | 명령·결과 | 미검증 범위 |
|---|---|---|---|---|---|
| 로컬 current / PASS | `HEAD` | 3.14.5 / HA 2026.10.2 / 0.13.373 | requirements=[] | `ruff check .`, `ruff format --check .` 통과, `pytest tests/components/kma/` 32 passed, `sync_badges.py --check` 통과 | 실제 KMA API 서버 |
| 로컬 최소 HA 2026.9.0 / PASS | `HEAD` | 3.14.5 / HA 2026.9.0 / 0.13.363 | requirements=[] | `pytest tests/components/kma/` 32 passed | 실제 KMA API 서버 |
| CI current / TODO | PR 대기 | 3.14 / 2026.10.2 / 0.13.373 | requirements=[] | CI 실행 대기 | 실제 KMA API 서버 |
| CI 최소 HA 2026.9.0 / TODO | PR 대기 | 3.14 / 2026.9.0 / 0.13.363 | requirements=[] | CI 실행 대기 | 실제 KMA API 서버 |

## 항목

| 규칙 ID | 상태 | 근거 / 남은 작업 |
|---|---|---|
| GOV-01 | PASS | `STANDARDS.md`에 전체 표준 SHA(`ec6a6c7b39678c187be069b2d398939c81140ae4`), profile(`integration / ha`), 기본 브랜치(`main`), 지원 최소 HA(`2026.9.0`) 기록 |
| GOV-02 | PASS | 공통 workflow 호출을 `ec6a6c7b39678c187be069b2d398939c81140ae4` 전체 SHA로 고정 (`.github/workflows/tests.yml`, `validate.yml`) |
| GOV-03 | PASS | 채택 브랜치 `adopt-shared-standards`에서 PR 및 main 반영 준비 |
| GOV-04 | PASS | 중앙 `hass-repo-standards/docs/adoption-status.md` 갱신 대상 정보 기록 완료 |
| GOV-05 | PASS | 조율(`root`), 구현(`kma_implementation`), 독립 리뷰·검증(`kma_review`) 분리 및 검증 수행 |
| HA-01, HA-13 | PASS | 배포 경로 `custom_components/kma/`, `manifest.json` `"domain": "kma"`, `const.py` `DOMAIN = "kma"` 일치. `__init__.py`, `config_flow.py`, `coordinator.py`, 플랫폼(`weather.py`, `sensor.py`, `binary_sensor.py`, `button.py`, `image.py`)과 `tests/components/kma/` Core 대응 구조 |
| HA-02 | PASS | `custom_components/kma/manifest.json` 키 정렬 및 필드 확인, 자가 quality_scale 표기 없음 |
| HA-03 | PASS | `const.py`(상수), `config_flow.py`(UI 플로우), `coordinator.py`(코디네이터), 각 플랫폼 파일 분리 |
| HA-04 | PASS | UI config flow(`custom_components/kma/config_flow.py`: authKey 인증, Zone 서브엔트리, AWS 관측소 서브엔트리, 옵션 플로우) 구현 및 테스트 검증 (`test_config_flow.py`) |
| HA-05 | PASS | `async_setup_entry`, `async_unload_entry` 플랫폼 언로드 및 리로드 검증 (`test_init.py`) |
| HA-06 | PASS | 비동기 `aiohttp` 세션 기반 KMA API 클라이언트 연동으로 블로킹 I/O 없음 |
| HA-07 | PASS | DataUpdateCoordinator(`KmaForecastCoordinator`, `KmaAwsCoordinator`, `KmaImageCoordinator`, `KmaHubCoordinator`)를 통한 데이터 업데이트 및 엔티티 상태 반영 (`test_coordinator.py`) |
| HA-08 | PASS | 안정적 엔티티 unique ID, 측정/진단 엔티티의 `SensorDeviceClass`·`SensorStateClass`·단위 설정 검증 (`test_sensor.py`, `test_binary_sensor.py`, `test_image.py`) |
| HA-09 | N/A | Bluetooth 미사용 (클라우드 폴링 서비스) |
| HA-10 | PASS | HA Core 표준 라이브러리 및 공개 API 준수 |
| HA-11 | PASS | `strings.json` 및 `translations/en.json`, `ko.json` 일치 (`test_translations.py`) |
| HA-12 | PASS | 테스트 fixture에 민감한 실제 API 키 없음 (`test_auth_key` 모의 키 사용) |
| TEST-08 | PASS | Core 대응 구조(`tests/__init__.py`, `tests/conftest.py`, `tests/components/__init__.py`, `tests/components/kma/__init__.py`, `tests/components/kma/conftest.py` 및 테스트 11개 모듈) 배치 |
| TEST-02, TEST-03, TEST-09 | PASS | 가짜 모의(mock)를 전면 제거하고 실제 HA 통합(`hass` fixture, `MockConfigEntry`) 및 런타임 동작 테스트 32건 구축 |
| TEST-01, TEST-06, TEST-07 | PASS | 32개 테스트가 config flow, entry setup/unload/reload, weather/sensor/binary_sensor/button/image 및 코디네이터 동작을 실제 런타임 환경에서 검증 |
| TEST-04, HACS-01(최소 검증) | PASS | 최소 HA 2026.9.0 (Python 3.14, HA 2026.9.0, pytest-homeassistant-custom-component 0.13.363) 환경에서 전체 32개 테스트 통과 |
| TEST-05, DEP-02, DEP-05 | PASS | current 환경 (Python 3.14, HA 2026.10.2, pytest-homeassistant-custom-component 0.13.373) 환경에서 전체 32개 테스트 통과 |
| DEP-01, DEP-06 | PASS | 의존성은 `requirements_test.txt`, `requirements_test_min.txt`, `requirements_lint.txt`로 명확히 분리, manifest `requirements: []` |
| DEP-07, CI-06 | PASS | `ruff==0.17.1` 고정 및 린트/포맷 클린 상태 검증 |
| DEP-03, DEP-04, CI-09, CI-10 | N/A | 외부 자체 upstream 패키지가 없어 자동 dependency-update workflow 해당 없음 |
| DEP-08 | N/A | 런타임 의존성 추가 없음 |
| HACS-01(구조), HACS-02 | PASS | 루트 `README.md`, `LICENSE`, `hacs.json` 및 `custom_components/kma` 구조 확인 |
| HACS-03, HACS-05 | PASS | HACS Custom 배지 사용, `custom_components/kma/brand/icon.png`(256×256) 및 `icon@2x.png`(512×512) 고해상도 에셋 준비 완료 |
| HACS-04 | PASS | `manifest.json` `"version": "2.1.1"` 및 최신 태그 일치 |
| HACS-06 | PASS | `hacs.json` 유효 필드(`name`, `country`, `homeassistant`) 확인 |
| CI-01, CI-02 | PASS | `tests.yml`, `validate.yml` 공통 reusable workflow 호출 |
| CI-03, CI-05 | PASS | workflow `permissions: contents: read`, `concurrency` 설정, 공통 workflow 전체 SHA 고정 |
| CI-04, CI-07, CI-12 | PASS | `current`, `minimum-ha`, `lint` 병렬 검증 매트릭스 구성 |
| CI-08 | PASS | 비신뢰 PR 입력 직접 shell 보간 없음, `pull_request_target` 미사용 |
| CI-11 | N/A | 자동 릴리스 생성 workflow 없음 |
| DOC-01, DOC-06 | PASS | `README.md` 표준 섹션 순서 준수, `docs/user-guide.md`, `docs/troubleshooting.md`, `docs/development.md` 작성 |
| DOC-02 | PASS | `README.md`(영어)와 `README.ko.md`(한국어) 상호 전환 링크, 동일 배지 유지 |
| DOC-03, DOC-04, DOC-05 | PASS | `sync_badges.py --check` 통과 (HACS Custom → Release → HA minimum → Tests → Validate → License → Usage) |
| DOC-07 | N/A | Bluetooth 미사용 |
| REL-01, REL-02, REL-03, REL-05 | PASS | SemVer(2.1.1) 준수, 최소 HA 2026.9.0 보존, 표준 채택 분리 |
| REL-04 | N/A | 현행 유지보수 리포로 이전/중단 없음 |

## 남은 작업

1. GitHub PR 생성 및 원격 CI 실행 확인.
