"""Workflow start, continuation, and execution-enable helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from trinity.workflow.decomposer import classify_blueprint_followup_action
from trinity.workflow.models import DecisionRecord, WorkflowSession, WorkflowState


class WorkflowLifecycleFlow:
    """Manage workflow lifecycle entrypoints for WorkflowEngine."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def start(
        self,
        goal: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> Any:
        """Start a new workflow for a user goal."""
        now = time.time()
        target_workspace = (
            self.engine.session.target_workspace
            if self._should_carry_target_workspace_into_new_workflow()
            else None
        )
        control_repo_target_confirmed = (
            self.engine.session.control_repo_target_confirmed
            if target_workspace is not None
            else False
        )
        effective_targets = self.engine._effective_target_agents(
            active_agents,
            target_agents,
        )
        model_overrides = self.engine._normalized_model_overrides(
            agent_model_overrides,
            effective_targets,
        )
        self.engine.session = WorkflowSession(
            id=f"wf-{uuid4().hex[:12]}",
            goal=goal,
            state=WorkflowState.PREFLIGHT,
            active_agents=list(active_agents),
            last_target_agents=list(effective_targets),
            agent_model_overrides=model_overrides,
            target_workspace=target_workspace,
            control_repo_target_confirmed=control_repo_target_confirmed,
            created_at=now,
            updated_at=now,
        )
        self.engine._persist(
            "workflow_started",
            {
                "goal": goal,
                "active_agents": active_agents,
                "target_agents": list(effective_targets),
                "agent_model_overrides": dict(model_overrides),
                "targeted": set(effective_targets) != set(active_agents),
            },
        )
        self.engine.set_state(WorkflowState.DELIBERATING, reason="user goal accepted")
        return self.engine.input_action_type(
            should_deliberate=True,
            prompt=goal,
            target_agents=effective_targets,
            agent_model_overrides=dict(model_overrides),
            agent_selection_mode=(
                "targeted" if set(effective_targets) != set(active_agents) else "all"
            ),
            started_new_workflow=True,
        )

    def _should_carry_target_workspace_into_new_workflow(self) -> bool:
        """Return whether an idle preselected target should survive workflow start."""
        return (
            self.engine.session.state == WorkflowState.IDLE
            and not self.engine.session.goal
            and self.engine.session.target_workspace is not None
        )

    def continue_from_blueprint(
        self,
        instruction: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> Any:
        """Continue an existing blueprint workflow with additional user text."""
        action_type = self.engine.input_action_type
        instruction = instruction.strip()
        if not instruction:
            return action_type(
                should_deliberate=False,
                message="Instruction cannot be empty.",
            )
        if self.engine.session.blueprint is None:
            return self.start(
                instruction,
                active_agents,
                target_agents=target_agents,
                agent_model_overrides=agent_model_overrides,
            )

        followup_action = classify_blueprint_followup_action(instruction)
        if followup_action == "execute":
            return self.enable_execution_for_current_blueprint(instruction)
        if followup_action == "cancel":
            return action_type(
                should_deliberate=False,
                message="Workflow action cancelled.",
            )
        if followup_action == "new":
            return self.start(
                instruction,
                active_agents,
                target_agents=target_agents,
                agent_model_overrides=agent_model_overrides,
            )

        if active_agents:
            self.engine.session.active_agents = list(active_agents)
        effective_targets = self.engine._effective_target_agents(
            self.engine.session.active_agents,
            target_agents,
        )
        model_overrides = self.engine._normalized_model_overrides(
            agent_model_overrides,
            effective_targets,
        )
        self.engine.session.last_target_agents = list(effective_targets)
        self.engine.session.agent_model_overrides = model_overrides
        source_state = self.engine.session.state
        self.engine.set_state(
            WorkflowState.DELIBERATING,
            reason="user continued from existing blueprint",
        )
        self.engine._persist(
            "workflow_continued",
            {
                "instruction": instruction,
                "source_state": source_state.value,
                "target_agents": list(effective_targets),
                "agent_model_overrides": dict(model_overrides),
                "targeted": set(effective_targets)
                != set(self.engine.session.active_agents),
            },
        )
        return action_type(
            should_deliberate=True,
            prompt=self.engine._build_blueprint_continuation_prompt(instruction),
            target_agents=effective_targets,
            agent_model_overrides=dict(model_overrides),
            agent_selection_mode=(
                "targeted"
                if set(effective_targets) != set(self.engine.session.active_agents)
                else "all"
            ),
        )

    def enable_execution_for_current_blueprint(
        self,
        instruction: str = "",
    ) -> Any:
        """Regenerate current blueprint packages as executable work packages."""
        action_type = self.engine.input_action_type
        if self.engine.session.blueprint is None:
            return action_type(
                should_deliberate=False,
                message="No approved blueprint is available to execute.",
            )
        if not self.engine.session.active_agents:
            return action_type(
                should_deliberate=False,
                message="No active agents are attached to this workflow.",
            )
        if self.engine.session.target_workspace is None:
            return action_type(
                should_deliberate=False,
                target_workspace_required=True,
                message="Target workspace is required before implementation.",
            )

        instruction = instruction.strip()
        blueprint_path = self._freeze_current_blueprint()
        if instruction:
            self.engine.session.decisions.append(
                DecisionRecord(
                    id=self.engine._question_flow()._next_decision_id(),
                    decision=instruction,
                    decided_by="user",
                    rationale="Execution instruction from session input.",
                )
            )

        self.engine.session.work_packages = self.engine.decomposer.decompose(
            self.engine.session.blueprint,
            self.engine._decomposition_agents(),
            requires_execution=True,
        )
        self.engine.session.execution_results = []
        self.engine.session.subtask_results = []
        self.engine.session.review_packages = []
        self.engine.session.review_results = []
        self.engine.session.updated_at = time.time()
        self.engine._persist(
            "execution_enabled",
            {
                "instruction": instruction,
                "blueprint_path": str(blueprint_path) if blueprint_path else "",
                "work_packages": [
                    package.id for package in self.engine.session.work_packages
                ],
            },
        )
        self.engine.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="current blueprint marked executable",
        )
        return action_type(
            should_deliberate=False,
            execution_requested=True,
            message="Current blueprint work packages are ready for execution.",
        )

    def _freeze_current_blueprint(self) -> Path | None:
        """Persist the approved blueprint as an immutable execution artifact."""
        if self.engine.session.blueprint is None:
            return None
        artifact_dir = self.engine.state_dir / "workflow" / "blueprints"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{self.engine.session.id}.json"
        if artifact_path.exists():
            return artifact_path
        payload = {
            "workflow_id": self.engine.session.id,
            "goal": self.engine.session.goal,
            "frozen_at": time.time(),
            "blueprint": self.engine.session.blueprint.to_dict(),
        }
        artifact_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return artifact_path
