<div align="center">

◯ ─────────── ◯
# 🧠 T R I N I T Y
◯ ─────────── ◯

**Three minds, one context.**

Multi-agent AI orchestrator that unifies **Claude Code**, **Codex**, and **Antigravity CLI**
through shared context, round-based deliberation, and intelligent task distribution.

[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/hongdangmoo49/Trinity/blob/main/LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-trinity--agent-blue)](https://pypi.org/project/trinity-agent/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)](https://github.com/hongdangmoo49/Trinity)

[한국어](./README.md) · [Quick Start](#-quick-start) · [Why Trinity](#-why-trinity) · [How It Works](#-how-it-works) · [TUI](#-interactive-tui) · [Commands](#-commands) · [Architecture](#-architecture)

</div>

---

> **Trinity transforms three AI coding agents into a single collaborative intelligence.**
>
> Instead of asking one AI to do everything, Trinity orchestrates a structured debate
> between Claude (Architect), Codex (Implementer), and Antigravity (Reviewer).
> They share context, discuss in rounds, reach consensus, and distribute tasks
> based on each agent's strengths.

---

## ❓ Why Trinity

Single-agent AI is powerful, but it has blind spots.

| Problem | What Happens | Trinity Fix |
| :--- | :--- | :--- |
| **Tunnel Vision** | One AI explores only one approach | Three agents debate alternatives before deciding |
| **No Peer Review** | Architectural flaws go unchecked | Antigravity reviews and challenges Claude's designs |
| **Context Loss** | Each agent works in isolation | Shared context file keeps everyone on the same page |
| **Uneven Quality** | Code quality depends on one model | Consensus mechanism ensures cross-verification |
| **Manual Delegation** | You decide who does what | Tasks auto-distribute based on agent strengths |

---

## 🚀 Quick Start

### Install

```bash
pip install trinity-agent
```

### Initialize in Your Project

```bash
# Interactive setup wizard — detects your installed AI CLIs
trinity init

# Non-interactive (uses defaults)
trinity init --non-interactive

# Complete CLI auth/theme/trust setup inside isolated provider-state homes
trinity bootstrap
```

### Run Your First Deliberation

```bash
# One-shot question
trinity ask "Design the authentication system architecture"

# Interactive TUI mode (real-time agent discussion)
trinity
```

That's it. Trinity will:
1. 🔍 Detect installed AI CLIs (Claude Code, Codex, Antigravity CLI)
2. 🧠 Start a round-based deliberation between available agents
3. 📊 Display results with consensus, task distribution, and reasoning

---

## 🔁 How It Works

```
  ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
  │   🏗️ Claude   │     │   ⚙️ Codex    │     │   🔍 Antigravity   │
  │  (Architect)  │     │ (Implementer) │     │  (Reviewer)   │
  └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                │
                       ┌────────┴────────┐
                       │  Orchestrator   │
                       │ Shared Context  │
                       │    Consensus    │
                       │  Task Distrib   │
                       └─────────────────┘
```

### Deliberation Flow

| Phase | Action |
| :--- | :--- |
| **Initialize** | Create shared context (`shared.md`) with the goal and agent list |
| **Round 1** | Each agent shares its **initial opinion** on the user's request |
| **Round 2+** | Agents read others' opinions, **AGREE or DISAGREE**, propose alternatives |
| **Consensus** | When ≥60% agents agree, consensus is **reached** |
| **Distribute** | Tasks are auto-assigned based on each agent's **strengths** |

### Agent Strengths

| Agent | Role | Best At |
| :--- | :--- | :--- |
| 🏗️ **Claude** | Architect | Architecture, design, code review, complex logic, planning |
| ⚙️ **Codex** | Implementer | Implementation, coding, prototyping, refactoring, testing |
| 🔍 **Antigravity** | Reviewer | Testing, research, alternative exploration, edge cases, QA |

---

## 💬 Interactive TUI

Trinity features a **Rich-based terminal UI** with real-time deliberation visualization.

```
  🧠 Trinity v0.9.2  —  Three minds, one context

  🏗️ claude ✅    ⚙️ codex ✅    🔍 antigravity ✅

  📊 Agent Status
  ┌────────────────────────────────────────────────────────────────┐
  │  🏗️ claude    Architect    ✅ responded    12%    I recommend... │
  │  ⚙️ codex     Implementer  ✅ responded    8%     Agreed with... │
  │  🔍 antigravity    Reviewer     ✅ responded    15%    I suggest...   │
  └────────────────────────────────────────────────────────────────┘

  💬 Deliberation
  ─── Round 1 ──────────────────────────────────────────────────────
    ✅ claude (Architect)
    ┌──────────────────────────────────────────────────────────┐
    │  I recommend using JWT with RS256 for the auth system.    │
    │  The architecture should follow a middleware pattern...   │
    └──────────────────────────────────────────────────────────┘

    ✅ codex (Implementer)
    ┌──────────────────────────────────────────────────────────┐
    │  I AGREE with claude. Additionally, we should add         │
    │  refresh token rotation for security...                   │
    └──────────────────────────────────────────────────────────┘

    ✅ antigravity (Reviewer)
    ┌──────────────────────────────────────────────────────────┐
    │  I suggest considering OAuth2 as an alternative. The      │
    │  token rotation idea is good, but we need edge case...    │
    └──────────────────────────────────────────────────────────┘

    🔍 Evaluating consensus...  2/3 agree (67%)

  💬 trinity>
```

### TUI Features

- **Real-time streaming** — Agent opinions appear as they arrive, not after all finish
- **Per-agent colors** — Claude (cyan), Codex (green), Antigravity (magenta)
- **Markdown rendering** — Agent responses rendered with formatting and syntax highlighting
- **Consensus progress bar** — Visual indicator of agreement fraction
- **Tree task distribution** — Clear view of who does what

---

## 📋 Commands

### CLI Commands

| Command | Description |
| :--- | :--- |
| `trinity` | Launch interactive TUI session |
| `trinity init` | Initialize `.trinity/` in current directory |
| `trinity init --non-interactive` | Initialize with defaults (no prompts) |
| `trinity bootstrap` | Run provider first-use auth/trust setup sequentially in the current terminal |
| `trinity bootstrap --check-only` | Check provider CLI installation without launching providers |
| `trinity ask "question"` | One-shot deliberation on a prompt |
| `trinity status` | Show agent status table |
| `trinity doctor` | Diagnose OS, terminal, provider CLI, and transport state |
| `trinity status-watch` | Live-updating status dashboard |
| `trinity context` | Display shared context |
| `trinity config [key]` | Show configuration values |
| `trinity logs` | View orchestrator logs (`--follow` uses Python, not POSIX tail) |
| `trinity reset --keep-context` | Reset session (preserve context) |
| `trinity bootstrap --legacy-tmux` | Start a legacy/debug tmux bootstrap session |
| `trinity attach` | Attach to a legacy `transport_mode = "tmux"` session |

### TUI Inline Commands

Inside the interactive TUI (`trinity` with no args):

| Command | Description |
| :--- | :--- |
| `<text>` | Ask agents to deliberate on a topic |
| `/status` | Show agent status |
| `/context` | Show shared context |
| `/rounds [N]` | Set max deliberation rounds (1–20) |
| `/agent <name> on\|off` | Enable/disable an agent |
| `/history` | Show deliberation history |
| `/save` | Save session results to file |
| `/resume [N\|latest\|ID]` | Select and resume a saved workflow session |
| `/help` | Show help |
| `/quit` | Exit Trinity |

The TUI starts with a new workflow session by default. The previous active
workflow is preserved in `.trinity/workflow/history/` and can be resumed
explicitly with `/resume`.

---

## ⚙️ Configuration

Edit `.trinity/trinity.config` (TOML format):

`trinity init` asks which model each agent should use and stores the matching
`context_budget` for known models. `model = "default"` keeps the local CLI's
default model and applies Trinity's conservative provider default budget.

```toml
[general]
session_name = "trinity"
lang = "en"
state_dir = ".trinity"
max_deliberation_rounds = 5
consensus_threshold = 0.6

[deliberation]
max_rounds = 5
consensus_threshold = 0.6
round_timeout_seconds = 120

[context]
rotate_threshold = 0.6
keep_sections = ["## Current Goal", "## Agreed Conclusion"]
recent_rounds_on_rotate = 3
summary_max_tokens = 500
prompt_compression_enabled = true
prompt_compression_round_threshold = 2
prompt_compression_max_summary_tokens = 200
caveman_mode = true
caveman_intensity = "full"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
model = "opus[1m]"
context_budget = 1000000
role_prompt = "You are the Architect. You design systems, review code..."
enabled = true
extra_args = ["--dangerously-skip-permissions"]

[agents.codex]
provider = "codex"
cli_command = "codex"
model = "gpt-5.1"
context_budget = 400000
role_prompt = "You are the Implementer. You write clean, efficient code..."
enabled = false                    # Disabled by default

[agents.antigravity]
provider = "antigravity-cli"
cli_command = "agy"
model = "default"
context_budget = 1000000
role_prompt = "You are the Reviewer. You explore alternatives..."
enabled = false                    # Disabled by default
```

---

## 🏗️ Architecture

```
trinity/
├── orchestrator.py         # Top-level coordinator — owns all components
├── cli.py                  # Click-based CLI entry point
├── config.py               # TOML config loader with defaults
├── models.py               # Core dataclasses (AgentSpec, DeliberationMessage, etc.)
│
├── agents/                 # Provider-specific agent wrappers
│   ├── base.py             #   AgentWrapper ABC
│   ├── claude_agent.py     #   Claude Code (print mode + interactive tmux)
│   ├── codex_agent.py      #   Codex (print mode + interactive tmux)
│   ├── antigravity_agent.py #   Antigravity CLI (one-shot print mode)
│   └── factory.py          #   AgentFactory — creates agents by provider
│
├── deliberation/           # The debate engine
│   ├── protocol.py         #   Round-based deliberation loop with event streaming
│   ├── consensus.py        #   Keyword-based agreement detection + negation filter
│   └── distributor.py      #   Maps consensus → agent tasks by strengths
│
├── context/                # Shared brain
│   ├── shared.py           #   SharedContextEngine — manages shared.md
│   ├── monitor.py          #   Token usage tracking per agent
│   └── rotator.py          #   Auto session rotation when context fills
│
├── completion/             # How we know an agent finished responding
│   ├── base.py             #   CompletionDetector ABC + FallbackChainDetector
│   ├── hook.py             #   Claude stop-hook file signal
│   ├── idle.py             #   Output stops changing detector
│   └── prompt.py           #   CLI prompt reappears detector
│
├── tui/                    # Interactive terminal UI
│   ├── app.py              #   TrinityTUI — Rich Live rendering engine
│   ├── session.py          #   InteractiveSession — input loop + event-driven updates
│   ├── events.py           #   TUIEventBus — thread-safe event bridge
│   └── theme.py            #   Per-agent visual themes (color, icon, role)
│
├── setup/                  # First-run experience
│   ├── detector.py         #   Auto-detect installed AI CLIs
│   └── wizard.py           #   Rich interactive setup wizard
│
├── tmux/                   # Interactive mode infrastructure
│   ├── pane.py             #   Low-level tmux pane I/O
│   ├── session.py          #   Session/pane lifecycle management
│   └── layout.py           #   TUI + agent split layout
│
├── workspace/              # Agent isolation
│   ├── isolation.py        #   Git worktree per agent (parallel editing)
│   └── managed_home.py     #   Per-agent isolated HOME directories
│
├── health/
│   └── checker.py          #   Agent health monitoring
│
├── retry.py                #   RetryConfig with exponential backoff + jitter
└── error_handler.py        #   Crash recovery and agent respawn
```

### Key Design Decisions

| Decision | Rationale |
| :--- | :--- |
| **Shared markdown file** | Agents read/write `shared.md` — simple, transparent, debuggable |
| **Round-based protocol** | Structured debate prevents circular arguments; forces progression |
| **Event-driven TUI** | `asyncio.wait(FIRST_COMPLETED)` + `Queue` enables real-time streaming |
| **Keyword consensus** | Fast, deterministic agreement detection with negation filtering |
| **Provider-agnostic agents** | `AgentWrapper` ABC — easy to add new AI providers |
| **Two execution modes** | Default one-shot provider calls plus legacy/debug tmux transport |

---

## 🔧 Prerequisites

| Requirement | Why | Required |
| :--- | :--- | :--- |
| **Python 3.10+** | Runtime | ✅ Yes |
| **Claude Code CLI** | Architect agent | Optional |
| **Codex CLI** | Implementer agent | Optional |
| **Antigravity CLI** | Reviewer agent | Optional |
| **tmux** | Legacy/debug transport or `bootstrap --legacy-tmux` | Optional |

> You need at least **one** AI CLI installed. Trinity auto-detects what's available during `trinity init`.

---

## 🧪 Development

```bash
# Clone and setup
git clone https://github.com/hongdangmoo49/Trinity.git
cd Trinity
uv sync

# Run tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=trinity --cov-report=term-missing
```

### Publishing

```bash
# After bumping pyproject.toml + src/trinity/__init__.py
uv build
uv publish --token <PYPI_TOKEN>
```

---

## 📊 Project Stats

| Metric | Value |
| :--- | :--- |
| **Version** | 0.9.2 |
| **Tests** | `uv run pytest` |
| **Coverage** | ~87% |
| **Source files** | 50+ |
| **Dependencies** | `click`, `rich`, `prompt_toolkit`, `tomli` |
| **Python** | 3.10+ |

---

## 📄 License

MIT License — see [LICENSE](https://github.com/hongdangmoo49/Trinity/blob/main/LICENSE).

---

<div align="center">

*"Three minds are better than one."*

**Trinity** — [`GitHub`](https://github.com/hongdangmoo49/Trinity) · [`PyPI`](https://pypi.org/project/trinity-agent/) · [`Issues`](https://github.com/hongdangmoo49/Trinity/issues)

</div>
