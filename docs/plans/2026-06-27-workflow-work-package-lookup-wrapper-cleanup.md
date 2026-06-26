# Workflow Work Package Lookup Wrapper Cleanup

## Context

`WorkflowCollectionFlow` owns work package lookup. `WorkflowEngine` still exposed
`_work_package_by_id`, a private wrapper that only forwarded to the collection
flow. Execution, review, and post-review flows used that wrapper, which kept a
lookup facade in the engine.

## Goal

- Remove `WorkflowEngine._work_package_by_id`.
- Make execution, review, and post-review flows call the collection flow owner
  directly.
- Keep public workflow behavior unchanged.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_execution_flow.py tests/test_workflow_review_flow.py tests/test_workflow_post_review_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
