# Workflow Lifecycle/Question Persistence Direct Calls

## 목적

`WorkflowEngine._persist()` 의존도를 줄이기 위해 lifecycle/question flow의 사용자 입력 이벤트 기록을 `WorkflowPersistenceFlow` 직접 호출로 전환한다.

## 범위

- workflow start 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- workflow continue 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- execution enabled 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- question decision 기록을 `engine._persistence_flow().persist()`로 전환한다.
- 패치 버전을 `1.0.415`로 올린다.

## 검증

- workflow engine/question/lifecycle focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.415`를 출력해야 한다.
