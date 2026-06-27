# Workflow Lifecycle/Question Wrapper Cleanup

## 목적

`WorkflowEngine`에 남아 있는 lifecycle/question forwarding wrapper를 제거해 각 flow가 자기 책임을 직접 사용하도록 정리한다.

## 범위

- `WorkflowLifecycleFlow`가 decision id 생성 시 `WorkflowQuestionFlow`를 직접 호출한다.
- 사용되지 않는 `WorkflowEngine._decision_for_question()`을 제거한다.
- 사용되지 않는 `WorkflowEngine._freeze_current_blueprint()` forwarding wrapper를 제거한다.
- `WorkflowEngine._next_decision_id()` forwarding wrapper를 제거한다.
- 패치 버전을 `1.0.407`로 올린다.

## 검증

- workflow engine focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.407`을 출력해야 한다.
