"""Workflow state models for v0.7.0 stateful sessions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from trinity.resources.models import AgentResourceProjection


class WorkflowState(str, Enum):
    """Lifecycle state for a Trinity workflow."""

    IDLE = "idle"
    PREFLIGHT = "preflight"
    DELIBERATING = "deliberating"
    NEEDS_USER_DECISION = "needs_user_decision"
    BLUEPRINT_READY = "blueprint_ready"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    POST_REVIEW_READY = "post_review_ready"
    IMPROVING = "improving"
    DONE = "done"
    FAILED = "failed"


class WorkStatus(str, Enum):
    """Lifecycle state for a workflow work package."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_ON_DECISION = "waiting_on_decision"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class PostReviewActionStatus(str, Enum):
    """Lifecycle state for a review follow-up action item."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IGNORED = "ignored"
    QUEUED = "queued"
    DONE = "done"


@dataclass
class ProviderSessionRef:
    """Provider-native conversation/session id mapped to a Trinity workflow."""

    provider: str
    agent_name: str
    session_key: str
    provider_session_id: str
    session_kind: str = ""
    lane: str = ""
    access: str = ""
    cwd: str = ""
    configured_model: str = ""
    resolved_model: str = ""
    last_request_id: str = ""
    last_observed_at: float = field(default_factory=time.time)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "agent_name": self.agent_name,
            "session_key": self.session_key,
            "provider_session_id": self.provider_session_id,
            "session_kind": self.session_kind,
            "lane": self.lane,
            "access": self.access,
            "cwd": self.cwd,
            "configured_model": self.configured_model,
            "resolved_model": self.resolved_model,
            "last_request_id": self.last_request_id,
            "last_observed_at": self.last_observed_at,
            "diagnostics": list(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProviderSessionRef":
        return cls(
            provider=str(data.get("provider", "")),
            agent_name=str(data.get("agent_name", "")),
            session_key=str(data.get("session_key", "")),
            provider_session_id=str(data.get("provider_session_id", "")),
            session_kind=str(data.get("session_kind", "")),
            lane=str(data.get("lane", "")),
            access=str(data.get("access", "")),
            cwd=str(data.get("cwd", "")),
            configured_model=str(data.get("configured_model", "")),
            resolved_model=str(data.get("resolved_model", "")),
            last_request_id=str(data.get("last_request_id", "")),
            last_observed_at=float(data.get("last_observed_at", time.time())),
            diagnostics=[str(item) for item in data.get("diagnostics", [])],
        )


@dataclass
class AgentRuntimeModel:
    """Observed provider model and context metadata for one agent."""

    provider: str
    agent_name: str
    configured_model: str = ""
    actual_model: str = ""
    model_label: str = ""
    context_window: int = 0
    max_output_tokens: int = 0
    budget_source: str = "unsupported"
    confidence: str = "unknown"
    observed_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "agent_name": self.agent_name,
            "configured_model": self.configured_model,
            "actual_model": self.actual_model,
            "model_label": self.model_label,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "budget_source": self.budget_source,
            "confidence": self.confidence,
            "observed_at": self.observed_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRuntimeModel":
        return cls(
            provider=str(data.get("provider", "")),
            agent_name=str(data.get("agent_name", "")),
            configured_model=str(data.get("configured_model", "")),
            actual_model=str(data.get("actual_model", "")),
            model_label=str(data.get("model_label", "")),
            context_window=int(data.get("context_window", 0) or 0),
            max_output_tokens=int(data.get("max_output_tokens", 0) or 0),
            budget_source=str(data.get("budget_source", "unsupported")),
            confidence=str(data.get("confidence", "unknown")),
            observed_at=float(data.get("observed_at", time.time())),
            metadata=(
                dict(data.get("metadata", {}))
                if isinstance(data.get("metadata"), dict)
                else {}
            ),
        )


@dataclass
class OpenQuestion:
    """A user-facing decision point raised by agents or workflow logic."""

    id: str
    question: str
    options: list[str] = field(default_factory=list)
    recommended_option: str | None = None
    blocking: bool = True
    raised_by: list[str] = field(default_factory=list)
    rationale: str = ""
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "options": list(self.options),
            "recommended_option": self.recommended_option,
            "blocking": self.blocking,
            "raised_by": list(self.raised_by),
            "rationale": self.rationale,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpenQuestion":
        return cls(
            id=str(data.get("id", "")),
            question=str(data.get("question", "")),
            options=[str(item) for item in data.get("options", [])],
            recommended_option=(
                str(data["recommended_option"])
                if data.get("recommended_option") is not None
                else None
            ),
            blocking=bool(data.get("blocking", True)),
            raised_by=[str(item) for item in data.get("raised_by", [])],
            rationale=str(data.get("rationale", "")),
            status=str(data.get("status", "open")),
        )


@dataclass
class DecisionRecord:
    """A resolved decision that must stay attached to the workflow."""

    id: str
    decision: str
    question_id: str | None = None
    decided_by: str = "user"
    rationale: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question_id": self.question_id,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionRecord":
        return cls(
            id=str(data.get("id", "")),
            question_id=(str(data["question_id"]) if data.get("question_id") is not None else None),
            decision=str(data.get("decision", "")),
            decided_by=str(data.get("decided_by", "user")),
            rationale=str(data.get("rationale", "")),
            timestamp=float(data.get("timestamp", time.time())),
        )


@dataclass
class ArchitectureComponent:
    """A major component in a proposed blueprint."""

    name: str
    responsibility: str
    owner_agent: str | None = None
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "responsibility": self.responsibility,
            "owner_agent": self.owner_agent,
            "dependencies": list(self.dependencies),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArchitectureComponent":
        return cls(
            name=str(data.get("name", "")),
            responsibility=str(data.get("responsibility", "")),
            owner_agent=(str(data["owner_agent"]) if data.get("owner_agent") is not None else None),
            dependencies=[str(dep) for dep in data.get("dependencies", [])],
        )


@dataclass
class RiskItem:
    """A risk captured from a proposed blueprint."""

    description: str
    severity: str = "medium"
    mitigation: str = ""
    owner_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "severity": self.severity,
            "mitigation": self.mitigation,
            "owner_agent": self.owner_agent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskItem":
        return cls(
            description=str(data.get("description", "")),
            severity=str(data.get("severity", "medium")),
            mitigation=str(data.get("mitigation", "")),
            owner_agent=(str(data["owner_agent"]) if data.get("owner_agent") is not None else None),
        )


@dataclass
class Blueprint:
    """Structured design conclusion produced by deliberation."""

    title: str
    summary: str
    architecture: list[ArchitectureComponent] = field(default_factory=list)
    data_flow: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    open_questions: list[OpenQuestion] = field(default_factory=list)
    work_packages: list[WorkPackage] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return whether this blueprint has enough substance to finalize."""
        has_design_detail = any(
            (
                self.architecture,
                self.data_flow,
                self.external_dependencies,
                self.acceptance_criteria,
            )
        )
        return bool(self.title.strip() and self.summary.strip() and has_design_detail)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "architecture": [item.to_dict() for item in self.architecture],
            "data_flow": list(self.data_flow),
            "external_dependencies": list(self.external_dependencies),
            "risks": [item.to_dict() for item in self.risks],
            "acceptance_criteria": list(self.acceptance_criteria),
            "open_questions": [item.to_dict() for item in self.open_questions],
            "work_packages": [item.to_dict() for item in self.work_packages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Blueprint":
        return cls(
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            architecture=[
                ArchitectureComponent.from_dict(item)
                for item in data.get("architecture", [])
                if isinstance(item, dict)
            ],
            data_flow=[str(item) for item in data.get("data_flow", [])],
            external_dependencies=[str(item) for item in data.get("external_dependencies", [])],
            risks=[
                RiskItem.from_dict(item) for item in data.get("risks", []) if isinstance(item, dict)
            ],
            acceptance_criteria=[str(item) for item in data.get("acceptance_criteria", [])],
            open_questions=[
                OpenQuestion.from_dict(item)
                for item in data.get("open_questions", [])
                if isinstance(item, dict)
            ],
            work_packages=[
                WorkPackage.from_dict(item)
                for item in data.get("work_packages", [])
                if isinstance(item, dict)
            ],
        )


@dataclass
class WorkPackage:
    """An agent-owned top-level package derived from a blueprint."""

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
    requires_execution: bool = True
    estimated_weight: int = 1
    parallel_group: int | None = None
    parallelizable: bool = True
    risk: str = "medium"
    repair_notes: list[str] = field(default_factory=list)
    repair_attempt_count: int = 0
    last_repair_signature: str = ""
    last_repair_review_id: str = ""
    repair_blocked_reason: str = ""
    repair_blocked_at: float = 0.0
    current_executor: str = ""
    last_executor: str = ""
    origin: str = "initial"
    origin_action_item_ids: list[str] = field(default_factory=list)
    parent_package_ids: list[str] = field(default_factory=list)
    supplemental_round: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "owner_agent": self.owner_agent,
            "objective": self.objective,
            "scope": list(self.scope),
            "out_of_scope": list(self.out_of_scope),
            "dependencies": list(self.dependencies),
            "expected_files": list(self.expected_files),
            "acceptance_criteria": list(self.acceptance_criteria),
            "status": self.status.value,
            "requires_execution": self.requires_execution,
            "estimated_weight": self.estimated_weight,
            "parallel_group": self.parallel_group,
            "parallelizable": self.parallelizable,
            "risk": self.risk,
            "repair_notes": list(self.repair_notes),
            "repair_attempt_count": self.repair_attempt_count,
            "last_repair_signature": self.last_repair_signature,
            "last_repair_review_id": self.last_repair_review_id,
            "repair_blocked_reason": self.repair_blocked_reason,
            "repair_blocked_at": self.repair_blocked_at,
            "current_executor": self.current_executor,
            "last_executor": self.last_executor,
            "origin": self.origin,
            "origin_action_item_ids": list(self.origin_action_item_ids),
            "parent_package_ids": list(self.parent_package_ids),
            "supplemental_round": self.supplemental_round,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPackage":
        status_value = str(data.get("status", WorkStatus.PENDING.value))
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            owner_agent=str(data.get("owner_agent", "")),
            objective=str(data.get("objective", "")),
            scope=[str(item) for item in data.get("scope", [])],
            out_of_scope=[str(item) for item in data.get("out_of_scope", [])],
            dependencies=[str(item) for item in data.get("dependencies", [])],
            expected_files=[str(item) for item in data.get("expected_files", [])],
            acceptance_criteria=[str(item) for item in data.get("acceptance_criteria", [])],
            status=WorkStatus(status_value),
            requires_execution=bool(data.get("requires_execution", True)),
            estimated_weight=max(1, int(data.get("estimated_weight", 1))),
            parallel_group=(
                int(data["parallel_group"]) if data.get("parallel_group") is not None else None
            ),
            parallelizable=bool(data.get("parallelizable", True)),
            risk=str(data.get("risk", "medium") or "medium"),
            repair_notes=[str(item) for item in data.get("repair_notes", [])],
            repair_attempt_count=max(0, int(data.get("repair_attempt_count", 0) or 0)),
            last_repair_signature=str(data.get("last_repair_signature", "") or ""),
            last_repair_review_id=str(data.get("last_repair_review_id", "") or ""),
            repair_blocked_reason=str(data.get("repair_blocked_reason", "") or ""),
            repair_blocked_at=float(data.get("repair_blocked_at", 0.0) or 0.0),
            current_executor=str(data.get("current_executor", "") or ""),
            last_executor=str(data.get("last_executor", "") or ""),
            origin=str(data.get("origin", "initial") or "initial"),
            origin_action_item_ids=[
                str(item) for item in data.get("origin_action_item_ids", [])
            ],
            parent_package_ids=[str(item) for item in data.get("parent_package_ids", [])],
            supplemental_round=int(data.get("supplemental_round", 0) or 0),
        )


