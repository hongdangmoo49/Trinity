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


# ---------------------------------------------------------------------------
# v0.7.0 Workflow Engine Data Models
# ---------------------------------------------------------------------------


class WorkflowState(str, Enum):
    """States of the workflow engine state machine."""

    IDLE = "idle"
    PREFLIGHT = "preflight"
    DELIBERATING = "deliberating"
    NEEDS_USER_DECISION = "needs_user_decision"
    BLUEPRINT_READY = "blueprint_ready"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    DONE = "done"
    FAILED = "failed"


class ProviderState(str, Enum):
    """Readiness state of a single AI provider / CLI."""

    READY = "ready"
    AUTH_REQUIRED = "auth_required"
    MODEL_LOADING = "model_loading"
    WORKSPACE_TRUST_REQUIRED = "workspace_trust_required"
    CLI_BANNER_ONLY = "cli_banner_only"
    PROMPT_NOT_SENT = "prompt_not_sent"
    PROCESS_DEAD = "process_dead"
    UNKNOWN_NOT_READY = "unknown_not_ready"


class VoteType(str, Enum):
    """Vote cast by an agent during structured consensus."""

    APPROVE = "approve"
    APPROVE_WITH_CHANGES = "approve_with_changes"
    BLOCKED_BY_QUESTION = "blocked_by_question"
    REJECT = "reject"


class WorkStatus(str, Enum):
    """Status of a work package or execution result."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_ON_DECISION = "waiting_on_decision"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ReadinessResult:
    """Readiness check result for a single agent."""

    agent_name: str
    ready: bool
    state: ProviderState
    reason: str
    action_hint: str
    excerpt: str = ""


@dataclass
class ArchitectureComponent:
    """A single component in the architecture blueprint."""

    name: str
    responsibility: str
    owner_agent: str | None = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class OpenQuestion:
    """An open question that needs resolution before/during execution."""

    id: str
    question: str
    options: list[str] = field(default_factory=list)
    recommended_option: str | None = None
    blocking: bool = True
    raised_by: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "options": self.options,
            "recommended_option": self.recommended_option,
            "blocking": self.blocking,
            "raised_by": self.raised_by,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpenQuestion:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DecisionRecord:
    """A decision made during the workflow (by user or agents)."""

    id: str
    decision: str
    decided_by: str
    rationale: str = ""
    question_id: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "rationale": self.rationale,
            "question_id": self.question_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Blueprint:
    """Architecture blueprint produced during deliberation."""

    title: str
    summary: str
    architecture: list[ArchitectureComponent]
    data_flow: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    open_questions: list[OpenQuestion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "architecture": [
                {"name": c.name, "responsibility": c.responsibility,
                 "owner_agent": c.owner_agent, "dependencies": c.dependencies}
                for c in self.architecture
            ],
            "data_flow": self.data_flow,
            "external_dependencies": self.external_dependencies,
            "risks": self.risks,
            "acceptance_criteria": self.acceptance_criteria,
            "open_questions": [q.to_dict() for q in self.open_questions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Blueprint:
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "architecture" in filtered:
            filtered["architecture"] = [
                ArchitectureComponent(**{k: v for k, v in a.items() if k in ArchitectureComponent.__dataclass_fields__})
                for a in filtered["architecture"]
            ]
        if "open_questions" in filtered:
            filtered["open_questions"] = [
                OpenQuestion.from_dict(q) for q in filtered["open_questions"]
            ]
        return cls(**filtered)


@dataclass
class StructuredConsensusResult:
    """Result of structured consensus voting on a blueprint."""

    reached: bool
    vote_count: dict[str, int]
    final_blueprint: Blueprint | None
    open_questions: list[OpenQuestion]
    blockers: list[str] = field(default_factory=list)


@dataclass
class WorkPackage:
    """A discrete unit of work assigned to a single agent."""

    id: str
    title: str
    owner_agent: str
    objective: str
    scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    expected_files: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    status: WorkStatus = WorkStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "owner_agent": self.owner_agent,
            "objective": self.objective,
            "scope": self.scope,
            "out_of_scope": self.out_of_scope,
            "dependencies": self.dependencies,
            "expected_files": self.expected_files,
            "acceptance_criteria": self.acceptance_criteria,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkPackage:
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        if "status" in filtered and isinstance(filtered["status"], str):
            filtered["status"] = WorkStatus(filtered["status"])
        return cls(**filtered)


@dataclass
class ExecutionResult:
    """Result of executing a work package."""

    package_id: str
    agent_name: str
    status: WorkStatus
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)
    decisions_made: list[DecisionRecord] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass
class WorkflowEvent:
    """An event in the workflow timeline."""

    event_type: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowEvent:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WorkflowSession:
    """Full state of a workflow session (serializable for persistence)."""

    id: str
    goal: str
    state: WorkflowState = WorkflowState.IDLE
    active_agents: list[str] = field(default_factory=list)
    current_round: int = 0
    pending_questions: list[OpenQuestion] = field(default_factory=list)
    blueprint: Blueprint | None = None
    work_packages: list[WorkPackage] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    execution_results: list[ExecutionResult] = field(default_factory=list)
    events: list[WorkflowEvent] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "state": self.state.value,
            "active_agents": self.active_agents,
            "current_round": self.current_round,
            "pending_questions": [q.to_dict() for q in self.pending_questions],
            "blueprint": self.blueprint.to_dict() if self.blueprint else None,
            "work_packages": [wp.to_dict() for wp in self.work_packages],
            "decisions": [d.to_dict() for d in self.decisions],
            "execution_results": [
                {
                    "package_id": r.package_id,
                    "agent_name": r.agent_name,
                    "status": r.status.value,
                    "summary": r.summary,
                    "files_changed": r.files_changed,
                    "decisions_made": [d.to_dict() for d in r.decisions_made],
                    "blockers": r.blockers,
                }
                for r in self.execution_results
            ],
            "events": [e.to_dict() for e in self.events],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowSession:
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}

        if "state" in filtered and isinstance(filtered["state"], str):
            filtered["state"] = WorkflowState(filtered["state"])

        if "pending_questions" in filtered:
            filtered["pending_questions"] = [
                OpenQuestion.from_dict(q) for q in filtered["pending_questions"]
            ]

        if "blueprint" in filtered and filtered["blueprint"] is not None:
            filtered["blueprint"] = Blueprint.from_dict(filtered["blueprint"])

        if "work_packages" in filtered:
            filtered["work_packages"] = [
                WorkPackage.from_dict(wp) for wp in filtered["work_packages"]
            ]

        if "decisions" in filtered:
            filtered["decisions"] = [
                DecisionRecord.from_dict(d) for d in filtered["decisions"]
            ]

        if "execution_results" in filtered:
            results = []
            for r in filtered["execution_results"]:
                er = {k: v for k, v in r.items() if k in ExecutionResult.__dataclass_fields__}
                if "status" in er and isinstance(er["status"], str):
                    er["status"] = WorkStatus(er["status"])
                if "decisions_made" in er:
                    er["decisions_made"] = [DecisionRecord.from_dict(d) for d in er["decisions_made"]]
                results.append(ExecutionResult(**er))
            filtered["execution_results"] = results

        if "events" in filtered:
            filtered["events"] = [
                WorkflowEvent.from_dict(e) for e in filtered["events"]
            ]

        return cls(**filtered)
