# Cross-Platform P0 Audit

- Date: 2026-06-05
- Branch: `codex/cross-platform-stability-redesign`
- Source plan: `docs/plans/2026-06-05-cross-platform-stability-redesign.md`

## Scope

P0의 목적은 구현 전에 현재 코드가 Windows Terminal, PowerShell, macOS Terminal, Linux terminal에서 깨질 수 있는 platform-specific 의존성을 명확히 고정하는 것이다.

확인 명령:

- `git status --short --branch`
- `grep -R "tmux" -n src tests docs README.md README.en.md pyproject.toml`
- `grep -R "tail -f\\|tail" -n src tests docs README.md README.en.md`
- `grep -R "prompt_toolkit\\|rich\\|Console\\|Panel\\|Table" -n src/trinity tests docs/plans/2026-06-05-cross-platform-stability-redesign.md`

## Baseline State

- Current branch: `codex/cross-platform-stability-redesign`
- Working tree before P0 edits: clean
- Default transport remains `one-shot`.
- Legacy/debug transport remains `tmux`.
- Provider set is Claude Code, Codex, Antigravity CLI.

## Findings

### F1. `trinity bootstrap` still depends on tmux and POSIX env syntax

Files:

- `src/trinity/cli.py`
- `src/trinity/providers/bootstrap.py`

Current behavior:

- CLI options expose `--session-name` and `--no-attach` as normal bootstrap options.
- `ProviderBootstrapper.launch_session()` creates a `TmuxSessionManager`, creates panes, sends one shell command per provider, then optionally attaches.
- `build_provider_command()` builds a shell string and prefixes env overrides with POSIX-style `env KEY=value command`.

Cross-platform risk:

- Windows Terminal and PowerShell do not have tmux by default.
- POSIX `env KEY=value` is not a portable command form.
- First-run auth/setup UI is harder to control when hidden inside a tmux pane.

Plan mapping:

- P2: introduce argv/env based process runner.
- P4: make sequential current-terminal bootstrap the default.
- P4: keep tmux bootstrap only behind `--legacy-tmux`.

### F2. `trinity logs --follow` depends on POSIX `tail`

File:

- `src/trinity/cli.py`

Current behavior:

- `logs --follow` runs `subprocess.run(["tail", "-f", "-n", str(lines), str(log_path)])`.

Cross-platform risk:

- Windows does not provide `tail` by default.
- Log follow behavior should not depend on shell utilities after pip install.

Plan mapping:

- P3: add `trinity.platform.log_tail.follow_file()`.
- P3: make CLI consume the Python generator and remove `tail`.

### F3. Isolated provider state is Linux/XDG-centered

File:

- `src/trinity/workspace/managed_home.py`
- `tests/test_managed_home.py`

Current behavior:

