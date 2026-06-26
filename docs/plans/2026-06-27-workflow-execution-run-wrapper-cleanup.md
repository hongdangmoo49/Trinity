# Workflow Execution Run Wrapper Cleanup

## Context

`ExecutionRecoveryFlow` owns execution-run lifecycle metadata. `WorkflowEngine`
still exposed private wrappers that only forwarded to that flow:

- `_touch_execution_run`
- `_finish_execution_run`

`WorkflowExecutionFlow` was the only caller. Keeping these wrappers in the
engine facade makes execution-run lifecycle ownership less clear.

## Goal

- Remove the two private execution-run forwarding wrappers from
  `WorkflowEngine`.
- Make `WorkflowExecutionFlow` call `ExecutionRecoveryFlow` directly.
- Keep public execution behavior unchanged.

## Verification

- `uv run pytest -q tests/test_workflow_engine.py tests/test_workflow_execution_flow.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
