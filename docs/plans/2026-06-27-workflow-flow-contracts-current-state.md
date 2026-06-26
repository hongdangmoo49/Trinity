# Workflow Flow Contracts Current State

## 목적

최근 facade 정리 PR 이후 `docs/development/workflow-flow-contracts.md`가 현재 구현과 어긋난 부분을 최신화한다.

## 범위

- `WorkflowDeliberationResultFlow`와 `WorkflowPersistenceFlow`를 authoritative flow 목록에 추가한다.
- persistence invariant를 `engine._persistence_flow().persist()` 기준으로 갱신한다.
- targeting/model override invariant를 `WorkflowTargetingFlow` 기준으로 갱신한다.
- 제거된 `WorkflowEngine._persist()` wrapper 참조를 개발 문서에서 제거한다.
- 패치 버전을 `1.0.420`으로 올린다.

## 검증

- 문서 내 제거된 wrapper 참조가 남지 않아야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.420`을 출력해야 한다.