- `ManagedHome.get_env_overrides()` returns `HOME`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`.
- It does not set Windows-specific `USERPROFILE`, `APPDATA`, or `LOCALAPPDATA`.
- Current tests lock in the XDG-only behavior.

Cross-platform risk:

- Windows provider CLIs may ignore `HOME` and read/write state through `%USERPROFILE%`, `%APPDATA%`, or `%LOCALAPPDATA%`.
- Isolated mode can leak into the real user profile or fail to find isolated auth/config.

Plan mapping:

- P1: detect OS/platform.
- P2: normalize managed-home env per OS.
- P2: update tests so Windows env is explicitly covered without depending on the host OS.

### F4. One-shot provider invocation is structurally good but not centralized

Files:

- `src/trinity/providers/invoker.py`
- `src/trinity/setup/detector.py`
- `src/trinity/workspace/isolation.py`

Current behavior:

- Provider one-shot calls already use argv lists and env dictionaries.
- Git/worktree and detector subprocess calls also use argv lists.
- There is no shared `ProcessRunner`, command display model, or central Windows shim/path policy yet.

Cross-platform risk:

- New commands can reintroduce shell strings or POSIX assumptions because the safe subprocess pattern is copied locally.
- Bootstrap still builds shell strings separately, so provider invocation and bootstrap do not share the same execution contract.

Plan mapping:

- P2: introduce a reusable process layer around argv/env/cwd/timeout.
- P2/P4: move bootstrap command construction from shell string to argv/env command specs.

### F5. tmux interactive transport is legacy but still reachable

Files:

- `src/trinity/orchestrator.py`
- `src/trinity/agents/claude_agent.py`
- `src/trinity/agents/codex_agent.py`
- `src/trinity/agents/factory.py`
- `src/trinity/completion/*`
- `src/trinity/legacy/tmux/*`
- `src/trinity/tmux/*`
- `src/trinity/providers/readiness.py`
- `tests/test_tmux.py`
- `tests/test_interactive_claude.py`

Current behavior:

- `transport_mode = "tmux"` and `trinity ask -i` still create interactive tmux agents.
- `trinity attach` is guarded and only attempts tmux attach when config transport is `tmux`.
- `trinity.tmux.*` is a compatibility shim around `trinity.legacy.tmux.*`.
- Legacy tmux session code uses tmux CLI and Unix-specific flags such as `-f /dev/null`.
- Some readiness guidance still points users toward bootstrap/tmux troubleshooting.

Cross-platform risk:

- The path is not cross-platform, but it is no longer the default agent runtime.
- It must remain clearly labeled legacy/debug and should fail with actionable platform hints when unavailable.

Plan mapping:

- P1: platform capability layer should expose tmux availability and OS hints.
- P4/P6: preserve legacy behavior, but make unsupported usage explicit.
- P6: refresh troubleshooting docs and smoke checklists so they reflect one-shot/Antigravity defaults.

### F6. TUI has Rich/prompt_toolkit fallback, but no explicit rendering policy layer

Files:

- `src/trinity/tui/session.py`
- `src/trinity/tui/app.py`
- `src/trinity/tui/prompt.py`
- `src/trinity/setup/wizard.py`
- `src/trinity/cli.py`
- `src/trinity/tui/theme.py`
- `src/trinity/i18n.py`
- `src/trinity/logging.py`

Current behavior:

- Rich `Console`, `Panel`, `Table`, `Live` are used directly across CLI/TUI modules.
- `TrinityPromptSession` catches prompt_toolkit Windows console buffer issues and falls back to dummy I/O in tests/non-console contexts.
- Rendering decisions are not centralized around terminal width, unicode, emoji, box drawing, CI, or dumb terminal capability.
- Agent icons and UI symbols are embedded in theme/i18n strings instead of selected through a capability-aware icon policy.
- Logging uses RichHandler directly without an explicit CI/dumb/NO_COLOR policy.

Cross-platform risk:

- Narrow terminals can overflow panel content.
- Emoji and box-drawing width can vary across Windows/macOS/Linux terminals.
- CI, redirected stdout, and dumb terminals should avoid live rendering and rich-heavy layout.
- `trinity init` can wait on Rich prompts in non-interactive install smoke contexts unless a non-interactive path is selected.

Plan mapping:

- P1: add terminal capability detection.
- P5: split rendering mode/icon/border/layout policy from business logic.
- P6: add packaging/install smoke coverage for non-interactive CLI entry points.

### F7. Cross-platform CI and docs do not yet prove pip UX

Files:

- `pyproject.toml`
- `.github/workflows/*`
- `README.md`
- `README.en.md`
- `docs/troubleshooting-provider-readiness.md`
- `docs/test-results/v070-smoke-checklist.md`
- `templates/trinity.config.example`

Current behavior:

- The package exposes a `trinity` console script.
- Existing documentation still contains prominent tmux/interactive-mode wording.
- Current automated coverage is primarily Linux/local unit tests.
- Some docs still reference old WSL/tmux smoke assumptions and historical provider names.

Cross-platform risk:

- A green Linux test run does not prove `pip install trinity-agent` works in Windows Terminal, PowerShell, or macOS Terminal.
- Users can reasonably expect tmux to be part of the normal startup path because README command tables still describe `trinity attach` and tmux mode without enough legacy/debug framing.

Plan mapping:

- P6: add Windows/macOS/Linux packaging smoke checks where practical.
- P6: update README wording so one-shot/current-terminal bootstrap is the default expectation and tmux is optional legacy/debug.

## Required Work Sequence Confirmation

The implementation order in the plan remains valid:

1. P1 platform capability layer.
2. P2 process runner and env normalization.
3. P3 Python log follow.
4. P4 tmux-free bootstrap default.
5. P5 adaptive TUI rendering.
6. P6 doctor, CI, docs, and final verification.

Parallelizable work:

- P3 can be implemented after or alongside P1 because log following does not depend on provider bootstrap.
- P4 and P5 can be implemented in parallel after P1/P2 if write scopes stay separate.
- P6 should stay last because it verifies the integrated behavior.

## P0 Acceptance Evidence

- The branch state and grep-based dependency audit are recorded.
- The risky runtime paths are mapped to concrete files and subsequent phases.
- No production behavior is changed in P0.
