# Workflow Review Persistence Direct Calls

## 목적

`WorkflowEngine._persist()` 의존도를 줄이기 위해 review flow의 리뷰/repair 이벤트 기록을 `WorkflowPersistenceFlow` 직접 호출로 전환한다.

## 범위

- review package planned 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- repair requested/recovery action/repair blocked 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- repair accepted/stopped 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- review result recorded 이벤트 기록을 `engine._persistence_flow().persist()`로 전환한다.
- 패치 버전을 `1.0.417`로 올린다.

## 검증

- workflow review focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.417`을 출력해야 한다.
