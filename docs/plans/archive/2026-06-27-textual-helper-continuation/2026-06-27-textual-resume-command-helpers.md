# Textual Resume Command Helpers

## Context

`TrinityTextualApp` still owns small pieces of `/resume` command policy. The
handler should remain responsible for UI transitions, but result-message
classification is pure command behavior and can be tested outside Textual.

The current failure contract is intentionally narrow: workflow-controller resume
failures are surfaced as messages beginning with `No `. Successful informational
messages may still be shown, but they should not block switching back to Nexus.

## Goal

- Move resume result-message presentation decisions out of `app.py`.
- Keep failure severity, empty state, and modal reopening behavior in one pure
  helper.
- Add focused unit coverage and include it in the required smoke list.

## Verification

- `uv run pytest -q tests/test_textual_resume_commands.py`
- `uv run python scripts/run_required_smoke_tests.py -q`
