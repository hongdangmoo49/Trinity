# Provider Readiness Troubleshooting

Trinity's default provider transport is `one-shot`. Claude Code, Codex, and
Antigravity are called as short-lived CLI processes and normally reuse the auth
state that already exists in the user's home directory.

Use this order when startup fails:

1. Run `trinity doctor`.
2. Check provider CLI installation with `trinity bootstrap --check-only`.
3. Run the provider CLI directly in your normal shell and complete login or
   workspace trust prompts.
4. Use `trinity bootstrap` only when you want Trinity to launch those setup
   prompts sequentially for selected configured agents.

## Common States

| Symptom | Likely state | Action |
| :--- | :--- | :--- |
| CLI command is missing | `missing` in `doctor` or `bootstrap --check-only` | Install the provider CLI and reopen the terminal |
| Provider asks for login, OAuth, or API key | `auth_required` | Run the provider CLI in your normal shell and finish auth |
| Provider asks whether to trust the workspace | `workspace_trust_required` | Accept trust in the provider CLI |
| One-shot call exits non-zero | `invalid` or provider-specific error | Inspect stderr, then retry with `trinity doctor` |
| Legacy tmux pane is dead | `process_dead` | Restart the legacy tmux session or use one-shot mode |

## Cross-platform Bootstrap

Default bootstrap does not require tmux:

```bash
trinity bootstrap --check-only
trinity bootstrap --agents claude
```

This runs selected provider CLIs one at a time in the current terminal. On
Windows Terminal, PowerShell, macOS Terminal, and Linux terminals, provider auth
prompts are shown directly in that terminal.

Useful options:

```bash
trinity bootstrap --agents claude,codex
trinity bootstrap --all --check-only
trinity bootstrap --skip-ready
trinity bootstrap --continue-on-error
```

## User-home vs Isolated Provider State

`provider_state_mode = "user-home"` is the default. Trinity does not override
provider home/config environment variables, so existing Claude/Codex/Antigravity
auth is reused.

`provider_state_mode = "isolated"` creates per-agent state under
`.trinity/agents/<agent>/provider-state`.

On Windows, Trinity sets:

- `HOME`
- `USERPROFILE`
- `APPDATA`
- `LOCALAPPDATA`

On macOS/Linux, Trinity sets:

- `HOME`
- `XDG_CONFIG_HOME`
- `XDG_DATA_HOME`
- `XDG_CACHE_HOME`

## Provider Notes

### Claude Code

Check:

```bash
claude --version
trinity bootstrap --check-only --agents claude
```

If auth is missing, run:

```bash
claude
```

Complete login/trust prompts, then retry Trinity.

### Codex

Check:

```bash
codex --version
trinity bootstrap --check-only --agents codex
```

If auth is missing, run:

```bash
codex login
```

or open `codex` in your normal shell and complete the prompt.

### Antigravity

Check:

```bash
agy --version
trinity bootstrap --check-only --agents antigravity
```

If auth or workspace trust is missing, run:

```bash
agy
```

Trinity uses `agy --print` in one-shot mode.

## Legacy tmux Transport

tmux is no longer the default runtime path. It remains available for explicit
debugging:

```bash
trinity ask -i "debug this prompt"
trinity bootstrap --legacy-tmux
trinity attach
```

On Windows, use the default one-shot transport unless you are running inside an
environment that provides tmux, such as WSL/MSYS.
