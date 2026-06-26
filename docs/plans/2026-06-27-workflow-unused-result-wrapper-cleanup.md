# Workflow Unused Result Wrapper Cleanup

## Context

Recent facade cleanup moved flow-owned behavior out of `WorkflowEngine`. Three
private wrappers remained in the engine without callers:

- `_record_execution_result`
- `_record_review_result`
- `_auto_replan_final_review_changes`

The owning flows already expose and call the real implementations directly.

## Goal

- Remove the unused private forwarding wrappers from `WorkflowEngine`.
- Keep public execution, review, and post-review entrypoints unchanged.
- Preserve flow ownership for execution results, review results, and final-review
  auto-replanning.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_execution_flow.py tests/test_workflow_review_flow.py tests/test_workflow_post_review_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
