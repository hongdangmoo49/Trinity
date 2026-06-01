"""Trinity data models — all core dataclasses."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MessageRole(str, Enum):
    """Role of a deliberation message."""

    OPINION = "opinion"
    COUNTER = "counter"
    AGREEMENT = "agreement"
    CONSENSUS = "consensus"
    TASK = "task"
    SUMMARY = "summary"
    SYSTEM = "system"


class Provider(str, Enum):
    """Supported AI CLI providers."""

    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    GEMINI_CLI = "gemini-cli"


@dataclass
class AgentSpec:
    """Configuration for a single agent."""

    name: str
    provider: Provider
    cli_command: str
    role_prompt: str = ""
    role_file: Path | None = None
    workspace_mode: str = "inplace"  # "inplace" | "git-worktree"
    branch_template: str = "trinity/{agent_name}"
    context_budget: int = 0  # 0 = auto-detect from provider defaults
    enabled: bool = True
    extra_args: list[str] = field(default_factory=list)

    # Provider-default context budgets (tokens)
    _DEFAULT_BUDGETS: dict[str, int] = field(
        default_factory=lambda: {
            Provider.CLAUDE_CODE: 200_000,
            Provider.CODEX: 128_000,
            Provider.GEMINI_CLI: 1_000_000,
        },
        repr=False,
        compare=False,
    )

    @property
    def effective_context_budget(self) -> int:
        """Return explicit budget if set, otherwise provider default."""
        if self.context_budget > 0:
            return self.context_budget
        return self._DEFAULT_BUDGETS.get(self.provider, 200_000)


@dataclass
class DeliberationMessage:
    """A single message exchanged during deliberation."""

    source: str  # agent name or "user"
    target: str  # "all" or specific agent name
    round_num: int
    role: MessageRole
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return self.metadata.get("token_count", 0)


@dataclass
class ContextUsage:
    """Token usage tracking for context limit management."""

    used: int = 0
    total: int = 200_000

    @property
    def ratio(self) -> float:
        return self.used / self.total if self.total > 0 else 0.0

    @property
    def should_rotate(self) -> bool:
        return self.ratio >= 0.60

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.used)

    def __str__(self) -> str:
        pct = self.ratio * 100
        return f"{self.used:,}/{self.total:,} ({pct:.1f}%)"


@dataclass
class ConsensusResult:
    """Result of consensus evaluation."""

    reached: bool
    agreement_count: int
    total_agents: int
    opinions: dict[str, str]  # agent_name → opinion text
    summary: str = ""

    @property
    def fraction(self) -> float:
        return self.agreement_count / self.total_agents if self.total_agents > 0 else 0.0


@dataclass
class TaskAssignment:
    """A task assigned to a specific agent."""

    agent_name: str
    task_description: str
    priority: int = 0  # higher = more important


@dataclass
class DeliberationResult:
    """Complete result of a deliberation session."""

    user_prompt: str
    rounds_completed: int
    consensus: ConsensusResult | None
    tasks: list[TaskAssignment] = field(default_factory=list)
    total_tokens_used: int = 0
    duration_seconds: float = 0.0

    @property
    def has_consensus(self) -> bool:
        return self.consensus is not None and self.consensus.reached


@dataclass
class AgentHealth:
    """Health status of a single agent."""

    name: str
    alive: bool = False
    context_ratio: float = 0.0
    last_activity: float = 0.0
    status: str = "unknown"  # "idle", "working", "error", "unknown"

    @property
    def context_warning(self) -> bool:
        return self.context_ratio >= 0.60
