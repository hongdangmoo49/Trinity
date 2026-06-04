# Isolated Provider Bootstrap Plan

## Goal

Keep Trinity's per-agent provider-state isolation, but add an explicit bootstrap
flow so Claude, Codex, and Gemini can complete their first-run setup,
authentication, and workspace trust prompts inside the same isolated homes that
normal Trinity sessions use.

## Problem

Trinity launches each provider with a managed home:

- `.trinity/agents/claude/provider-state`
- `.trinity/agents/codex/provider-state`
- `.trinity/agents/gemini/provider-state`

This is correct for isolation, but it means provider CLIs do not see the user's
normal WSL home configuration. A provider that is already authenticated in
`/home/user` can still show first-run setup or auth prompts when launched by
Trinity.

## Implementation Plan

1. Add a `trinity bootstrap` command that:
   - loads the project config;
   - prepares the same per-agent managed homes and launch directories used by
     regular Trinity sessions;
   - opens a tmux bootstrap session;
   - launches each selected provider CLI with the isolated `HOME` and `XDG_*`
     environment variables;
   - optionally attaches to the session so the user can complete auth/setup.

2. Keep isolation as the default and only supported behavior for this flow.
   - Do not copy credentials from the user's real home.
   - Do not symlink provider configs into `.trinity`.
   - Do not disable `HOME`/`XDG_*` overrides.

3. Improve readiness guidance so auth/trust failures point users to
   `trinity bootstrap` instead of generic provider commands that would use the
   wrong home directory.

4. Add focused tests for:
   - bootstrap target selection;
   - isolated env command construction;
   - CLI command behavior without launching real provider CLIs or tmux;
   - readiness action hints.

5. Document the completed behavior in a result note after implementation and
   verification.

## Acceptance Criteria

- `trinity bootstrap` starts a separate tmux session for provider first-run
  setup using isolated provider-state directories.
- Running normal Trinity after bootstrap reuses the initialized provider-state.
- The command supports agent filtering and disabled-agent inclusion for manual
  preparation.
- Existing print/interactive deliberation paths continue using isolated homes.
- Unit tests pass for the changed areas.
