# Workflow Recovery Facade Thinning

## 배경

`ExecutionRecoveryFlow`가 도입된 뒤 `WorkflowEngine`에는 과거 내부 helper와의 호환을 위한 private wrapper가 일부 남아 있었다. 검색 결과 다음 method들은 정의만 있고 호출부가 없었다.

- `_normalize_execution_retry_selector`
- `_execution_retry_disabled_reason`
- `_matches_execution_retry_selector`
- `_persist_recovery_action`
- `_packages_with_status`
- `_last_workflow_event`

공개 API인 `detect_interrupted_execution`, `execution_recovery_summary`, `build_execution_retry_plan`, `prepare_execution_retry`, `retry_interrupted_execution`, `mark_interrupted_execution`, `abort_interrupted_execution`은 유지한다.

## 목표

- WorkflowEngine이 recovery flow의 facade 역할만 하도록 미사용 private wrapper를 제거한다.
- `ExecutionRecoveryFlow`의 실제 retry/recovery 로직은 변경하지 않는다.
- 패치 버전을 `1.0.328`로 올린다.

## 변경 계획

1. `WorkflowEngine`에서 미사용 private recovery wrapper를 삭제한다.
2. recovery flow 관련 테스트와 전체 테스트로 회귀를 확인한다.

## 검증

- `git diff --check`
- `uv run trinity --version`
- `uv run pytest -q tests/test_workflow_engine.py tests/test_textual_app.py`
- `uv run pytest -q`
