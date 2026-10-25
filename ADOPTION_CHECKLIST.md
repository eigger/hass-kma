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
| 로컬 current / PASS | `HEAD` | 3.14.5 / HA 2026.10.2 / 0.13.373 | requirements=[] | `ruff check .`, `ruff format --check .` 통과, `pytest tests/components/kma/` 436 passed, `sync_badges.py --check` 통과 | 실제 KMA API 서버 |
| 로컬 최소 HA 2026.9.0 / PASS | `HEAD` | 3.14.5 / HA 2026.9.0 / 0.13.363 | requirements=[] | `pytest tests/components/kma/` 436 passed | 실제 KMA API 서버 |
| CI current / PASS | `7a3654e` | 3.14 / 2026.10.2 / 0.13.373 | requirements=[] | [Run 39124546627](https://github.com/eigger/hass-kma/actions/runs/39124546627) (lint 11s, test 1m14s 통과) | 실제 KMA API 서버 |
| CI 최소 HA 2026.9.0 / PASS | `7a3654e` | 3.14 / 2026.9.0 / 0.13.363 | requirements=[] | [Run 39124546627](https://github.com/eigger/hass-kma/actions/runs/39124546627) (lint 8s, test 49s 통과) | 실제 KMA API 서버 |

## 항목

| 규칙 ID | 상태 | 근거 / 남은 작업 |
|---|---|---|
| GOV-01 | PASS | `STANDARDS.md`에 전체 표준 SHA(`1524e4d71b0976812bb854f9e390b94408a96b52`), profile(`integration / ha`), 기본 브랜치(`main`), 지원 최소 HA(`2026.9.0`) 기록 |
| GOV-02 | PASS | 공통 workflow 호출을 `1524e4d71b0976812bb854f9e390b94408a96b52` 전체 SHA로 고정 (`.github/workflows/tests.yml`, `validate.yml`) |
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
| TEST-08 | PASS | Core 대응 구조(`tests/__init__.py`, `tests/conftest.py`, `tests/components/__init__.py`, `tests/components/kma/__init__.py`, `tests/components/kma/conftest.py` 및 테스트 17개 모듈) 배치 |
| TEST-02, TEST-03, TEST-09 | PASS | 실제 HA 통합(`hass` fixture, `MockConfigEntry`) 및 런타임/단위 테스트 436건 구축 |
| TEST-01, TEST-06, TEST-07 | PASS | 436개 테스트가 config flow, entry setup/unload/reload, weather/sensor/binary_sensor/button/image, 코디네이터 스로틀/오류/허브 집계, API 파싱, authKey 마스킹 등을 검증 |
| TEST-04, HACS-01(최소 검증) | PASS | 최소 HA 2026.9.0 (Python 3.14, HA 2026.9.0, pytest-homeassistant-custom-component 0.13.363) 환경에서 전체 436개 테스트 통과 |
| TEST-05, DEP-02, DEP-05 | PASS | current 환경 (Python 3.14, HA 2026.10.2, pytest-homeassistant-custom-component 0.13.373) 환경에서 전체 436개 테스트 통과 |
| DEP-01, DEP-06 | PASS | 의존성은 `requirements_test.txt`, `requirements_test_min.txt`, `requirements_lint.txt`로 명확히 분리, manifest `requirements: []` |
| DEP-07, CI-06 | PASS | `ruff==0.17.1` 고정 및 린트/포맷 클린 상태 검증 |
| DEP-03, DEP-04, CI-09, CI-10 | N/A | 외부 자체 upstream 패키지가 없어 자동 dependency-update workflow 해당 없음 |
| DEP-08 | N/A | 런타임 의존성 추가 없음 |
| HACS-01(구조), HACS-02 | PASS | 루트 `README.md`, `LICENSE`, `hacs.json` 및 `custom_components/kma` 구조 확인 |
| HACS-03, HACS-05 | PASS | HACS Custom 배지 사용, `custom_components/kma/brand/icon.png`(256×256) 및 `icon@2x.png`(512×512) 고해상도 에셋 준비 완료 |
| HACS-04 | PASS | `manifest.json` `"version": "2.1.2"` 및 최신 태그 일치 |
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
| REL-01, REL-02, REL-03, REL-05 | PASS | SemVer(2.1.2) 준수, 최소 HA 2026.9.0 보존, 표준 채택 분리 |
| REL-04 | N/A | 현행 유지보수 리포로 이전/중단 없음 |

## 남은 작업

1. GitHub PR #36 업데이트 및 원격 CI(Validate, Tests) 100% 통과 확인.
2. 실제 KMA API 서버 연동 및 실기기 대시보드 표시 검증 (단위 및 런타임 모의 테스트 완료).


## 2026-10-23 HACS ZIP and Downloads (scoped)

- Target base: `95cc95403cd1e5a08a17ddd5c5d42ac01a7a4e08`; reviewed release central: `fd4162c0b93fbe8e109f99c787773ae09ba157e1`.
- Scope: HACS-04/CI-11 release ZIP and DOC-03/05 Downloads replacing Analytics Usage. No release is created during this update.
- Local scoped validation: PASS — canonical badge check, no Analytics Usage, release metadata/caller contract, actionlint 1.7.12, native git diff --check, unchanged tracked integration/manifest/dependencies/tests.
- Actual archive build: PASS at `2bcdeb69045e906e64e43377a1d33ae250e4bed5`; `kma.zip`, 20 files, SHA256 `e69c85ecc90d2f27c32300aaa9a95d235cce45084be9879310eee604e6f3c8b6`. All archive members matched checkout bytes; manifest.json and __init__.py are at ZIP root. Final documentation-only follow-up preserves this integration tree. Windows Python 3.14.6; validation WSL Python 3.14.4/PyYAML 6.0.3/packaging 26.0.
- Full central integration checker: FAIL (pre-existing or unadopted contracts outside this scoped update; not treated as PASS). Findings:

```text
DOC-01 README.md: Exactly one ordered header marker pair required
DOC-01 README.ko.md: Exactly one ordered header marker pair required
HA-02 custom_components/kma/manifest.json: categories requires 1–3 actual product categories (HA-02 project policy)
HA-13 custom_components/__init__.py: Required contract file is missing
GOV-02 .github/workflows/tests.yml: standards-ref must equal the reviewed reusable workflow SHA
GOV-02 .github/workflows/tests.yml: standards-ref must equal the reviewed reusable workflow SHA
TEST-08 tests/__init__.py: must exist and be empty
TEST-08 tests/components/__init__.py: must exist and be empty
TEST-08 tests/components/kma/__init__.py: must exist and be empty
TEST-03 tests/conftest.py: must match the central template exactly
TEST-08 tests/components/kma/conftest.py: Exactly one ordered domain-fixtures marker pair required
CI-02 .github/workflows/tests.yml: name and events must match the central template (actual default branch)
CI-01 .github/workflows/validate.yml: central standards composite action pinned to full SHA required
```

- Existing CI workflows are preserved, except hass-kocom-smarthome where matching reviewed central references are synchronized. Existing support minimum and prior exceptions remain.
- Independent review and remote CI: tracked in this branch's pull request; merge requires resolved actionable findings and successful applicable checks. No real release upload, device or new real HA runtime validation is claimed by these local packaging checks.


## 2026-10-25 중앙 검사기 부분 갱신 검증

- 검토한 중앙 SHA: `1863343638014adb8a4001afc8fddc1a27dc500f`; 적용 시작 커밋: `0042dce6d7dc1812bc12f0a36086dc18c015e5a9`.
- 범위: 중앙 pin·standards-ref·검토 기준 기록 정합화 및 누락 standards job 추가. HA 구현·요구 버전은 유지합니다.
- 로컬: Python 3.14.5 / PyYAML 6.0.3, `python scripts/check_integration.py <target>` (검토한 중앙 source에서 실행): FAIL — 아래 미충족 항목을 확인했으며 성공으로 표시하지 않음.
- actionlint: PASS. PR CI·독립 리뷰 결과는 PR 링크와 check 결과를 확인합니다. 이 로컬 결과만으로 전체 채택 완료를 주장하지 않습니다.
- 수정 전에도 최신 검사기로 검사 시 13개 진단이 있었습니다. 이번 검사기가 드러내는 잔여 항목은 다음과 같습니다. 승인 예외나 실패 무시를 추가하지 않았습니다.

```text
DOC-01 README.md: Exactly one ordered header marker pair required
DOC-01 README.ko.md: Exactly one ordered header marker pair required
HA-02 custom_components/kma/manifest.json: categories requires 1–3 actual product categories (HA-02 project policy)
HA-13 custom_components/__init__.py: Required contract file is missing
TEST-08 tests/__init__.py: must exist and be empty
TEST-08 tests/components/__init__.py: must exist and be empty
TEST-08 tests/components/kma/__init__.py: must exist and be empty
TEST-03 tests/conftest.py: must match the central template exactly
TEST-08 tests/components/kma/conftest.py: Exactly one ordered domain-fixtures marker pair required
```
- 독립 리뷰: 별도 review_checker_rollout 담당자가 19개 리포의 workflow 69개·기존 job 100개를 구조 비교했습니다. 새 CI 회귀 지적 없음. 기존 job ID·입력·권한·지원 최소와 통합 코드 보존 및 새 standards job의 중앙 템플릿 일치 확인. 실행 변경 없는 이 기록 추가 전 작업 트리를 검토했습니다.


## 2026-10-25 CI 실패 보완 검증

- 이전 부분 갱신의 실패 진단을 실제 수정했습니다. 표준 README 관리 영역과 실제 설치 앵커를 중앙 렌더러로 적용하고, 제품 기능에 근거한 manifest categories 및 검토 근거를 기록했습니다. 기존 제품별 사용 설명·지원 최소·회귀 테스트를 보존합니다.
- 범위: custom_components namespace 파일, 정확한 중앙 루트 테스트 설정·빈 package 파일, domain fixture 관리 영역을 보완했습니다. 기존 HA fixture와 통신 mock은 유지합니다.
- 원격 Hassfest는 categories를 지원하는 검토 Core `ec18d8b25d1ee39aa8b85a72a170e42bee33228c`의 공식 validator 경로를 사용합니다. 통합 지원 최소를 올리지 않습니다.
- 현재 환경 실제 버전: `{"python": "3.14.5", "homeassistant": "2026.10.2", "pytest-homeassistant-custom-component": "0.13.373"}`. 각 리포 별도 격리 환경에서 의존성을 설치하고 pip check PASS.
- `python -m pytest tests/components/kma/ -q`: **472 passed**, skip 없음. 최신 중앙 검사기·actionlint·Ruff lint/format·git diff --check PASS.
- 최소 HA 조합과 최종 head 원격 CI는 이 PR의 갱신된 checks 결과로 확인합니다. 실물 기기·실제 외부 API/서버 검증은 수행하지 않았습니다.
- 독립 리뷰: 주 담당 root가 해당 작업 트리를 검토했습니다. 제품 분류의 실제 기능 근거, 기존 테스트 보존·의미 있는 파일 이동, fixture 역할 alias, 번역 및 README 관리 영역을 확인했으며 manifest 키 순서 지적 수정 후 추가 회귀 지적 없음.


### 2026-10-25 Standards workflow 분리 검증

- 분리 시작 커밋: `a630e43f868b9c800dc4edd3492208344c5e5567`; 검토 중앙 소스 `ca740d88b32fa5dcbc94c41fce2908450c76ed50` (중앙 PR #24). Validate는 HACS/Hassfest job을 그대로 유지하며 중앙 job만 standards.yml로 이동하고 표시 이름을 Standards로 변경합니다.
- 독립 리뷰: root 구현의 19개 리포에 대해 별도 fix_scale_atflee_ci 담당자가 Validate job 19개와 이동 job 19개의 YAML 정의를 비교했습니다. 파일 이동·표시 이름 외 실제 검사 단계·이벤트·권한·timeout·입력 변경 없음. 중앙 위치 인식 변경은 root가 별도 독립 리뷰했습니다.
- 로컬: 새 중앙 검사기·actionlint·diff 검사 PASS. 중앙 전체232개·관련38개 회귀 테스트와 양 배치19개 동등성 검사 PASS. 모든 대상 기본 브랜치의 branch protection·rulesets 조회에서 필수 검사 이름 설정이 없어 이름 변경으로 인한 대기 충돌 없음. 원격 CI는 이 PR의 최신 head에서 확인합니다.
- 검사 기준을 추가하거나 완화하지 않았으며 기존 inline 배치도 같은 기준으로 지원합니다. 실제 runtime·지원 최소·의존성은 이 파일 분리에서 변경하지 않습니다.
