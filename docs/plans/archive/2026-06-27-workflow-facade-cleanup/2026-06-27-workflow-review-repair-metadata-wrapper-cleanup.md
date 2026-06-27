# Workflow Review Repair Metadata Wrapper Cleanup

## Context

`WorkflowReviewFlow` owns review-repair metadata reconstruction. `WorkflowEngine`
still exposed `_review_repair_metadata_from_events`, a private wrapper that only
forwarded to the review flow and had no external callers.

## Goal

- Remove the unused `WorkflowEngine._review_repair_metadata_from_events`
  forwarding wrapper.
- Keep review repair metadata behavior owned by `WorkflowReviewFlow`.
- Keep public workflow review behavior unchanged.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_review_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
