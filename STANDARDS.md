# 적용한 공통 규칙

- 표준: https://github.com/eigger/hass-repo-standards/tree/main
- 참조 커밋 SHA: `1524e4d71b0976812bb854f9e390b94408a96b52`
- 채택일: 2026-10-18
- profile: integration / ha (실제 HA fixture·통합 로딩 필수)
- 적용 점검표: [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md)
- 중앙 현황표: https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md
- 조율 / 구현 / 독립 리뷰·검증 담당: 조율 `root` / 구현 `kma_implementation` / 독립 리뷰·검증 `kma_review`
- 중앙 현황 갱신일: 2026-10-18
- 실제 기본 브랜치: main
- 테스트 경로: tests/components/kma/
- 변경 전 지원 최소 HA / 선언 근거: 2026.9.0 / `hacs.json`
- 적용 후 지원 최소 HA: 2026.9.0 (변경 없음, 역사적 기준 보존)
- current HA 테스트 환경: Python 3.14.5, pytest-homeassistant-custom-component 0.13.373, HA 2026.10.2
- 최소 HA 검증 환경: Python 3.14.5, pytest-homeassistant-custom-component 0.13.363, HA 2026.9.0
- 최소 package 검증: 없음 (requirements=[])

## 예외

현재 등록된 예외 없음.

- Reviewed release standards SHA: `fd4162c0b93fbe8e109f99c787773ae09ba157e1`


## 2026-10-23 ZIP release and Downloads update

Base commit: `95cc95403cd1e5a08a17ddd5c5d42ac01a7a4e08`. HACS remains Custom. `hacs.json` now selects `kma.zip`; publishing the next release builds and attaches that integration ZIP through the pinned central action. Analytics Usage is replaced by Downloads. The archive contains tracked integration files at its root. No existing release/tag/assets are modified.

Implementation and review: root; generated release caller reuses the independently reviewed central ZIP contract. Support minimum, manifest, code, dependencies, README body and prior adoption exceptions are preserved. Verification evidence is recorded in ADOPTION_CHECKLIST.md; this scoped update does not establish full standards compliance.

## 2026-10-24 HACS Default badges

HACS Default listing confirmed in hacs/default `integration` (see `hacs_default_evidence` in `.hass-standards.json`). The HACS badge becomes Default, the Downloads badge uses the official HACS data (`HACS Downloads`) in place of the GitHub release-asset Downloads badge, and both READMEs gain the My HACS install badge. The HACS value is no longer Custom; the 2026-10-23 entry above is historical. `hacs.json`, ZIP release, manifest, code and support minimum are unchanged.