@dataclass
class SubtaskResult:
    """Report from a parent agent about provider-internal delegation."""

    id: str
    parent_package_id: str
    parent_agent: str
    delegated_to: str
    objective: str
    result_summary: str
    status: WorkStatus
    decisions_made: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    unresolved_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "parent_package_id": self.parent_package_id,
            "parent_agent": self.parent_agent,
            "delegated_to": self.delegated_to,
            "objective": self.objective,
            "result_summary": self.result_summary,
            "status": self.status.value,
            "decisions_made": list(self.decisions_made),
            "files_changed": list(self.files_changed),
            "unresolved_issues": list(self.unresolved_issues),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubtaskResult":
        status_value = str(data.get("status", WorkStatus.DONE.value))
        return cls(
            id=str(data.get("id", "")),
            parent_package_id=str(data.get("parent_package_id", "")),
            parent_agent=str(data.get("parent_agent", "")),
            delegated_to=str(data.get("delegated_to", "")),
            objective=str(data.get("objective", "")),
            result_summary=str(data.get("result_summary", "")),
            status=WorkStatus(status_value),
            decisions_made=[str(item) for item in data.get("decisions_made", [])],
            files_changed=[str(item) for item in data.get("files_changed", [])],
            unresolved_issues=[str(item) for item in data.get("unresolved_issues", [])],
        )


