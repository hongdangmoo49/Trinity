# Workflow Persistence Flow

## 목적

`WorkflowEngine`에 남아 있는 session save, event append, timestamp 보정, 초기 session load/create 책임을 별도 flow로 분리한다.

## 범위

- `WorkflowPersistenceFlow`를 추가한다.
- `WorkflowEngine.save()`와 `_persist()`는 기존 호출 표면을 유지하되 새 flow에 위임한다.
- `WorkflowEngine._event_timestamp()`와 `_load_or_create()` 구현을 제거한다.
- 기존 event payload 구조와 저장 순서는 유지한다.
- 패치 버전을 `1.0.412`로 올린다.

## 검증

- workflow persistence focused 테스트를 통과해야 한다.
- workflow engine focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.412`를 출력해야 한다.
