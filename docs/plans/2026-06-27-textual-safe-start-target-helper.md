# Textual Safe Start Target Helper

## Context

`textual_app/target_workspace.py` now owns target workspace path resolution and
control-repository detection. `TrinityTextualApp` still has one small target
helper, `_safe_start_target_workspace`, which decides whether a start-screen
workspace candidate can be persisted without showing the control-repository
confirmation modal.

## Goal

- Move the safe start target decision into `textual_app/target_workspace.py`.
- Keep the Textual app responsible for UI flow, not pure target path policy.
- Test `None`, control-repository, child, and sibling workspace behavior.

## Verification

- `uv run pytest -q tests/test_textual_target_workspace.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
