# Isolated Provider Bootstrap Result

## Branch

- `codex/isolated-provider-bootstrap`

## Summary

Implemented an explicit isolated provider bootstrap flow while keeping Trinity's
per-agent provider-state isolation intact.

The new command is:

```bash
trinity bootstrap
```

It starts a separate tmux session, launches selected provider CLIs with the same
isolated `HOME` and `XDG_*` environment variables used by normal Trinity
sessions, and lets the user complete first-run setup, authentication, theme
selection, and workspace trust prompts inside `.trinity/agents/<agent>/provider-state`.

## Implemented

- Added `src/trinity/providers/bootstrap.py`.
- Added `trinity bootstrap` CLI command.
- Added options:
  - `--agents claude,codex`
  - `--all`
  - `--session-name <name>`
  - `--force`
  - `--no-attach`
- Changed readiness action hints to direct users to `trinity bootstrap` instead
  of running provider CLIs in the normal user home.
- Documented the flow in README files and provider readiness troubleshooting.
- Added tests for bootstrap target selection, command construction, tmux launch
  orchestration, CLI behavior, and readiness hints.

## Verification

```bash
uv run pytest tests/test_provider_bootstrap.py tests/test_provider_readiness.py tests/test_cli.py -q
```

Result:

```text
41 passed in 0.20s
```

```bash
uv run pytest -q
```

Result:

```text
909 passed, 1 warning in 19.65s
```

The remaining warning is an existing AsyncMock resource warning in the test
suite and is not introduced by this change.
