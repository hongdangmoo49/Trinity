# Provider Error Gate Flow Reuse

## 배경

`WorkflowEngine.mark_deliberation_result`는 provider error gate flow를 `should_open`과 `open` 호출마다 새로 만들고 있었다. 현재 flow 객체는 session과 callback을 묶는 얇은 stateful helper이므로 동작 문제는 없지만, 한 흐름 안에서는 같은 flow 인스턴스를 재사용하는 편이 책임 경계가 더 분명하다.

## 목표

- `mark_deliberation_result`에서 `ProviderErrorGateFlow`를 한 번만 생성해 재사용한다.
- provider error gate의 open/retry/continue/stop 동작은 변경하지 않는다.
- 패치 버전을 `1.0.329`로 올린다.

## 변경 계획

1. `provider_gate = self._provider_error_gate_flow()` 지역 변수를 도입한다.
2. `provider_gate.should_open(result)`와 `provider_gate.open(result)`를 호출한다.
3. provider error gate focused 테스트와 전체 테스트로 회귀를 확인한다.

## 검증

- `git diff --check`
- `uv run trinity --version`
- `uv run pytest -q tests/test_provider_error_gate_flow.py tests/test_workflow_engine.py`
- `uv run pytest -q`
