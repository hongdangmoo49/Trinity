# Workflow Execution Persistence Direct Calls

## 목적

`WorkflowEngine._persist()` 의존도를 줄이기 위해 execution flow의 실행 이벤트 기록을 `WorkflowPersistenceFlow` 직접 호출로 전환한다.

## 범위

- execution run start 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- implementation requested 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- work package start/completion 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- execution batch planned/result recorded 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- 패치 버전을 `1.0.416`으로 올린다.

## 검증

- workflow execution focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.416`을 출력해야 한다.
