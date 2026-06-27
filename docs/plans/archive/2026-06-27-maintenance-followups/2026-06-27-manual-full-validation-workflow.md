# Manual Full Validation Workflow

## 목적

PR 필수 CI는 focused required smoke로 유지하면서, 릴리스 후보나 큰 리팩터링 전에는 GitHub Actions에서 full test suite를 수동 실행할 수 있게 한다.

## 범위

- `.github/workflows/full-validation.yml`을 추가한다.
- workflow는 `workflow_dispatch` 전용으로 실행한다.
- Ubuntu/Python 3.12에서 `uv run pytest -q`를 실행한다.
- 유지보수 전략 문서의 Full Validation 기준을 수동 workflow 기준으로 최신화한다.
- 패치 버전을 `1.0.453`으로 올린다.

## 비목표

- PR required smoke gate를 full suite로 바꾸지 않는다.
- schedule/nightly 실행은 이번 PR에서 추가하지 않는다.
- publish workflow의 required smoke preflight는 변경하지 않는다.

## 검증

- workflow YAML이 기존 CI에서 checkout/setup 단계와 충돌하지 않아야 한다.
- focused smoke와 required smoke가 통과해야 한다.
- `trinity --version`이 `1.0.453`을 출력해야 한다.
