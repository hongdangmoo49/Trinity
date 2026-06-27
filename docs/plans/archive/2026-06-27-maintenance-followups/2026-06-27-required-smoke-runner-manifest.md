# Required Smoke Runner Manifest

## 목적

PR CI에서 돌리는 필수 smoke 테스트 목록을 로컬에서도 쉽게 확인하고, manifest 품질 문제를 빠르게 발견할 수 있게 한다.

## 범위

- `scripts/run_required_smoke_tests.py`에 `--list` 옵션을 추가한다.
- `.github/required-smoke-tests.txt`의 중복 항목을 명시적으로 실패 처리한다.
- runner 동작을 단위 테스트로 고정한다.
- CI workflow 자체와 required smoke 목록은 변경하지 않는다.
- 패치 버전을 `1.0.442`로 올린다.

## 비목표

- 필수 smoke 테스트 범위를 줄이거나 늘리지 않는다.
- GitHub Actions matrix, wheel smoke, PyPI publish workflow는 변경하지 않는다.
- 전체 테스트/야간 테스트 전략은 별도 항목으로 다룬다.

## 검증

- required smoke runner 단위 테스트를 통과해야 한다.
- `--list`가 manifest 순서대로 테스트 경로를 출력해야 한다.
- 중복 manifest 항목이 명확한 오류로 실패해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.442`를 출력해야 한다.
