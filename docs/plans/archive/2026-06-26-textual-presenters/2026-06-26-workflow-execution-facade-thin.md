# Workflow Execution Facade Thinning

## 배경

`WorkflowExecutionFlow`가 실행 scheduling/result/finalization 책임을 가지게 된 뒤 `WorkflowEngine`에는 호출되지 않는 private execution wrapper가 남아 있었다.

- `_preview_execution_scope`
- `_finalize_execution_state`

검색 결과 두 method는 정의 외 호출부가 없으며, `ExecutionScope` import도 이 wrapper 때문에만 남아 있었다.

## 목표

- 미사용 execution private wrapper를 제거한다.
- 공개 실행 API와 `WorkflowExecutionFlow` 동작은 변경하지 않는다.
- 패치 버전을 `1.0.330`으로 올린다.

## 변경 계획

1. `_preview_execution_scope`, `_finalize_execution_state`를 삭제한다.
2. 불필요해진 `ExecutionScope` import를 삭제한다.
3. execution/workflow focused 테스트와 전체 테스트로 회귀를 확인한다.

## 검증

- `git diff --check`
- `uv run trinity --version`
- `uv run pytest -q tests/test_workflow_execution_flow.py tests/test_workflow_engine.py`
- `uv run pytest -q`
