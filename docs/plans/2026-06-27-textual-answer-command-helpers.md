# Textual Answer Command Helpers

## Context

`/answer` already delegates parsing to `command_parsers.py`, but the Textual app
still classifies workflow outcome messages inline. That keeps command policy in
the UI shell and repeats the local command presentation pattern used by other
commands.

## Goal

- Move `/answer` outcome message severity and empty-state decisions into a pure
  helper.
- Keep `TrinityTextualApp` focused on dispatching workflow controller calls and
  recording the local command result.
- Add focused helper tests and include them in required smoke.

## Verification

- `uv run pytest -q tests/test_textual_answer_commands.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
