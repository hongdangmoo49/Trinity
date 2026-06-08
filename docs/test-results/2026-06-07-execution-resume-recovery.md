# Execution Resume Recovery Implementation

작성일: 2026-06-07

브랜치: `codex/execution-resume-recovery-design`

## 목적

`/execute` 중 TUI를 종료한 뒤 `/resume`으로 돌아왔을 때 stale execution을 명확히 감지하고,
사용자가 명시적으로 retry/mark/abort를 선택하기 전에는 같은 WP를 조용히 재실행하지 않게 했다.

## 구현 범위

- `WorkflowSession.execution_run` metadata 추가
- `WorkPackage.current_executor` / `last_executor` 추가
- `WorkflowEngine.detect_interrupted_execution()` / retry / mark / abort action 추가
- `TextualWorkflowController.request_execution()` stale guard 추가
- Textual `/resume`, `/execute`, `/status`, `/workflow`, `/report` recovery 표시
- Plain TUI `/execute` recovery action 처리와 `/workflow` recovery 표시
- Execution Matrix `Assignee` / `Executor` 컬럼 분리
- 환경 검증 blocker 자동 fallback 억제
- done / needs_review package 재실행 방지

## 검증 명령

```bash
uv run pytest \
  tests/test_workflow_engine.py::test_detect_interrupted_execution_when_running_without_worker \
  tests/test_workflow_engine.py::test_retry_interrupted_packages_excludes_done_packages \
  tests/test_textual_workflow_controller.py::test_resume_surfaces_execution_recovery \
  tests/test_textual_workflow_controller.py::test_execute_requires_recovery_choice_for_stale_execution \
  tests/test_textual_snapshot.py::test_snapshot_projects_execution_recovery_and_executor_details \
  tests/test_execution_protocol.py::test_environment_blocker_does_not_auto_fallback \
  tests/test_textual_app.py::test_status_reports_interrupted_execution \
  tests/test_textual_app.py::test_execution_matrix_separates_owner_and_executor -q

uv run pytest \
  tests/test_execution_protocol.py \
  tests/test_workflow_engine.py \
  tests/test_textual_workflow_controller.py \
  tests/test_textual_snapshot.py -q

uv run pytest \
  tests/test_textual_app.py::test_status_reports_interrupted_execution \
  tests/test_textual_app.py::test_execution_matrix_separates_owner_and_executor \
  tests/test_textual_app.py::test_start_slash_status_does_not_start_workflow \
  tests/test_textual_app.py::test_textual_status_refresh_replaces_existing_local_command_table -q

uvx ruff format \
  src/trinity/workflow/models.py \
  src/trinity/workflow/engine.py \
  src/trinity/workflow/execution.py \
  src/trinity/textual_app/snapshot.py \
  src/trinity/textual_app/app.py \
  src/trinity/textual_app/report_export.py \
  src/trinity/textual_app/screens/execution_matrix.py \
  src/trinity/textual_app/workflow_controller.py \
  src/trinity/tui/session.py \
  tests/test_workflow_engine.py \
  tests/test_textual_workflow_controller.py \
  tests/test_textual_snapshot.py \
  tests/test_execution_protocol.py \
  tests/test_textual_app.py

uvx ruff check \
  src/trinity/workflow/models.py \
  src/trinity/workflow/engine.py \
  src/trinity/workflow/execution.py \
  src/trinity/textual_app/snapshot.py \
  src/trinity/textual_app/app.py \
  src/trinity/textual_app/report_export.py \
  src/trinity/textual_app/screens/execution_matrix.py \
  src/trinity/textual_app/workflow_controller.py \
  src/trinity/tui/session.py \
  tests/test_workflow_engine.py \
  tests/test_textual_workflow_controller.py \
  tests/test_textual_snapshot.py \
  tests/test_execution_protocol.py \
  tests/test_textual_app.py

git diff --check
uv run pytest -q
uvx ruff check src tests
```

## 현재 결과

- 신규 targeted tests: `8 passed`
- 관련 workflow/execution/snapshot/controller tests: `81 passed`
- 관련 Textual status/matrix 회귀 tests: `4 passed`
- formatter: `13 files reformatted, 1 file left unchanged`
- 변경 파일 대상 ruff: `All checks passed`
- 관련 회귀 재검증: `85 passed`
- whitespace check: 통과
- 전체 pytest: `1258 passed, 1 warning`
- 전체 ruff(`src tests`): 실패. 이번 변경과 무관한 기존 `F401`, `F541`, `F811`, `E402`, `F841`
  항목들이 다수 보고됨.

## 수동 확인 포인트

1. `/execute` 실행 중 TUI 종료
2. `/resume latest`
3. Nexus 중앙 영역에 `Execution Recovery` 표시 확인
4. `/execute` 재입력 시 즉시 재실행하지 않고 recovery 안내가 나오는지 확인
5. `/execute retry`가 done package를 제외하고 interrupted/blocked/failed package만 재실행하는지 확인
6. Execution Matrix에서 `Assignee`는 owner, `Executor`는 실제 실행자 또는 `fallback`으로 표시되는지 확인
