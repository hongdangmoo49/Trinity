# Workflow Deliberation Result Flow

## 목적

`WorkflowEngine`에 남아 있는 deliberation result 적용 로직을 별도 flow로 분리해 엔진을 public facade에 가깝게 유지한다.

## 범위

- `WorkflowDeliberationResultFlow`를 추가한다.
- provider observation 기록, provider error gate 진입, structured blueprint 적용, consensus fallback 적용을 새 flow로 이동한다.
- `WorkflowEngine.mark_deliberation_result()`는 public entrypoint로 유지하고 새 flow에 위임한다.
- `WorkflowEngine._apply_structured_deliberation_result()`와 `_apply_consensus_deliberation_result()`를 제거한다.
- 패치 버전을 `1.0.408`로 올린다.

## 검증

- workflow engine focused 테스트를 통과해야 한다.
- provider error gate focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.408`을 출력해야 한다.
