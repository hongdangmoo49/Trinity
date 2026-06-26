# Workflow Engine Persist Wrapper Removal

## 목적

`WorkflowEngine._persist()` forwarding wrapper를 제거해 workflow event persistence 진입점을 `WorkflowPersistenceFlow`로 단일화한다.

## 범위

- `WorkflowEngine.set_state()`가 `WorkflowPersistenceFlow.persist()`를 직접 호출한다.
- `ExecutionRecoveryFlow`와 `ProviderErrorGateFlow` 생성 시 persistence callback으로 `WorkflowPersistenceFlow.persist()`를 직접 전달한다.
- `WorkflowEngine._persist()`를 제거한다.
- 패치 버전을 `1.0.419`로 올린다.

## 검증

- workflow engine/recovery/provider gate focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.419`를 출력해야 한다.
