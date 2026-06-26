# Workflow Post-Review Persistence Direct Calls

## 목적

`WorkflowEngine._persist()` 의존도를 줄이기 위해 post-review flow의 후속작업 이벤트 기록을 `WorkflowPersistenceFlow` 직접 호출로 전환한다.

## 범위

- post-review item extraction/acceptance 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- follow-up request 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- auto replan skipped/queued 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- 패치 버전을 `1.0.418`로 올린다.

## 검증

- workflow post-review focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.418`을 출력해야 한다.
