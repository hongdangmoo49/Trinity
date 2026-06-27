# Workflow Result Collection Wrapper Cleanup

## Context

`WorkflowEngine` still had private forwarding wrappers for result collection:

- `_review_results`
- `_post_review_items`

The public `review_results` and `post_review_items` properties already exist,
so these private wrappers add facade drift without adding behavior. One
post-review flow path also called back into `engine._review_results()`, which
encouraged flow code to depend on the engine forwarding surface.

## Goal

- Remove the two private collection forwarding wrappers from `WorkflowEngine`.
- Keep public properties unchanged.
- Make `WorkflowPostReviewFlow` use the public `engine.review_results` property
  for review result collection.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_post_review_flow.py tests/test_workflow_review_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
