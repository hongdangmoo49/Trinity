# Workflow Review Flow Wrapper Cleanup

## Context

`WorkflowReviewFlow` owns review package planning, approval checks, review
result recording, and repair-loop metadata. `WorkflowEngine` still exposed a few
private wrappers that only forwarded to the review flow:

- `_latest_review_is_approved`
- `_review_package_is_approved`
- `_planned_review_packages`

These wrappers keep facade drift alive and encourage tests to assert against the
engine's private forwarding surface instead of the flow that owns the behavior.

## Goal

- Remove the unused private forwarding wrappers from `WorkflowEngine`.
- Keep public workflow review methods unchanged.
- Move the existing helper assertion to the review flow owner.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py::test_review_request_keeps_legacy_multi_review_pending`
- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_review_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
