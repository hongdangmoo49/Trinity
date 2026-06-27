# Workflow Post-Review Wrapper Cleanup

## Context

`WorkflowPostReviewFlow` owns post-review candidate creation, item selection,
supplemental package ids, owner resolution, and follow-up event recording.
`WorkflowEngine` still exposed private wrappers that only forwarded to those
flow methods.

These wrappers are not public API. Keeping them in the engine facade makes tests
and future code more likely to depend on the wrong owner.

## Goal

- Remove unused private post-review forwarding wrappers from `WorkflowEngine`.
- Keep public post-review methods unchanged:
  - `extract_post_review_items`
  - `handle_post_review_input`
  - `accept_post_review_items`
  - `queue_supplemental_work_packages`
  - `post_review_summary`
- Keep `WorkflowPostReviewFlow` as the owner of post-review helper behavior.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_post_review_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
