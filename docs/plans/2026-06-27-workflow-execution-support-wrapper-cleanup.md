# Workflow Execution Support Wrapper Cleanup

## Context

`WorkflowExecutionFlow` still called two private `WorkflowEngine` forwarding
wrappers:

- `_upsert_subtask_result`
- `_plan_review_packages`

The actual owners are `WorkflowCollectionFlow` and `WorkflowReviewFlow`. Keeping
the wrappers in `WorkflowEngine` adds facade drift without behavior.

## Goal

- Remove the two private forwarding wrappers from `WorkflowEngine`.
- Make `WorkflowExecutionFlow` call the owning flows directly.
- Keep execution, subtask persistence, and review planning behavior unchanged.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_execution_flow.py tests/test_workflow_review_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
