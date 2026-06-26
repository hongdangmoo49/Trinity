# Workflow Lifecycle Flow 분리

- 브랜치: `refactor/workflow-lifecycle-flow`
- 버전: `1.0.308` -> `1.0.309`
- 대상: `src/trinity/workflow/engine.py`, `src/trinity/workflow/lifecycle_flow.py`

## 배경

`WorkflowEngine`에는 신규 workflow 시작, 기존 blueprint continuation, blueprint 실행 활성화, 실행용 blueprint freeze 같은 lifecycle 동작이 아직 직접 남아 있다.

이 로직은 workflow state machine의 핵심 entrypoint이지만, engine이 모든 세부 구현을 직접 들고 있으면 input routing, question flow, execution/review flow 분리 이후에도 engine이 계속 비대해진다. lifecycle 동작을 별도 helper로 옮기고 engine은 public API facade 역할을 유지한다.

## 개선안

1. `start`, `continue_from_blueprint`, `enable_execution_for_current_blueprint` 구현을 `WorkflowLifecycleFlow`로 이동한다.
2. `_should_carry_target_workspace_into_new_workflow`, `_freeze_current_blueprint` helper를 `WorkflowLifecycleFlow`로 이동한다.
3. `WorkflowEngine`의 기존 public/private 메서드는 호환 wrapper로 유지한다.
4. workflow start/continue/execution enable 이벤트와 반환 action payload는 변경하지 않는다.

## 범위

- workflow start 이벤트 payload 변경 없음
- blueprint continuation 분기 규칙 변경 없음
- execution enable guard와 message 변경 없음
- public CLI/TUI 동작 변경 없음

## 기대 효과

- workflow lifecycle 정책 변경 시 수정 위치가 명확해진다.
- `WorkflowEngine`은 public operation facade와 persistence/state 공통 기능에 더 가까워진다.
- 이후 남은 engine helper를 더 작게 분리하기 쉬워진다.