@dataclass
class ExecutionResult:
    """Result reported by an agent after executing one work package."""

    package_id: str
    agent_name: str
    status: WorkStatus
    summary: str = ""
    files_changed: list[str] = field(default_factory=list)
    decisions_made: list[DecisionRecord] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    follow_up: list[str] = field(default_factory=list)
    subtasks: list[SubtaskResult] = field(default_factory=list)
    raw_response_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "summary": self.summary,
            "files_changed": list(self.files_changed),
            "decisions_made": [decision.to_dict() for decision in self.decisions_made],
            "blockers": list(self.blockers),
            "follow_up": list(self.follow_up),
            "subtasks": [subtask.to_dict() for subtask in self.subtasks],
            "raw_response_path": (str(self.raw_response_path) if self.raw_response_path else None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionResult":
        status_value = str(data.get("status", WorkStatus.FAILED.value))
        raw_path = data.get("raw_response_path")
        return cls(
            package_id=str(data.get("package_id", "")),
            agent_name=str(data.get("agent_name", "")),
            status=WorkStatus(status_value),
            summary=str(data.get("summary", "")),
            files_changed=[str(item) for item in data.get("files_changed", [])],
            decisions_made=[
                DecisionRecord.from_dict(item)
                for item in data.get("decisions_made", [])
                if isinstance(item, dict)
            ],
            blockers=[str(item) for item in data.get("blockers", [])],
            follow_up=[str(item) for item in data.get("follow_up", [])],
            subtasks=[
                SubtaskResult.from_dict(item)
                for item in data.get("subtasks", [])
                if isinstance(item, dict)
            ],
            raw_response_path=Path(str(raw_path)) if raw_path else None,
        )


@dataclass
class PostReviewActionItem:
    """A user-selectable follow-up item extracted after final review."""

    id: str
    source: str
    kind: str
    severity: str
    title: str
    summary: str
    rationale: str = ""
    related_wp_ids: list[str] = field(default_factory=list)
    related_review_ids: list[str] = field(default_factory=list)
    suggested_owner: str = ""
    requires_execution: bool = True
    status: PostReviewActionStatus = PostReviewActionStatus.PROPOSED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "summary": self.summary,
            "rationale": self.rationale,
            "related_wp_ids": list(self.related_wp_ids),
            "related_review_ids": list(self.related_review_ids),
            "suggested_owner": self.suggested_owner,
            "requires_execution": self.requires_execution,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostReviewActionItem":
        status_value = str(data.get("status", PostReviewActionStatus.PROPOSED.value))
        try:
            status = PostReviewActionStatus(status_value)
        except ValueError:
            status = PostReviewActionStatus.PROPOSED
        return cls(
            id=str(data.get("id", "")),
            source=str(data.get("source", "")),
            kind=str(data.get("kind", "enhancement") or "enhancement"),
            severity=str(data.get("severity", "medium") or "medium"),
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            rationale=str(data.get("rationale", "")),
            related_wp_ids=[str(item) for item in data.get("related_wp_ids", [])],
            related_review_ids=[str(item) for item in data.get("related_review_ids", [])],
            suggested_owner=str(data.get("suggested_owner", "") or ""),
            requires_execution=bool(data.get("requires_execution", True)),
            status=status,
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )


@dataclass
class WorkflowSession:
    """Persisted state for one stateful workflow."""

    id: str
    goal: str
    state: WorkflowState
    active_agents: list[str] = field(default_factory=list)
    last_target_agents: list[str] = field(default_factory=list)
    agent_model_overrides: dict[str, str] = field(default_factory=dict)
    current_round: int = 0
    target_workspace: Path | None = None
    control_repo_target_confirmed: bool = False
    pending_questions: list[OpenQuestion] = field(default_factory=list)
    blueprint: Blueprint | None = None
    work_packages: list[WorkPackage] = field(default_factory=list)
    execution_results: list[ExecutionResult] = field(default_factory=list)
    subtask_results: list[SubtaskResult] = field(default_factory=list)
    review_packages: list[dict[str, Any]] = field(default_factory=list)
    review_results: list[dict[str, Any]] = field(default_factory=list)
    post_review_items: list[dict[str, Any]] = field(default_factory=list)
    follow_up_requests: list[dict[str, Any]] = field(default_factory=list)
    supplemental_round: int = 0
    decisions: list[DecisionRecord] = field(default_factory=list)
    execution_run: dict[str, Any] = field(default_factory=dict)
    provider_sessions: dict[str, ProviderSessionRef] = field(default_factory=dict)
    runtime_models: dict[str, AgentRuntimeModel] = field(default_factory=dict)
    resource_projections: dict[str, AgentResourceProjection] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @property
    def open_questions(self) -> list[OpenQuestion]:
        """Return unanswered questions."""
        return [q for q in self.pending_questions if q.status == "open"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "state": self.state.value,
            "active_agents": list(self.active_agents),
            "last_target_agents": list(self.last_target_agents),
            "agent_model_overrides": dict(self.agent_model_overrides),
            "current_round": self.current_round,
            "target_workspace": (str(self.target_workspace) if self.target_workspace else None),
            "control_repo_target_confirmed": self.control_repo_target_confirmed,
            "pending_questions": [q.to_dict() for q in self.pending_questions],
            "blueprint": self.blueprint.to_dict() if self.blueprint else None,
            "work_packages": [package.to_dict() for package in self.work_packages],
            "execution_results": [result.to_dict() for result in self.execution_results],
            "subtask_results": [result.to_dict() for result in self.subtask_results],
            "review_packages": [dict(item) for item in self.review_packages],
            "review_results": [dict(item) for item in self.review_results],
            "post_review_items": [dict(item) for item in self.post_review_items],
            "follow_up_requests": [dict(item) for item in self.follow_up_requests],
            "supplemental_round": self.supplemental_round,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "execution_run": dict(self.execution_run),
            "provider_sessions": {
                key: value.to_dict()
                for key, value in self.provider_sessions.items()
            },
            "runtime_models": {
                key: value.to_dict()
                for key, value in self.runtime_models.items()
            },
            "resource_projections": {
                key: value.to_dict()
                for key, value in self.resource_projections.items()
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowSession":
        state_value = str(data.get("state", WorkflowState.IDLE.value))
        return cls(
            id=str(data.get("id", "")),
            goal=str(data.get("goal", "")),
            state=WorkflowState(state_value),
            active_agents=[str(item) for item in data.get("active_agents", [])],
            last_target_agents=[
                str(item) for item in data.get("last_target_agents", [])
            ],
            agent_model_overrides={
                str(key): str(value)
                for key, value in data.get("agent_model_overrides", {}).items()
            }
            if isinstance(data.get("agent_model_overrides", {}), dict)
            else {},
            current_round=int(data.get("current_round", 0)),
            target_workspace=(
                Path(str(data["target_workspace"]))
                if data.get("target_workspace") is not None
                else None
            ),
            control_repo_target_confirmed=bool(data.get("control_repo_target_confirmed", False)),
            pending_questions=[
                OpenQuestion.from_dict(item)
                for item in data.get("pending_questions", [])
                if isinstance(item, dict)
            ],
            blueprint=(
                Blueprint.from_dict(data["blueprint"])
                if isinstance(data.get("blueprint"), dict)
                else None
            ),
            work_packages=[
                WorkPackage.from_dict(item)
                for item in data.get("work_packages", [])
                if isinstance(item, dict)
            ],
            execution_results=[
                ExecutionResult.from_dict(item)
                for item in data.get("execution_results", [])
                if isinstance(item, dict)
            ],
            subtask_results=[
                SubtaskResult.from_dict(item)
                for item in data.get("subtask_results", [])
                if isinstance(item, dict)
            ],
            review_packages=[
                dict(item) for item in data.get("review_packages", []) if isinstance(item, dict)
            ],
            review_results=[
                dict(item) for item in data.get("review_results", []) if isinstance(item, dict)
            ],
            post_review_items=[
                dict(item) for item in data.get("post_review_items", []) if isinstance(item, dict)
            ],
            follow_up_requests=[
                dict(item)
                for item in data.get("follow_up_requests", [])
                if isinstance(item, dict)
            ],
            supplemental_round=int(data.get("supplemental_round", 0) or 0),
            decisions=[
                DecisionRecord.from_dict(item)
                for item in data.get("decisions", [])
                if isinstance(item, dict)
            ],
            execution_run=(
                dict(data.get("execution_run", {}))
                if isinstance(data.get("execution_run"), dict)
                else {}
            ),
            provider_sessions={
                str(key): ProviderSessionRef.from_dict(value)
                for key, value in (
                    data.get("provider_sessions", {})
                    if isinstance(data.get("provider_sessions"), dict)
                    else {}
                ).items()
                if isinstance(value, dict)
            },
            runtime_models={
                str(key): AgentRuntimeModel.from_dict(value)
                for key, value in (
                    data.get("runtime_models", {})
                    if isinstance(data.get("runtime_models"), dict)
                    else {}
                ).items()
                if isinstance(value, dict)
            },
            resource_projections={
                str(key): AgentResourceProjection.from_dict(value)
                for key, value in (
                    data.get("resource_projections", {})
                    if isinstance(data.get("resource_projections"), dict)
                    else {}
                ).items()
                if isinstance(value, dict)
            },
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )
