# Textual Review Command Helpers

## Context

`/review` delegates workflow work to `TextualWorkflowController`, but the Textual
app still classifies workflow outcome messages inline. This keeps command
presentation policy mixed into the UI shell.

The current `/review` warning contract is:

- messages beginning with `No review`
- messages containing `not connected`

Other messages remain informational.

## Goal

- Move `/review` outcome message severity decisions into a pure helper.
- Keep `TrinityTextualApp` focused on controller dispatch and result rendering.
- Add focused helper tests and include them in required smoke.

## Verification

- `uv run pytest -q tests/test_textual_review_commands.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
