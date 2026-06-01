# Trinity Agent

**Three minds, one context.** Multi-agent AI orchestrator that unifies Claude Code, Codex, and Gemini CLI through shared context, round-based deliberation, and task distribution.

## Quick Start

```bash
# Install
pip install trinity-agent

# Initialize in your project
trinity init

# Run a deliberation
trinity ask "인증 시스템 아키텍처를 설계해줘"

# Interactive mode (tmux)
trinity ask "질문" --interactive
```

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Claude    │     │    Codex    │     │   Gemini    │
│  (Architect)│     │(Implementer)│     │  (Reviewer) │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┴───────────────────┘
                   │
           ┌───────┴───────┐
           │   Orchestrator │
           │  Shared Context│
           │   Consensus    │
           └───────────────┘
```

1. **Shared Context** — All agents read/write to a shared markdown file
2. **Round-based Deliberation** — Agents discuss in rounds until consensus
3. **Consensus Detection** — Keyword-based agreement detection
4. **Task Distribution** — Assign tasks based on agent strengths

## Commands

| Command | Description |
|---------|-------------|
| `trinity init` | Initialize `.trinity/` in current directory |
| `trinity ask "question"` | Run deliberation on a prompt |
| `trinity status` | Show agent status |
| `trinity context` | Display shared context |
| `trinity config [key]` | Show configuration |
| `trinity logs` | View orchestrator logs |
| `trinity reset --keep-context` | Reset session (preserve context) |
| `trinity attach` | Attach to tmux session |
| `trinity status-watch` | Live status dashboard |

## Configuration

Edit `.trinity/trinity.config`:

```toml
[general]
session_name = "trinity"
max_deliberation_rounds = 5
consensus_threshold = 0.6

[agents.claude]
provider = "claude-code"
cli_command = "claude"
role_prompt = "You are the Architect..."
enabled = true

[agents.codex]
provider = "codex"
cli_command = "codex"
role_prompt = "You are the Implementer..."
enabled = true

[agents.gemini]
provider = "gemini-cli"
cli_command = "gemini"
role_prompt = "You are the Reviewer..."
enabled = true
```

## Architecture

| Module | Description |
|--------|-------------|
| `trinity.orchestrator` | Top-level coordinator |
| `trinity.agents` | Provider-specific agent wrappers (Claude, Codex, Gemini) |
| `trinity.deliberation` | Protocol, consensus, task distribution |
| `trinity.completion` | Completion detection (Hook, PromptReturn, Idle) |
| `trinity.context` | Shared context engine, monitor, session rotation |
| `trinity.health` | Agent health monitoring |
| `trinity.workspace` | Workspace isolation (git worktree), managed home |
| `trinity.retry` | Retry with exponential backoff |
| `trinity.error_handler` | Crash recovery and agent respawn |

## Requirements

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (optional)
- [Codex CLI](https://github.com/openai/codex) (optional)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) (optional)
- tmux (for interactive mode)

## Development

```bash
git clone https://github.com/hongdangmoo49/Trinity.git
cd Trinity
uv sync
uv run pytest tests/ -v
```

## License

MIT
