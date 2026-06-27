# Workflow Targeting Wrapper Cleanup

## 목적

`WorkflowEngine`에 남아 있는 targeting/model override forwarding wrapper를 제거해 agent targeting 책임을 `WorkflowTargetingFlow`에 집중한다.

## 범위

- `WorkflowQuestionFlow`와 `WorkflowLifecycleFlow`가 `WorkflowTargetingFlow`를 직접 호출한다.
- `ProviderErrorGateFlow` 구성 시 model override 정규화 콜백으로 `WorkflowTargetingFlow.normalized_model_overrides()`를 직접 전달한다.
- 사용되지 않는 `WorkflowEngine._effective_target_agents()`, `_normalized_model_overrides()`, `_can_continue_existing_blueprint()`, `_should_carry_target_workspace_into_new_workflow()`를 제거한다.
- 패치 버전을 `1.0.411`로 올린다.

## 검증

- workflow engine/question/lifecycle/provider gate focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.411`을 출력해야 한다.
