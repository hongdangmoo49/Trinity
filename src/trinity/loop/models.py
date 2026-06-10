"""Data models for Trinity loop engineering runs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LoopStatus(str, Enum):
    """Persisted lifecycle state for one loop run."""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class LoopTrigger:
    """How a loop run is started."""

    trigger_type: str = "manual"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.trigger_type, **dict(self.metadata)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LoopTrigger":
        if not isinstance(data, dict):
            return cls()
        trigger_type = str(data.get("type") or "manual").strip() or "manual"
        metadata = {key: value for key, value in data.items() if key != "type"}
        return cls(trigger_type=trigger_type, metadata=metadata)


@dataclass(frozen=True)
class LoopStopPolicy:
    """Policy for deciding the next loop state after gate evaluation."""

    on_gate_pass: str = "complete"
    on_gate_fail: str = "iterate"
    on_budget_exceeded: str = "pause"
    on_user_decision_required: str = "pause"
    on_max_iterations: str = "pause"

    def to_dict(self) -> dict[str, str]:
        return {
            "on_gate_pass": self.on_gate_pass,
            "on_gate_fail": self.on_gate_fail,
            "on_budget_exceeded": self.on_budget_exceeded,
            "on_user_decision_required": self.on_user_decision_required,
            "on_max_iterations": self.on_max_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LoopStopPolicy":
        if not isinstance(data, dict):
            return cls()
        return cls(
            on_gate_pass=str(data.get("on_gate_pass") or "complete"),
            on_gate_fail=str(data.get("on_gate_fail") or "iterate"),
            on_budget_exceeded=str(data.get("on_budget_exceeded") or "pause"),
            on_user_decision_required=str(
                data.get("on_user_decision_required") or "pause"
            ),
            on_max_iterations=str(data.get("on_max_iterations") or "pause"),
        )


@dataclass(frozen=True)
class LoopGateSpec:
    """One completion or safety gate declared in a loop spec."""

    id: str
    gate_type: str
    required: bool = True
    retryable: bool = True
    command: str = ""
    cwd: str = ""
    timeout_seconds: float = 300.0
    allowed_states: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "type": self.gate_type,
            "required": self.required,
            "retryable": self.retryable,
            "command": self.command,
            "cwd": self.cwd,
            "timeout_seconds": self.timeout_seconds,
            "allowed_states": list(self.allowed_states),
        }
        data.update(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopGateSpec":
        gate_id = str(data.get("id") or "").strip()
        gate_type = str(data.get("type") or data.get("gate_type") or "").strip()
        if not gate_id:
            raise ValueError("loop gate id is required")
        if not gate_type:
            raise ValueError(f"loop gate {gate_id!r} type is required")
        allowed_states = _string_tuple(
            data.get("allowed_states", data.get("states", ()))
        )
        known = {
            "id",
            "type",
            "gate_type",
            "required",
            "retryable",
            "command",
            "cwd",
            "timeout_seconds",
            "allowed_states",
            "states",
        }
        return cls(
            id=gate_id,
            gate_type=gate_type,
            required=bool(data.get("required", True)),
            retryable=bool(data.get("retryable", True)),
            command=str(data.get("command") or ""),
            cwd=str(data.get("cwd") or ""),
            timeout_seconds=float(data.get("timeout_seconds", 300.0) or 300.0),
            allowed_states=allowed_states,
            metadata={key: value for key, value in data.items() if key not in known},
        )


@dataclass(frozen=True)
class LoopGateResult:
    """Result of evaluating a loop gate for one iteration."""

    id: str
    gate_type: str
    status: str
    summary: str
    iteration: int = 0
    artifact_path: str = ""
    retryable: bool = True
    blocking: bool = True
    exit_code: int | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.gate_type,
            "status": self.status,
            "summary": self.summary,
            "iteration": self.iteration,
            "artifact_path": self.artifact_path,
            "retryable": self.retryable,
            "blocking": self.blocking,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopGateResult":
        return cls(
            id=str(data.get("id", "")),
            gate_type=str(data.get("type", data.get("gate_type", ""))),
            status=str(data.get("status", "")),
            summary=str(data.get("summary", "")),
            iteration=int(data.get("iteration", 0) or 0),
            artifact_path=str(data.get("artifact_path", "")),
            retryable=bool(data.get("retryable", True)),
            blocking=bool(data.get("blocking", True)),
            exit_code=(
                int(data["exit_code"]) if data.get("exit_code") is not None else None
            ),
            started_at=float(data.get("started_at", time.time())),
            finished_at=float(data.get("finished_at", time.time())),
            details=(
                dict(data.get("details", {}))
                if isinstance(data.get("details"), dict)
                else {}
            ),
        )


@dataclass(frozen=True)
class LoopSpec:
    """Source-of-truth loop definition loaded from TOML."""

    id: str
    title: str
    goal: str
    trigger: LoopTrigger = field(default_factory=LoopTrigger)
    agents: tuple[str, ...] = ()
    resource_packs: tuple[str, ...] = ()
    target_workspace: str = ""
    max_iterations: int = 1
    max_runtime_seconds: float = 0.0
    max_token_budget: int = 0
    gates: tuple[LoopGateSpec, ...] = ()
    stop_policy: LoopStopPolicy = field(default_factory=LoopStopPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "goal": self.goal,
            "trigger": self.trigger.to_dict(),
            "agents": list(self.agents),
            "resource_packs": list(self.resource_packs),
            "target_workspace": self.target_workspace,
            "max_iterations": self.max_iterations,
            "max_runtime_seconds": self.max_runtime_seconds,
            "max_token_budget": self.max_token_budget,
            "gates": [gate.to_dict() for gate in self.gates],
            "stop_policy": self.stop_policy.to_dict(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopSpec":
        spec_id = str(data.get("id") or "").strip()
        if not spec_id:
            raise ValueError("loop spec id is required")
        title = str(data.get("title") or spec_id).strip()
        goal = str(data.get("goal") or "").strip()
        if not goal:
            raise ValueError(f"loop spec {spec_id!r} goal is required")
        gates_data = data.get("gates", [])
        if not isinstance(gates_data, list):
            raise ValueError("loop spec gates must be a list")
        known = {
            "id",
            "title",
            "goal",
            "trigger",
            "agents",
            "resource_packs",
            "target_workspace",
            "max_iterations",
            "max_runtime_seconds",
            "max_token_budget",
            "gates",
            "stop_policy",
        }
        return cls(
            id=spec_id,
            title=title,
            goal=goal,
            trigger=LoopTrigger.from_dict(data.get("trigger")),
            agents=_string_tuple(data.get("agents", ())),
            resource_packs=_string_tuple(data.get("resource_packs", ())),
            target_workspace=str(data.get("target_workspace") or ""),
            max_iterations=max(1, int(data.get("max_iterations", 1) or 1)),
            max_runtime_seconds=max(
                0.0,
                float(data.get("max_runtime_seconds", 0.0) or 0.0),
            ),
            max_token_budget=max(0, int(data.get("max_token_budget", 0) or 0)),
            gates=tuple(LoopGateSpec.from_dict(item) for item in gates_data),
            stop_policy=LoopStopPolicy.from_dict(data.get("stop_policy")),
            metadata={key: value for key, value in data.items() if key not in known},
        )


@dataclass
class LoopRun:
    """Persisted state for one loop execution."""

    id: str
    spec_id: str
    spec_title: str = ""
    status: LoopStatus = LoopStatus.QUEUED
    iteration: int = 0
    workflow_ids: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    stop_reason: str = ""
    token_used: int = 0
    gate_results: list[LoopGateResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "spec_id": self.spec_id,
            "spec_title": self.spec_title,
            "status": self.status.value,
            "iteration": self.iteration,
            "workflow_ids": list(self.workflow_ids),
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "stop_reason": self.stop_reason,
            "token_used": self.token_used,
            "gate_results": [result.to_dict() for result in self.gate_results],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoopRun":
        return cls(
            id=str(data.get("id", "")),
            spec_id=str(data.get("spec_id", "")),
            spec_title=str(data.get("spec_title", "")),
            status=LoopStatus(str(data.get("status", LoopStatus.QUEUED.value))),
            iteration=int(data.get("iteration", 0) or 0),
            workflow_ids=[str(item) for item in data.get("workflow_ids", [])],
            started_at=float(data.get("started_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            completed_at=(
                float(data["completed_at"])
                if data.get("completed_at") is not None
                else None
            ),
            stop_reason=str(data.get("stop_reason", "")),
            token_used=int(data.get("token_used", 0) or 0),
            gate_results=[
                LoopGateResult.from_dict(item)
                for item in data.get("gate_results", [])
                if isinstance(item, dict)
            ],
        )


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())
