# Textual Target Command Helper Separation

## Context

`TrinityTextualApp` is still the largest Textual surface. Recent work moved
slash command routing and several pure presenter functions out of the app, but
some command handlers still own small utility logic directly.

The `/target` command is a good next slice because it mixes UI flow with path
normalization and control-repository detection. Those path helpers are pure,
easy to test, and reused by both slash-command target handling and workspace
selection preflight checks.

## Goal

- Move target workspace path normalization out of `textual_app/app.py`.
- Keep `TrinityTextualApp` focused on UI state transitions and modal flow.
- Add focused tests for relative path resolution and control-repository
  detection.
- Preserve the existing `/target` behavior.

## Scope

- Add `trinity.textual_app.target_workspace`.
- Replace private app methods with imported helper calls.
- Add unit coverage for the helper module.

Out of scope for this slice:

- Changing `/target` UX copy.
- Changing workspace creation/preflight behavior.
- Moving the whole `/target` command handler to a service object.

## Verification

- `uv run pytest -q tests/test_textual_target_workspace.py`
- `uv run pytest -q tests/test_textual_command_parsers.py tests/test_textual_local_commands.py tests/test_textual_smoke.py tests/test_textual_runtime.py tests/test_textual_workflow_controller.py tests/test_textual_target_workspace.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
