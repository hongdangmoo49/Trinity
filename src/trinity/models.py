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


@dataclass(frozen=True)
class ModelContextSpec:
    """Known model context metadata used by setup and budget checks."""

    model: str
    display_name: str
    context_budget: int
    note: str = ""


PROVIDER_MODEL_CONTEXTS: dict[Provider, tuple[ModelContextSpec, ...]] = {
    Provider.CLAUDE_CODE: (
        ModelContextSpec(
            model="default",
            display_name="Default account model",
            context_budget=200_000,
            note="Account-dependent; conservative fallback",
        ),
        ModelContextSpec(
            model="opus",
            display_name="Opus alias",
            context_budget=1_000_000,
            note="1M when extended context is available",
        ),
        ModelContextSpec(
            model="opus[1m]",
            display_name="Opus 1M alias",
            context_budget=1_000_000,
        ),
        ModelContextSpec(
            model="sonnet",
            display_name="Sonnet alias",
            context_budget=200_000,
        ),
        ModelContextSpec(
            model="sonnet[1m]",
            display_name="Sonnet 1M alias",
            context_budget=1_000_000,
        ),
        ModelContextSpec(
            model="opusplan",
            display_name="Opus plan mode",
            context_budget=200_000,
            note="Plan-mode Opus remains 200K",
        ),
    ),
    Provider.CODEX: (
        ModelContextSpec(
            model="default",
            display_name="Codex CLI default",
            context_budget=128_000,
            note="Conservative fallback when local Codex config owns model choice",
        ),
        ModelContextSpec(
            model="gpt-5.1",
            display_name="GPT-5.1",
            context_budget=400_000,
        ),
        ModelContextSpec(
            model="gpt-5",
            display_name="GPT-5",
            context_budget=400_000,
        ),
    ),
    Provider.GEMINI_CLI: (
        ModelContextSpec(
            model="default",
            display_name="Gemini CLI default",
            context_budget=1_000_000,
        ),
        ModelContextSpec(
            model="gemini-2.5-pro",
            display_name="Gemini 2.5 Pro",
            context_budget=1_000_000,
        ),
        ModelContextSpec(
            model="gemini-2.5-flash",
            display_name="Gemini 2.5 Flash",
            context_budget=1_000_000,
        ),
        ModelContextSpec(
            model="gemini-2.0-flash",
            display_name="Gemini 2.0 Flash",
            context_budget=1_000_000,
        ),
    ),
}


PROVIDER_DEFAULT_MODELS: dict[Provider, str] = {
    Provider.CLAUDE_CODE: "default",
    Provider.CODEX: "default",
    Provider.GEMINI_CLI: "default",
}


def provider_model_choices(provider: Provider) -> tuple[ModelContextSpec, ...]:
    """Return known model choices for a provider."""
    return PROVIDER_MODEL_CONTEXTS.get(provider, ())


def model_context_budget(provider: Provider, model: str) -> int | None:
    """Return known context budget for a provider/model pair."""
    normalized = (model or PROVIDER_DEFAULT_MODELS.get(provider, "default")).strip()
    for spec in provider_model_choices(provider):
        if spec.model == normalized:
            return spec.context_budget
    return None


def provider_default_budget(provider: Provider) -> int:
    """Return the default context budget for a provider."""
    default_model = PROVIDER_DEFAULT_MODELS.get(provider, "default")
    return model_context_budget(provider, default_model) or 200_000


class TaskIntent(str, Enum):
    """Whether a task plan is design-only or intended for later execution."""

    PLAN = "plan"
    DESIGN_ONLY = "design_only"
    EXECUTION = "execution"


@dataclass
class AgentSpec:
    """Configuration for a single agent."""

    name: str
    provider: Provider
    cli_command: str
    model: str = "default"
    role_prompt: str = ""
    role_file: Path | None = None
    workspace_mode: str = "inplace"  # "inplace" | "git-worktree"
    branch_template: str = "trinity/{agent_name}"
    context_budget: int = 0  # 0 = auto-detect from provider defaults
    enabled: bool = True
    extra_args: list[str] = field(default_factory=list)

    @property
    def effective_context_budget(self) -> int:
        """Return explicit budget, known model budget, or provider default."""
        if self.context_budget > 0:
            return self.context_budget
        return (
            model_context_budget(self.provider, self.model)
            or provider_default_budget(self.provider)
        )


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

    def should_rotate(self, threshold: float = 0.60) -> bool:
        """Check if context usage exceeds rotation threshold."""
        return self.ratio >= threshold

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
    """A planned task assigned to a specific agent."""

    agent_name: str
    task_description: str
    priority: int = 0  # higher = more important
    intent: TaskIntent = TaskIntent.PLAN
    requires_execution: bool = False

    @property
    def design_only(self) -> bool:
        """Return True when this task should stay in planning/design mode."""
        return self.intent == TaskIntent.DESIGN_ONLY


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

    def context_warning(self, threshold: float = 0.60) -> bool:
        """Check if context usage exceeds warning threshold."""
        return self.context_ratio >= threshold
