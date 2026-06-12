# Memory Cleanup Command

Date: 2026-06-13

## Scope

- Added `/memory cleanup --oversized-backups` as a local memory maintenance command.
- The command defaults to dry-run and only deletes `shared.md.oversized-*` candidates when `--apply` is explicitly supplied.
- The default retention keeps the latest oversized backup. Users can adjust it with `--keep-latest N`.
- The same cleanup helper is used by Textual, plain TUI, and the Click CLI.

## Safety Rules

- Cleanup only targets files matching `shared.md.oversized-*` in the shared context directory.
- Symlinks, directories, and files resolving outside the shared context directory are skipped.
- Dry-run reports retained files, cleanup candidates, candidate bytes, and the exact apply command.
- No automatic cleanup runs during startup, resume, compact, or snapshot rendering.

## Validation

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_context_commands.py -q
# 6 passed

PYTHONPATH=src .venv/bin/python -m py_compile \
  src/trinity/context/commands.py \
  src/trinity/textual_app/app.py \
  src/trinity/tui/session.py \
  src/trinity/cli.py
# passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_tui_prompt.py \
  tests/test_context_commands.py -q
# 23 passed

PYTHONPATH=src .venv/bin/python -m pytest tests/test_textual_app.py -q
# 123 passed

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_tui_session.py \
  tests/test_context_commands.py -q
# 90 passed

PYTHONPATH=src .venv/bin/trinity memory cleanup --help
# showed cleanup options
```

