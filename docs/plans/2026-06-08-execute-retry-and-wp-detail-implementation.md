# Execute Retry and WP Detail Implementation

작성일: 2026-06-08

브랜치: `codex/execution-resume-recovery-design`

대상 버전: `0.11.0`

상태: 구현 완료

## 요약

`/execute-retry`를 독립 slash command로 추가하고, 실행 실패/차단/중단 상태의
work package를 사용자가 다시 선택해 새 execution run으로 재시도할 수 있게 했다.

Textual Workbench에서는 `/execute-retry` 입력 시 중앙 modal을 띄우며, modal 안에서
`all`, `failed`, `blocked`, `interrupted`, `custom` 범위를 고를 수 있다. `custom`
범위에서는 같은 modal의 work package 목록 옆에 checkbox가 표시된다.

Execution 화면은 기존 DataTable 요약 대신 row list로 변경되었고, 각 work package row에
`View` 버튼이 추가되었다. 이 버튼은 package objective, scope, dependency, expected files,
acceptance criteria, repair notes, 마지막 실행 결과를 보여주는 상세 modal을 연다.

## 구현 내용

### Retry Engine

- `ExecutionRetryPlan`, `RetrySkip`을 추가했다.
- `WorkflowEngine.build_execution_retry_plan()`은 재시도 후보를 비파괴적으로 계산한다.
- `WorkflowEngine.prepare_execution_retry()`는 선택된 package만 `pending`으로 되돌리고
  기존 execution result와 artifact 기록은 삭제하지 않는다.
- `WorkflowEngine.pending_execution_package_ids()`와 `begin_execution(package_ids=...)`로
  이번 execution run에서 dispatch할 package id를 명시한다.
- retry execution run은 `retry_selector`, `retry_packages`, `retry_requested_at` metadata를
  유지한다.
- 기존 `/execute retry` 경로는 compatibility wrapper로 유지하되 새 retry planner를 사용한다.

### Textual UX

- `/execute-retry` command를 registry에 추가했다.
- Textual command router는 `/execute-retry` 입력 시 즉시 실행하지 않고
  `ExecutionRetryModal`을 연다.
- target workspace가 없으면 retry 선택을 pending 상태로 보관하고 기존 Execute Preflight를
  연 뒤, preflight confirm 이후 같은 retry selection을 이어서 실행한다.
- `ExecutionRetryModal`은 중앙 modal이며 `custom` 선택 시 checkbox가 같은 목록에 표시된다.
- retry할 수 없는 package는 disabled 상태와 reason을 함께 보여준다.

### Work Package Detail

- `WorkPackageSnapshot`에 objective, scope, out_of_scope, dependencies, expected_files,
  acceptance_criteria, requires_execution, weight, parallel metadata, repair notes,
  last result, retryability 정보를 추가했다.
- `ExecutionMatrixScreen`은 각 package row에 `View` 버튼을 렌더링한다.
- `WorkPackageDetailModal`은 snapshot 기반으로 package 설계와 최근 실행 결과를 표시한다.

### Plain TUI

- `PLAIN_TUI_COMMAND_HANDLERS`에 `execute-retry`를 등록했다.
- plain TUI의 `/execute-retry`는 `all`, `failed`, `blocked`, `interrupted`, `custom`,
  또는 WP id 목록을 받아 같은 retry planner를 사용한다.
- plain TUI execution loop도 `pending_execution_package_ids()` 기준으로 선택된 package만
  orchestrator에 dispatch한다.

## 검증

작업 중 다음 회귀 묶음이 통과했다.

```text
uv run pytest tests/test_workflow_engine.py tests/test_textual_workflow_controller.py tests/test_textual_snapshot.py tests/test_textual_app.py tests/test_tui_prompt.py tests/test_tui_session.py tests/test_slash_command_docs.py -q
250 passed
```

최종 검증으로 전체 테스트를 실행했다.

```text
uv run pytest -q
1264 passed, 1 warning
```
