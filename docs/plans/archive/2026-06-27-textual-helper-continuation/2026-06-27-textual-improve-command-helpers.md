# Textual Improve Command Helpers

## Context

`/improve` still classifies workflow outcome messages inside
`TrinityTextualApp`. That logic belongs with command presentation policy rather
than the UI shell.

The current `/improve` warning contract is:

- messages beginning with `No matching`
- messages containing `required`

Other messages remain informational.

## Goal

- Move `/improve` outcome message severity decisions into a pure helper.
- Keep `TrinityTextualApp` focused on controller dispatch and result rendering.
- Add focused helper tests and include them in required smoke.

## Verification

- `uv run pytest -q tests/test_textual_improve_commands.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
