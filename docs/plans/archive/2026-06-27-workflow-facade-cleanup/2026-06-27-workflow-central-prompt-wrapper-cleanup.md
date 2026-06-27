# Workflow Central Prompt Wrapper Cleanup

## 목적

`WorkflowEngine`에 남아 있는 central prompt forwarding wrapper를 제거해 prompt 생성 책임을 `WorkflowCentralFlow`에 집중한다.

## 범위

- `WorkflowQuestionFlow`는 decision continuation prompt 생성 시 `WorkflowCentralFlow`를 직접 호출한다.
- `WorkflowLifecycleFlow`는 blueprint continuation prompt 생성 시 `WorkflowCentralFlow`를 직접 호출한다.
- `WorkflowEngine._build_decision_continuation_prompt()`, `_build_blueprint_continuation_prompt()`, `_target_workspace_prompt_block()`을 제거한다.
- 패치 버전을 `1.0.409`로 올린다.

## 검증

- workflow engine/question/lifecycle focused 테스트를 통과해야 한다.
- required smoke test를 통과해야 한다.
- `trinity --version`이 `1.0.409`를 출력해야 한다.
