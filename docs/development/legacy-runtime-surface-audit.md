# Legacy Runtime Surface Audit

This audit records the current legacy runtime surface after the Nexus and
workflow maintenance pass.

## Scope

Audited paths:

- `src/trinity/legacy/`
- `src/trinity/tmux/`
- `src/trinity/tui/`

## Current Findings

### `trinity.legacy.tmux`

`trinity.legacy.tmux` is still an active implementation surface, not dead code.
It is imported by:

- Claude/Codex interactive agent wrappers
- `AgentFactory`
- completion detectors
- `TrinityOrchestrator`
- provider bootstrap checks
- tmux compatibility tests

Do not remove this package until interactive/tmux mode is formally deprecated or
ported to a new runtime.

### `trinity.tmux`

`trinity.tmux` is a compatibility shim over `trinity.legacy.tmux`. Tests still
assert the shim imports:

- `trinity.tmux.pane.TmuxPane`
- `trinity.tmux.session.TmuxSessionManager`

Keep this shim until a release note announces the import-path migration.

### `trinity.tui`

`trinity.tui` is still the plain terminal fallback selected by `trinity --plain`
or when Textual is unavailable. It also owns shared report rendering utilities
used by current tests.

Do not remove `trinity.tui` while:

- `--plain` exists
- Textual fallback is supported
- `DeliberationReportBuilder` lives in `trinity.tui.report`

### Legacy Gemini

Tracked source no longer includes `src/trinity/legacy/gemini`. Old plans and
test-result documents mention it only as historical migration context.

## Removal Conditions

Before deleting any legacy runtime surface:

1. Replace internal imports with the new runtime path.
2. Keep external compatibility shims for at least one minor release.
3. Add a release note or migration note for import-path changes.
4. Run focused tmux/completion/provider bootstrap tests.
5. Run required smoke on all supported platforms.

## Focused Tests

Use this focused set when touching legacy runtime paths:

```bash
uv run pytest -q tests/test_tmux.py tests/test_completion.py tests/test_provider_bootstrap.py tests/test_cli.py
```

Then run:

```bash
uv run python scripts/run_required_smoke_tests.py -q
```
