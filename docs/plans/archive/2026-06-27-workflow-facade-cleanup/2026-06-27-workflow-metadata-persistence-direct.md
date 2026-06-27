# Workflow Metadata Persistence Direct Calls

## 목적

`WorkflowEngine._persist()` 의존도를 줄이기 위해 독립 metadata flow들이 `WorkflowPersistenceFlow`를 직접 사용하도록 전환한다.

## 범위

- central conversation 기록을 `engine._persistence_flow().persist()`로 전환한다.
- quality signal 기록을 `engine._persistence_flow().persist()`로 전환한다.
- target workspace 선택/해제를 `engine._persistence_flow().persist()`로 전환한다.
- provider metadata observation 기록을 `engine._persistence_flow().persist()`로 전환한다.
- 패치 버전을 `1.0.414`로 올린다.

## 검증

- workflow engine/resource/quality focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.414`를 출력해야 한다.
