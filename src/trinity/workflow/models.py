"""Workflow state models for v0.7.0 stateful sessions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class WorkflowState(str, Enum):
    """Lifecycle state for a Trinity workflow."""

    IDLE = "idle"
    PREFLIGHT = "preflight"
    DELIBERATING = "deliberating"
    NEEDS_USER_DECISION = "needs_user_decision"
    BLUEPRINT_READY = "blueprint_ready"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
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
            question_id=(
                str(data["question_id"]) if data.get("question_id") is not None else None
            ),
            decision=str(data.get("decision", "")),
            decided_by=str(data.get("decided_by", "user")),
            rationale=str(data.get("rationale", "")),
            timestamp=float(data.get("timestamp", time.time())),
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
            acceptance_criteria=[
                str(item) for item in data.get("acceptance_criteria", [])
            ],
            status=WorkStatus(status_value),
            requires_execution=bool(data.get("requires_execution", True)),
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
            unresolved_issues=[
                str(item) for item in data.get("unresolved_issues", [])
            ],
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
            "decisions_made": [
                decision.to_dict() for decision in self.decisions_made
            ],
            "blockers": list(self.blockers),
            "follow_up": list(self.follow_up),
            "subtasks": [subtask.to_dict() for subtask in self.subtasks],
            "raw_response_path": (
                str(self.raw_response_path) if self.raw_response_path else None
            ),
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
class WorkflowSession:
    """Persisted state for one stateful workflow."""

    id: str
    goal: str
    state: WorkflowState
    active_agents: list[str] = field(default_factory=list)
    current_round: int = 0
    pending_questions: list[OpenQuestion] = field(default_factory=list)
    blueprint: dict[str, Any] | None = None
    work_packages: list[WorkPackage] = field(default_factory=list)
    execution_results: list[ExecutionResult] = field(default_factory=list)
    subtask_results: list[SubtaskResult] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
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
            "current_round": self.current_round,
            "pending_questions": [q.to_dict() for q in self.pending_questions],
            "blueprint": self.blueprint,
            "work_packages": [package.to_dict() for package in self.work_packages],
            "execution_results": [
                result.to_dict() for result in self.execution_results
            ],
            "subtask_results": [
                result.to_dict() for result in self.subtask_results
            ],
            "decisions": [decision.to_dict() for decision in self.decisions],
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
            current_round=int(data.get("current_round", 0)),
            pending_questions=[
                OpenQuestion.from_dict(item)
                for item in data.get("pending_questions", [])
            ],
            blueprint=data.get("blueprint"),
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
            decisions=[
                DecisionRecord.from_dict(item) for item in data.get("decisions", [])
            ],
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )
