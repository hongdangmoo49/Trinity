"""Stateful workflow engine for Trinity TUI sessions."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable
from uuid import uuid4

from trinity.models import (
    AgentSpec,
    DeliberationResult,
)
from trinity.providers.policy import (
    ExecutionScope,
)
from trinity.routing.quality import QualityLedger
from trinity.workflow.decomposer import (
    BlueprintDecomposer,
    classify_blueprint_followup_action,
    classify_execution_intent,
)
from trinity.workflow.execution_flow import WorkflowExecutionFlow
from trinity.workflow.post_review_flow import WorkflowPostReviewFlow
from trinity.workflow.review_flow import WorkflowReviewFlow
from trinity.workflow.models import (
    AgentRuntimeModel,
    AgentResourceProjection,
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    PostReviewActionItem,
    PostReviewActionStatus,
    ProviderSessionRef,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
    WorkflowSession,
    WorkflowState,
)
from trinity.workflow.persistence import WorkflowPersistence
from trinity.workflow.provider_error_gate_flow import ProviderErrorGateFlow
from trinity.workflow.recovery_flow import (
    ExecutionRecoveryFlow,
    ExecutionRetryPlan,
    RetrySkip,
)
from trinity.workflow.review import (
    FINAL_REVIEW_PACKAGE_ID,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
)

if TYPE_CHECKING:
    from trinity.context.shared import SharedContextEngine


@dataclass(frozen=True)
class WorkflowInputAction:
    """Result of routing a user input through workflow state."""

    should_deliberate: bool
    prompt: str = ""
    target_agents: tuple[str, ...] = ()
    agent_model_overrides: dict[str, str] = field(default_factory=dict)
    agent_selection_mode: str = "all"
    provider_retry_merge_context: dict[str, Any] = field(default_factory=dict)
    decision_record: DecisionRecord | None = None
    started_new_workflow: bool = False
    replaced_decision: bool = False
    execution_requested: bool = False
    target_workspace_required: bool = False
    message: str = ""


class WorkflowEngine:
    """Persisted state machine for user-guided multi-agent workflows."""

    input_action_type = WorkflowInputAction

    def __init__(
        self,
        state_dir: Path,
        state_file: Path | None = None,
        events_file: Path | None = None,
        decomposer: BlueprintDecomposer | None = None,
        agent_specs: dict[str, AgentSpec] | None = None,
    ):
        self.state_dir = state_dir
        workflow_dir = state_dir / "workflow"
        self.persistence = WorkflowPersistence(
            state_dir,
            state_file=state_file or workflow_dir / "session.json",
            events_file=events_file or workflow_dir / "events.jsonl",
        )
        self.state_file = self.persistence.session_path
        self.events_file = self.persistence.events_path
        self.decomposer = decomposer or BlueprintDecomposer()
        self.agent_specs = dict(agent_specs or {})
        self.session = self._load_or_create()

    @property
    def state(self) -> WorkflowState:
        return self.session.state

    @property
    def pending_questions(self) -> list[OpenQuestion]:
        return self.session.open_questions

    @property
    def decisions(self) -> list[DecisionRecord]:
        return list(self.session.decisions)

    @property
    def work_packages(self) -> list[WorkPackage]:
        return list(self.session.work_packages)

    @property
    def execution_results(self) -> list[ExecutionResult]:
        return list(self.session.execution_results)

    def quality_summaries(self) -> dict[str, dict[str, Any]]:
        """Return advisory quality summaries keyed by agent name."""
        return {
            name: summary.to_dict()
            for name, summary in QualityLedger(
                self.session.quality_signals
            ).summaries().items()
        }

    def _decomposition_agents(self) -> list[str] | dict[str, AgentSpec]:
        if not self.agent_specs:
            return list(self.session.active_agents)
        active = set(self.session.active_agents)
        return {
            name: spec
            for name, spec in self.agent_specs.items()
            if name in active
        }

    @property
    def target_workspace(self) -> Path | None:
        return self.session.target_workspace

    @property
    def subtask_results(self) -> list[SubtaskResult]:
        return list(self.session.subtask_results)

    @property
    def review_packages(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.session.review_packages]

    @property
    def review_results(self) -> list[ReviewResult]:
        return self._review_results()

    @property
    def post_review_items(self) -> list[PostReviewActionItem]:
        return self._post_review_items()

    @property
    def has_pending_execution(self) -> bool:
        """Return whether any generated package still needs execution."""
        return any(
            package.requires_execution
            and package.status
            in {
                WorkStatus.PENDING,
                WorkStatus.RUNNING,
                WorkStatus.WAITING_ON_DECISION,
                WorkStatus.BLOCKED,
                WorkStatus.FAILED,
            }
            for package in self.session.work_packages
        )

    @property
    def has_interrupted_execution(self) -> bool:
        """Return whether the persisted execution run needs recovery."""
        return self.execution_recovery_summary() is not None

    def _execution_recovery_flow(self) -> ExecutionRecoveryFlow:
        return ExecutionRecoveryFlow(
            session=self.session,
            persistence=self.persistence,
            persist=self._persist,
            set_state=self.set_state,
        )

    def _provider_error_gate_flow(self) -> ProviderErrorGateFlow:
        return ProviderErrorGateFlow(
            session=self.session,
            persist=self._persist,
            set_state=self.set_state,
            action_type=self.input_action_type,
            normalize_model_overrides=self._normalized_model_overrides,
            mark_deliberation_result=self.mark_deliberation_result,
        )

    def _execution_flow(self) -> WorkflowExecutionFlow:
        return WorkflowExecutionFlow(self)

    def _review_flow(self) -> WorkflowReviewFlow:
        return WorkflowReviewFlow(self)

    def _post_review_flow(self) -> WorkflowPostReviewFlow:
        return WorkflowPostReviewFlow(self)

    @staticmethod
    def _effective_target_agents(
        active_agents: list[str],
        target_agents: list[str] | tuple[str, ...] | None,
    ) -> tuple[str, ...]:
        active = [str(agent).strip() for agent in active_agents if str(agent).strip()]
        active_set = set(active)
        requested = [
            str(agent).strip()
            for agent in (target_agents or active)
            if str(agent).strip()
        ]
        selected = tuple(agent for agent in requested if agent in active_set)
        return selected or tuple(active)

    @staticmethod
    def _normalized_model_overrides(
        agent_model_overrides: dict[str, str] | None,
        allowed_agents: tuple[str, ...] | list[str] = (),
    ) -> dict[str, str]:
        if not agent_model_overrides:
            return {}
        allowed = {
            str(agent).strip()
            for agent in allowed_agents
            if str(agent).strip()
        }
        return {
            str(agent).strip(): str(model).strip()
            for agent, model in agent_model_overrides.items()
            if str(agent).strip()
            and str(model).strip()
            and (not allowed or str(agent).strip() in allowed)
        }

    def handle_user_input(
        self,
        text: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> WorkflowInputAction:
        """Route plain session text through the current workflow state."""
        if self.session.state == WorkflowState.POST_REVIEW_READY:
            return self.handle_post_review_input(text, active_agents)
        if self.session.state == WorkflowState.NEEDS_USER_DECISION:
            return self.answer_pending_question(text)
        if self._can_continue_existing_blueprint():
            return self.continue_from_blueprint(
                text,
                active_agents,
                target_agents=target_agents,
                agent_model_overrides=agent_model_overrides,
            )
        return self.start(
            text,
            active_agents,
            target_agents=target_agents,
            agent_model_overrides=agent_model_overrides,
        )

    def _can_continue_existing_blueprint(self) -> bool:
        """Return whether free text should stay attached to this workflow."""
        return self.session.blueprint is not None and self.session.state in {
            WorkflowState.BLUEPRINT_READY,
            WorkflowState.REVIEWING,
            WorkflowState.DONE,
            WorkflowState.FAILED,
        }

    def start(
        self,
        goal: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> WorkflowInputAction:
        """Start a new workflow for a user goal."""
        now = time.time()
        target_workspace = (
            self.session.target_workspace
            if self._should_carry_target_workspace_into_new_workflow()
            else None
        )
        control_repo_target_confirmed = (
            self.session.control_repo_target_confirmed
            if target_workspace is not None
            else False
        )
        effective_targets = self._effective_target_agents(active_agents, target_agents)
        model_overrides = self._normalized_model_overrides(
            agent_model_overrides,
            effective_targets,
        )
        self.session = WorkflowSession(
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
        self._persist(
            "workflow_started",
            {
                "goal": goal,
                "active_agents": active_agents,
                "target_agents": list(effective_targets),
                "agent_model_overrides": dict(model_overrides),
                "targeted": set(effective_targets) != set(active_agents),
            },
        )
        self.set_state(WorkflowState.DELIBERATING, reason="user goal accepted")
        return WorkflowInputAction(
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
            self.session.state == WorkflowState.IDLE
            and not self.session.goal
            and self.session.target_workspace is not None
        )

    def answer_pending_question(self, answer: str) -> WorkflowInputAction:
        """Record an answer to the oldest open question and continue deliberation."""
        return self.answer_question("next", answer)

    def answer_question(
        self,
        selector: str,
        answer: str,
        *,
        replace: bool = False,
    ) -> WorkflowInputAction:
        """Record or replace a user answer for a selected workflow question."""
        answer = answer.strip()
        if not answer:
            return WorkflowInputAction(
                should_deliberate=False,
                message="Answer cannot be empty.",
            )

        question = self.resolve_question(selector, include_answered=replace)
        if question is None:
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"No matching workflow question: {selector}",
            )
        if question.status != "open" and not replace:
            return WorkflowInputAction(
                should_deliberate=False,
                message=(
                    f"Question {question.id} is already answered. "
                    "Use /answer --replace to update it."
                ),
            )

        existing = self._decision_for_question(question.id) if replace else None
        question.status = "answered"
        if existing is not None:
            decision = existing
            decision.decision = answer
            decision.decided_by = "user"
            decision.rationale = f"Updated answer to: {question.question}"
            decision.timestamp = time.time()
            event_type = "decision_replaced"
            replaced = True
        else:
            decision = DecisionRecord(
                id=f"dec-{len(self.session.decisions) + 1:03d}",
                question_id=question.id,
                decision=answer,
                decided_by="user",
                rationale=f"Answer to: {question.question}",
            )
            self.session.decisions.append(decision)
            event_type = "decision_recorded"
            replaced = False

        self.session.updated_at = time.time()
        self._persist(
            event_type,
            {
                "decision_id": decision.id,
                "question_id": question.id,
                "decision": answer,
                "replaced": replaced,
            },
        )

        if self.pending_questions:
            self.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="more blocking questions remain",
            )
            return WorkflowInputAction(
                should_deliberate=False,
                decision_record=decision,
                replaced_decision=replaced,
            )

        if self._provider_error_gate_flow().is_gate_question(question):
            return self._provider_error_gate_flow().handle_answer(
                answer,
                decision,
                replaced_decision=replaced,
            )

        self.set_state(WorkflowState.DELIBERATING, reason="user decision answered")
        target_agents = self._effective_target_agents(
            self.session.active_agents,
            self.session.last_target_agents,
        )
        model_overrides = self._normalized_model_overrides(
            self.session.agent_model_overrides,
            target_agents,
        )
        active_agent_set = {
            str(agent).strip()
            for agent in self.session.active_agents
            if str(agent).strip()
        }
        return WorkflowInputAction(
            should_deliberate=True,
            prompt=self._build_decision_continuation_prompt(decision),
            target_agents=target_agents,
            agent_model_overrides=dict(model_overrides),
            agent_selection_mode=(
                "targeted"
                if set(target_agents) != active_agent_set
                else "all"
            ),
            decision_record=decision,
            replaced_decision=replaced,
        )

    def answer_question_option(
        self,
        option_selector: str,
        *,
        question_selector: str = "next",
        replace: bool = False,
    ) -> WorkflowInputAction:
        """Record a numbered option for a selected workflow question."""
        question = self.resolve_question(
            question_selector,
            include_answered=replace,
        )
        if question is None:
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"No matching workflow question: {question_selector}",
            )
        if not option_selector.isdigit():
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"Option must be a number: {option_selector}",
            )
        index = int(option_selector) - 1
        if index < 0 or index >= len(question.options):
            return WorkflowInputAction(
                should_deliberate=False,
                message=f"Question {question.id} has no option {option_selector}.",
            )
        return self.answer_question(
            question.id,
            question.options[index],
            replace=replace,
        )

    def continue_from_blueprint(
        self,
        instruction: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> WorkflowInputAction:
        """Continue an existing blueprint workflow with additional user text."""
        instruction = instruction.strip()
        if not instruction:
            return WorkflowInputAction(
                should_deliberate=False,
                message="Instruction cannot be empty.",
            )
        if self.session.blueprint is None:
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
            return WorkflowInputAction(
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
            self.session.active_agents = list(active_agents)
        effective_targets = self._effective_target_agents(
            self.session.active_agents,
            target_agents,
        )
        model_overrides = self._normalized_model_overrides(
            agent_model_overrides,
            effective_targets,
        )
        self.session.last_target_agents = list(effective_targets)
        self.session.agent_model_overrides = model_overrides
        source_state = self.session.state
        self.set_state(
            WorkflowState.DELIBERATING,
            reason="user continued from existing blueprint",
        )
        self._persist(
            "workflow_continued",
            {
                "instruction": instruction,
                "source_state": source_state.value,
                "target_agents": list(effective_targets),
                "agent_model_overrides": dict(model_overrides),
                "targeted": set(effective_targets) != set(self.session.active_agents),
            },
        )
        return WorkflowInputAction(
            should_deliberate=True,
            prompt=self._build_blueprint_continuation_prompt(instruction),
            target_agents=effective_targets,
            agent_model_overrides=dict(model_overrides),
            agent_selection_mode=(
                "targeted"
                if set(effective_targets) != set(self.session.active_agents)
                else "all"
            ),
        )

    def enable_execution_for_current_blueprint(
        self,
        instruction: str = "",
    ) -> WorkflowInputAction:
        """Regenerate current blueprint packages as executable work packages."""
        if self.session.blueprint is None:
            return WorkflowInputAction(
                should_deliberate=False,
                message="No approved blueprint is available to execute.",
            )
        if not self.session.active_agents:
            return WorkflowInputAction(
                should_deliberate=False,
                message="No active agents are attached to this workflow.",
            )
        if self.session.target_workspace is None:
            return WorkflowInputAction(
                should_deliberate=False,
                target_workspace_required=True,
                message="Target workspace is required before implementation.",
            )

        instruction = instruction.strip()
        blueprint_path = self._freeze_current_blueprint()
        if instruction:
            self.session.decisions.append(
                DecisionRecord(
                    id=self._next_decision_id(),
                    decision=instruction,
                    decided_by="user",
                    rationale="Execution instruction from session input.",
                )
            )

        self.session.work_packages = self.decomposer.decompose(
            self.session.blueprint,
            self._decomposition_agents(),
            requires_execution=True,
        )
        self.session.execution_results = []
        self.session.subtask_results = []
        self.session.review_packages = []
        self.session.review_results = []
        self.session.updated_at = time.time()
        self._persist(
            "execution_enabled",
            {
                "instruction": instruction,
                "blueprint_path": str(blueprint_path) if blueprint_path else "",
                "work_packages": [package.id for package in self.session.work_packages],
            },
        )
        self.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="current blueprint marked executable",
        )
        return WorkflowInputAction(
            should_deliberate=False,
            execution_requested=True,
            message="Current blueprint work packages are ready for execution.",
        )

    def _freeze_current_blueprint(self) -> Path | None:
        """Persist the approved blueprint as an immutable execution artifact."""
        if self.session.blueprint is None:
            return None
        artifact_dir = self.state_dir / "workflow" / "blueprints"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{self.session.id}.json"
        if artifact_path.exists():
            return artifact_path
        payload = {
            "workflow_id": self.session.id,
            "goal": self.session.goal,
            "frozen_at": time.time(),
            "blueprint": self.session.blueprint.to_dict(),
        }
        artifact_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return artifact_path

    def resolve_question(
        self,
        selector: str,
        *,
        include_answered: bool = False,
    ) -> OpenQuestion | None:
        """Resolve a question id, 1-based index, or ``next`` selector."""
        selector = selector.strip()
        if not selector:
            return None

        normalized = selector.lower()
        open_questions = self.pending_questions
        questions = self.session.pending_questions if include_answered else open_questions

        if normalized in {"next", "first"}:
            return open_questions[0] if open_questions else None

        if normalized.isdigit():
            index = int(normalized) - 1
            if 0 <= index < len(questions):
                return questions[index]
            return None

        if include_answered and normalized.startswith("dec-"):
            decision = next(
                (item for item in self.session.decisions if item.id.lower() == normalized),
                None,
            )
            if decision and decision.question_id:
                normalized = decision.question_id.lower()

        return next(
            (question for question in questions if question.id.lower() == normalized),
            None,
        )

    def _decision_for_question(self, question_id: str) -> DecisionRecord | None:
        """Return the existing decision attached to a question."""
        return next(
            (
                decision
                for decision in self.session.decisions
                if decision.question_id == question_id
            ),
            None,
        )

    def _next_decision_id(self) -> str:
        return f"dec-{len(self.session.decisions) + 1:03d}"

    def set_target_workspace(
        self,
        path: Path,
        *,
        control_repo_confirmed: bool = False,
    ) -> None:
        """Persist the workspace where provider implementation may write files."""
        resolved = path.expanduser().resolve()
        self.session.target_workspace = resolved
        self.session.control_repo_target_confirmed = control_repo_confirmed
        self.session.updated_at = time.time()
        self._persist(
            "target_workspace_selected",
            {
                "target_workspace": str(resolved),
                "control_repo_target_confirmed": control_repo_confirmed,
            },
        )

    def clear_target_workspace(self) -> None:
        """Clear the selected implementation workspace."""
        self.session.target_workspace = None
        self.session.control_repo_target_confirmed = False
        self.session.updated_at = time.time()
        self._persist("target_workspace_cleared", {})

    def add_open_question(self, question: OpenQuestion) -> None:
        """Add a pending question and move workflow to waiting state."""
        self.session.pending_questions.append(question)
        self.set_state(
            WorkflowState.NEEDS_USER_DECISION,
            reason=f"question added: {question.id}",
        )

    def mark_deliberation_result(self, result: DeliberationResult) -> None:
        """Update workflow state after a deliberation completes."""
        self.session.current_round = result.rounds_completed
        self._record_provider_observations(result.metadata)
        if self._provider_error_gate_flow().should_open(result):
            self._provider_error_gate_flow().open(result)
            return

        structured = result.metadata.get("structured_consensus")
        if isinstance(structured, dict):
            if self._apply_structured_questions(structured):
                self.set_state(
                    WorkflowState.NEEDS_USER_DECISION,
                    reason="structured deliberation requires user decision",
                )
                return

            blueprint = structured.get("final_blueprint")
            if structured.get("reached") and isinstance(blueprint, dict):
                self.session.blueprint = Blueprint.from_dict(blueprint)
                self.session.work_packages = self.decomposer.decompose(
                    self.session.blueprint,
                    self._decomposition_agents(),
                    requires_execution=self._requires_execution(result),
                )
                self.session.execution_results = []
                self.session.subtask_results = []
                self.session.review_packages = []
                self.session.review_results = []
                self._record_central_conversation(
                    title="Central Agent Response",
                    body=self._central_blueprint_body(self.session.blueprint),
                    related_ids=[package.id for package in self.session.work_packages],
                )
                self.set_state(
                    WorkflowState.BLUEPRINT_READY,
                    reason="structured blueprint reached consensus",
                )
                return

        if result.has_consensus:
            summary = result.consensus.summary if result.consensus else ""
            self.session.blueprint = Blueprint(
                title="Consensus Blueprint",
                summary=summary,
                acceptance_criteria=[summary] if summary else [],
            )
            self.session.work_packages = []
            self.session.execution_results = []
            self.session.subtask_results = []
            self.session.review_packages = []
            self.session.review_results = []
            self._record_central_conversation(
                title="Central Agent Response",
                body=self._central_blueprint_body(self.session.blueprint),
                related_ids=[package.id for package in self.session.work_packages],
            )
            self.set_state(
                WorkflowState.BLUEPRINT_READY,
                reason="deliberation reached consensus",
            )
        else:
            self.set_state(WorkflowState.FAILED, reason="deliberation ended without consensus")

    def _record_central_conversation(
        self,
        *,
        title: str,
        body: str,
        role: str = "central",
        channel: str = "nexus",
        command: str = "",
        related_ids: Iterable[str] = (),
        truncated: bool = False,
    ) -> None:
        """Persist a central-agent transcript item for report reconstruction."""
        self._persist(
            "central_conversation_recorded",
            {
                "message_id": f"cc-{uuid4().hex[:12]}",
                "role": role,
                "channel": channel,
                "title": title,
                "body": body,
                "command": command,
                "related_ids": [str(item) for item in related_ids if str(item).strip()],
                "truncated": truncated,
            },
        )

    @staticmethod
    def _central_blueprint_body(blueprint: Blueprint) -> str:
        lines = [f"# {blueprint.title or 'Blueprint'}"]
        if blueprint.summary:
            lines.extend(["", blueprint.summary])
        if blueprint.architecture:
            lines.extend(["", "## Architecture"])
            lines.extend(
                f"- {component.name}: {component.responsibility}"
                for component in blueprint.architecture
            )
        if blueprint.data_flow:
            lines.extend(["", "## Data Flow"])
            lines.extend(f"- {item}" for item in blueprint.data_flow)
        if blueprint.acceptance_criteria:
            lines.extend(["", "## Acceptance Criteria"])
            lines.extend(f"- {item}" for item in blueprint.acceptance_criteria)
        return "\n".join(lines)

    def _record_provider_observations(self, metadata: dict[str, Any]) -> None:
        """Persist provider session/model observations from result metadata."""
        provider_sessions = metadata.get("provider_sessions")
        runtime_models = metadata.get("runtime_models")
        resource_projections = metadata.get("resource_projections")
        changed = False

        if isinstance(provider_sessions, dict):
            for key, value in provider_sessions.items():
                if not isinstance(value, dict):
                    continue
                session = ProviderSessionRef.from_dict(value)
                if not session.provider_session_id:
                    continue
                session_key = session.session_key or str(key)
                if not session_key:
                    continue
                self.session.provider_sessions[session_key] = session
                changed = True

        if isinstance(runtime_models, dict):
            for key, value in runtime_models.items():
                if not isinstance(value, dict):
                    continue
                model = AgentRuntimeModel.from_dict(value)
                model_key = model.agent_name or str(key)
                if not model_key:
                    continue
                self.session.runtime_models[model_key] = model
                changed = True

        if isinstance(resource_projections, dict):
            for key, value in resource_projections.items():
                if not isinstance(value, dict):
                    continue
                projection = AgentResourceProjection.from_dict(value)
                projection_key = str(key).strip() or projection.key
                if not projection_key:
                    continue
                self.session.resource_projections[projection_key] = projection
                changed = True

        if not changed:
            return

        self.session.updated_at = time.time()
        self._persist(
            "provider_metadata_observed",
            {
                "provider_sessions": sorted(self.session.provider_sessions.keys()),
                "runtime_models": sorted(self.session.runtime_models.keys()),
                "resource_projections": sorted(
                    self.session.resource_projections.keys()
                ),
            },
        )

    def _apply_structured_questions(self, structured: dict) -> bool:
        raw_questions = structured.get("open_questions", [])
        if not isinstance(raw_questions, list) or not raw_questions:
            return False

        existing = {
            self._normalize_question(question.question)
            for question in self.session.pending_questions
        }
        added = False
        saw_valid_question = False
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            question = OpenQuestion.from_dict(item)
            normalized = self._normalize_question(question.question)
            if not normalized:
                continue
            saw_valid_question = True
            if normalized in existing:
                continue
            question.id = self._unique_question_id(question.id)
            self.session.pending_questions.append(question)
            existing.add(normalized)
            added = True
        return added or saw_valid_question

    @staticmethod
    def _normalize_question(question: str) -> str:
        return " ".join(question.strip().lower().split())

    def _unique_question_id(self, question_id: str) -> str:
        """Return a question id that does not collide with session history."""
        base = question_id.strip() or "oq"
        existing = {question.id for question in self.session.pending_questions}
        existing.update(
            decision.question_id for decision in self.session.decisions if decision.question_id
        )
        if base not in existing:
            return base

        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def _requires_execution(self, result: DeliberationResult) -> bool:
        if any(task.requires_execution for task in result.tasks):
            return True

        text = "\n".join(
            part
            for part in (
                self.session.goal,
                result.user_prompt,
                result.consensus.summary if result.consensus else "",
            )
            if part
        )
        return classify_execution_intent(text)

    def pending_execution_package_ids(self) -> list[str]:
        """Return the package ids that the next execution run should dispatch."""
        return self._execution_flow().pending_execution_package_ids()

    def begin_execution(self, package_ids: Iterable[str] | None = None) -> None:
        """Move the workflow into execution before dispatching work packages."""
        self._execution_flow().begin_execution(package_ids)

    def record_work_package_started(
        self,
        package_id: str,
        agent_name: str = "",
        occurred_at: float | None = None,
    ) -> None:
        """Persist that one work package has started execution."""
        self._execution_flow().record_work_package_started(
            package_id,
            agent_name=agent_name,
            occurred_at=occurred_at,
        )

    def record_work_package_completed(
        self,
        package_id: str,
        agent_name: str = "",
        status: str = "",
        summary: str = "",
        occurred_at: float | None = None,
        attempt_chain: list[dict[str, object]] | None = None,
        raw_response_path: str = "",
    ) -> None:
        """Persist that one work package has finished execution."""
        self._execution_flow().record_work_package_completed(
            package_id,
            agent_name=agent_name,
            status=status,
            summary=summary,
            occurred_at=occurred_at,
            attempt_chain=attempt_chain,
            raw_response_path=raw_response_path,
        )

    def plan_parallel_groups(self) -> list[list[WorkPackage]]:
        """Preview dependency/file-safe work package groups for the current session."""
        return self._execution_flow().plan_parallel_groups()

    @staticmethod
    def _preview_execution_scope(package: WorkPackage) -> ExecutionScope:
        """Build scheduling metadata for TUI parallel-group previews."""
        return WorkflowExecutionFlow.preview_execution_scope(package)

    def record_execution_batch_planned(
        self,
        batches: list[list[str]],
        notices: list[dict[str, object]] | None = None,
        occurred_at: float | None = None,
    ) -> None:
        """Persist execution scheduling batches and policy notices."""
        self._execution_flow().record_execution_batch_planned(
            batches,
            notices=notices,
            occurred_at=occurred_at,
        )

    def record_execution_results(
        self,
        results: list[ExecutionResult],
        *,
        finalize: bool = True,
        emit_events: bool = True,
    ) -> None:
        """Persist execution results and derive the next workflow state."""
        self._execution_flow().record_execution_results(
            results,
            finalize=finalize,
            emit_events=emit_events,
        )

    def _record_execution_result(
        self,
        result: ExecutionResult,
        *,
        emit_event: bool,
    ) -> None:
        """Upsert one execution result without finalizing the workflow."""
        self._execution_flow().record_execution_result(result, emit_event=emit_event)

    def _finalize_execution_state(self) -> None:
        """Derive the workflow state after current execution progress."""
        self._execution_flow().finalize_execution_state()

    def ensure_review_packages(self) -> list[ReviewPackage]:
        """Ensure completed execution has review packages planned."""
        return self._review_flow().ensure_review_packages()

    def review_packages_for_request(
        self,
        selector: str = "wp",
        package_ids: Iterable[str] = (),
    ) -> list[ReviewPackage]:
        """Return review packages selected by a /review request."""
        return self._review_flow().review_packages_for_request(
            selector,
            package_ids=package_ids,
        )

    def record_review_results(
        self,
        results: Iterable[ReviewResult],
        *,
        finalize: bool = True,
    ) -> None:
        """Persist review results and update workflow/package state."""
        self._review_flow().record_review_results(results, finalize=finalize)

    def prepare_review_repairs(
        self,
        results: Iterable[ReviewResult],
        *,
        max_attempts: int = 3,
    ) -> tuple[str, ...]:
        """Queue packages with requested review changes for another execution pass."""
        return self._review_flow().prepare_review_repairs(
            results,
            max_attempts=max_attempts,
        )

    def reconcile_review_repair_metadata(
        self,
        *,
        max_attempts: int = 3,
    ) -> tuple[str, ...]:
        """Recover repair-loop metadata for sessions saved before repair guards."""
        return self._review_flow().reconcile_review_repair_metadata(
            max_attempts=max_attempts,
        )

    def review_repair_blocked_package_ids(self) -> tuple[str, ...]:
        """Return packages paused by review-repair loop guards."""
        return self._review_flow().review_repair_blocked_package_ids()

    def accept_review_repair_blocks(self) -> tuple[str, ...]:
        """Mark review-repair blocked packages as accepted by the user."""
        return self._review_flow().accept_review_repair_blocks()

    def stop_review_repair_blocks(self) -> tuple[str, ...]:
        """Stop the workflow after review-repair loop guards pause packages."""
        return self._review_flow().stop_review_repair_blocks()

    def _block_review_repair(
        self,
        package: WorkPackage,
        result: ReviewResult,
        *,
        reason: str,
        signature: str,
        max_attempts: int,
        required_changes: Iterable[str] | None = None,
        review_package_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Persist that a review repair should not be auto-restarted again."""
        return self._review_flow().block_review_repair(
            package,
            result,
            reason=reason,
            signature=signature,
            max_attempts=max_attempts,
            required_changes=required_changes,
            review_package_ids=review_package_ids,
        )

    def _record_review_result(self, result: ReviewResult) -> None:
        self._review_flow().record_review_result(result)

    def _record_execution_quality(self, result: ExecutionResult) -> None:
        self._execution_flow().record_execution_quality(result)

    def _record_review_quality(self, result: ReviewResult) -> None:
        self._review_flow().record_review_quality(result)

    def _apply_review_result_to_package(self, result: ReviewResult) -> None:
        self._review_flow().apply_review_result_to_package(result)

    def _finalize_review_state(self, latest_results: list[ReviewResult]) -> None:
        self._review_flow().finalize_review_state(latest_results)

    def finalize_post_review(self, final_result: ReviewResult | None = None) -> None:
        """Move a completed final review into the user-selectable follow-up state."""
        self._post_review_flow().finalize_post_review(final_result)

    def _auto_replan_final_review_changes(
        self,
        final_result: ReviewResult | None,
        created_items: Iterable[PostReviewActionItem],
    ) -> tuple[str, ...]:
        """Queue supplemental WPs for required final-review changes."""
        return self._post_review_flow()._auto_replan_final_review_changes(
            final_result,
            created_items,
        )

    def extract_post_review_items(
        self,
        final_result: ReviewResult | None = None,
    ) -> list[PostReviewActionItem]:
        """Normalize review findings into post-review action items."""
        return self._post_review_flow().extract_post_review_items(final_result)

    def handle_post_review_input(
        self,
        text: str,
        active_agents: list[str],
    ) -> WorkflowInputAction:
        """Handle user follow-up after final review without starting a new workflow."""
        return self._post_review_flow().handle_post_review_input(text, active_agents)

    def accept_post_review_items(
        self,
        item_ids: Iterable[str],
        *,
        note: str | None = None,
        active_agents: list[str] | None = None,
    ) -> tuple[str, ...]:
        """Mark action items accepted and append supplemental work packages."""
        return self._post_review_flow().accept_post_review_items(
            item_ids,
            note=note,
            active_agents=active_agents,
        )

    def queue_supplemental_work_packages(
        self,
        items: Iterable[PostReviewActionItem],
        *,
        active_agents: list[str] | None = None,
    ) -> tuple[str, ...]:
        """Append accepted action items as supplemental work packages."""
        return self._post_review_flow().queue_supplemental_work_packages(
            items,
            active_agents=active_agents,
        )

    def post_review_summary(self) -> str:
        """Return a concise user-facing summary of post-review actions."""
        return self._post_review_flow().post_review_summary()

    def _latest_review_is_approved(self, package_id: str) -> bool:
        planned = [
            review
            for review in self._planned_review_packages()
            if review.package_id == package_id
            and review.scope != "final"
            and review.package_id != FINAL_REVIEW_PACKAGE_ID
            and review.required
        ]
        if planned:
            return all(self._review_package_is_approved(review) for review in planned)

        for result in reversed(self._review_results()):
            if result.package_id == package_id and result.scope != "final":
                return result.status == ReviewStatus.APPROVED
        return False

    def _review_package_is_approved(self, review: ReviewPackage) -> bool:
        for result in reversed(self._review_results()):
            if result.review_package_id == review.id:
                return result.status == ReviewStatus.APPROVED
            if (
                result.package_id == review.package_id
                and result.reviewer_agent == review.reviewer_agent
                and result.target_agent == review.target_agent
                and result.scope == review.scope
            ):
                return result.status == ReviewStatus.APPROVED
        return False

    def _planned_review_packages(self) -> list[ReviewPackage]:
        reviews: list[ReviewPackage] = []
        for item in self.session.review_packages:
            if not isinstance(item, dict):
                continue
            try:
                reviews.append(ReviewPackage.from_dict(item))
            except (TypeError, ValueError):
                continue
        return reviews

    def detect_interrupted_execution(
        self,
        *,
        worker_running: bool = False,
        reason: str = "process_lost",
    ) -> dict[str, Any] | None:
        """Mark and return stale execution recovery metadata."""
        return self._execution_recovery_flow().detect_interrupted_execution(
            worker_running=worker_running,
            reason=reason,
        )

    def execution_recovery_summary(self) -> dict[str, Any] | None:
        """Return a serializable execution recovery summary when applicable."""
        return self._execution_recovery_flow().execution_recovery_summary()

    def build_execution_retry_plan(
        self,
        selector: str = "all",
        package_ids: Iterable[str] = (),
    ) -> ExecutionRetryPlan:
        """Build a non-destructive retry plan for failed/blocked/stale packages."""
        return self._execution_recovery_flow().build_execution_retry_plan(
            selector=selector,
            package_ids=package_ids,
        )

    def prepare_execution_retry(
        self,
        selector: str = "all",
        package_ids: Iterable[str] = (),
    ) -> ExecutionRetryPlan:
        """Mark selected retry packages pending without deleting prior results."""
        return self._execution_recovery_flow().prepare_execution_retry(
            selector=selector,
            package_ids=package_ids,
        )

    def retry_interrupted_execution(self) -> dict[str, Any] | None:
        """Prepare interrupted/failed packages for explicit user retry."""
        return self._execution_recovery_flow().retry_interrupted_execution()

    @staticmethod
    def _normalize_execution_retry_selector(
        selector: str,
        package_ids: Iterable[str],
    ) -> str:
        return ExecutionRecoveryFlow.normalize_execution_retry_selector(
            selector,
            package_ids,
        )

    @staticmethod
    def _execution_retry_disabled_reason(
        package: WorkPackage,
        interrupted_ids: set[str],
    ) -> str:
        return ExecutionRecoveryFlow.execution_retry_disabled_reason(
            package,
            interrupted_ids,
        )

    @staticmethod
    def _matches_execution_retry_selector(
        package: WorkPackage,
        selector: str,
        interrupted_ids: set[str],
    ) -> bool:
        return ExecutionRecoveryFlow.matches_execution_retry_selector(
            package,
            selector,
            interrupted_ids,
        )

    def mark_interrupted_execution(self) -> dict[str, Any] | None:
        """Turn stale running packages into blocked work that needs user review."""
        return self._execution_recovery_flow().mark_interrupted_execution()

    def abort_interrupted_execution(self) -> dict[str, Any] | None:
        """Abort a stale execution and require an explicit user decision."""
        return self._execution_recovery_flow().abort_interrupted_execution()

    def _touch_execution_run(self, occurred_at: float | None = None) -> None:
        self._execution_recovery_flow().touch_execution_run(occurred_at)

    def _finish_execution_run(self, outcome: str) -> None:
        self._execution_recovery_flow().finish_execution_run(outcome)

    def _persist_recovery_action(self, action: str, packages: list[str]) -> None:
        self._execution_recovery_flow().persist_recovery_action(action, packages)

    def _packages_with_status(self, status: WorkStatus) -> list[WorkPackage]:
        return self._execution_recovery_flow().packages_with_status(status)

    def _last_workflow_event(self) -> dict[str, Any] | None:
        return self._execution_recovery_flow().last_workflow_event()

    def _work_package_by_id(self, package_id: str) -> WorkPackage | None:
        return next(
            (package for package in self.session.work_packages if package.id == package_id),
            None,
        )

    def _review_repair_metadata_from_events(self) -> dict[str, dict[str, Any]]:
        metadata_by_package: dict[str, dict[str, Any]] = {}
        for event in self.persistence.load_events_for_workflow(
            self.session.id,
            event_names={"work_package_repair_requested"},
        ):
            data = event.get("data", {})
            if not isinstance(data, dict):
                continue
            package_id = str(data.get("package_id", "")).strip()
            if not package_id:
                continue
            metadata = metadata_by_package.setdefault(
                package_id,
                {
                    "attempt_count": 0,
                    "repair_signature": "",
                    "review_package_id": "",
                },
            )
            next_count = int(metadata["attempt_count"]) + 1
            try:
                event_count = int(data.get("repair_attempt_count", 0) or 0)
            except (TypeError, ValueError):
                event_count = 0
            metadata["attempt_count"] = max(next_count, event_count)
            repair_signature = str(data.get("repair_signature", "") or "")
            if repair_signature:
                metadata["repair_signature"] = repair_signature
            review_package_id = str(data.get("review_package_id", "") or "")
            if not review_package_id:
                review_package_ids = data.get("review_package_ids", [])
                if isinstance(review_package_ids, list) and review_package_ids:
                    review_package_id = str(review_package_ids[-1])
            if review_package_id:
                metadata["review_package_id"] = review_package_id
        return metadata_by_package

    @classmethod
    def _review_repair_signature(cls, result: ReviewResult) -> str:
        return cls._review_repair_signature_from_parts(
            result.package_id,
            result.target_agent,
            result.required_changes,
        )

    @classmethod
    def _review_repair_signature_from_parts(
        cls,
        package_id: str,
        target_agent: str,
        required_changes: Iterable[str],
    ) -> str:
        changes = [
            normalized
            for normalized in (
                cls._normalize_repair_change(change) for change in required_changes
            )
            if normalized
        ]
        payload = {
            "package_id": package_id,
            "target_agent": target_agent,
            "required_changes": sorted(set(changes)),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _merged_review_repair_changes(
        cls,
        results: Iterable[ReviewResult],
    ) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for result in results:
            for change in result.required_changes:
                normalized = cls._normalize_repair_change(change)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged

    @staticmethod
    def _review_repair_target_agent(
        package: WorkPackage,
        results: Iterable[ReviewResult],
    ) -> str:
        targets = {
            str(result.target_agent).strip()
            for result in results
            if str(result.target_agent).strip()
        }
        if len(targets) == 1:
            return next(iter(targets))
        if targets:
            return ",".join(sorted(targets))
        return package.owner_agent

    @staticmethod
    def _normalize_repair_change(change: str) -> str:
        return re.sub(r"\s+", " ", str(change).strip())

    def _review_results(self) -> list[ReviewResult]:
        reviews: list[ReviewResult] = []
        for item in self.session.review_results:
            if not isinstance(item, dict):
                continue
            try:
                reviews.append(ReviewResult.from_dict(item))
            except (TypeError, ValueError):
                continue
        return reviews

    def _post_review_items(self) -> list[PostReviewActionItem]:
        items: list[PostReviewActionItem] = []
        for item in self.session.post_review_items:
            if not isinstance(item, dict):
                continue
            try:
                items.append(PostReviewActionItem.from_dict(item))
            except (TypeError, ValueError):
                continue
        return items

    def _post_review_candidates_from_review(
        self,
        review: ReviewResult,
    ) -> list[PostReviewActionItem]:
        candidates: list[PostReviewActionItem] = []
        is_final = review.scope == "final" or review.package_id == FINAL_REVIEW_PACKAGE_ID
        source = "final_review" if is_final else "wp_review"
        related_wp_ids = [] if is_final else [review.package_id]
        suggested_owner = "" if is_final else self._owner_for_related_package(review.package_id)

        for change in review.required_changes:
            candidates.append(
                self._new_post_review_item(
                    source=source,
                    kind="bugfix",
                    severity=review.severity or "high",
                    summary=change,
                    review=review,
                    related_wp_ids=related_wp_ids,
                    suggested_owner=suggested_owner,
                    rationale=review.summary,
                )
            )
        for risk in review.execution_risks:
            candidates.append(
                self._new_post_review_item(
                    source=source,
                    kind="validation",
                    severity=review.severity or "high",
                    summary=risk,
                    review=review,
                    related_wp_ids=related_wp_ids,
                    suggested_owner=suggested_owner,
                    rationale=review.summary,
                )
            )
        if is_final:
            for follow_up in review.follow_up:
                candidates.append(
                    self._new_post_review_item(
                        source=source,
                        kind="enhancement",
                        severity=self._downgrade_optional_severity(review.severity),
                        summary=follow_up,
                        review=review,
                        related_wp_ids=[],
                        suggested_owner="",
                        rationale=review.summary,
                    )
                )
        return [item for item in candidates if item.summary.strip()]

    def _new_post_review_item(
        self,
        *,
        source: str,
        kind: str,
        severity: str,
        summary: str,
        review: ReviewResult,
        related_wp_ids: list[str],
        suggested_owner: str,
        rationale: str = "",
    ) -> PostReviewActionItem:
        return PostReviewActionItem(
            id="",
            source=source,
            kind=kind,
            severity=self._normalize_severity(severity),
            title=self._action_title(summary),
            summary=summary.strip(),
            rationale=rationale.strip(),
            related_wp_ids=list(related_wp_ids),
            related_review_ids=[review.review_package_id],
            suggested_owner=suggested_owner,
            requires_execution=True,
        )

    def _create_user_request_action_item(self, instruction: str) -> PostReviewActionItem:
        item = PostReviewActionItem(
            id=self._next_post_review_item_id(self._post_review_items()),
            source="user_request",
            kind="enhancement",
            severity="medium",
            title=self._action_title(instruction),
            summary=instruction.strip(),
            rationale="User requested additional post-review improvement.",
            requires_execution=True,
        )
        return item

    @staticmethod
    def _post_review_item_key(item: PostReviewActionItem) -> tuple[str, str, tuple[str, ...]]:
        normalized = " ".join(item.summary.strip().lower().split())
        return (item.source, normalized, tuple(sorted(item.related_wp_ids)))

    @staticmethod
    def _normalize_improve_instruction(text: str) -> str:
        instruction = text.strip()
        if instruction.lower().startswith("/improve"):
            instruction = instruction[len("/improve") :].strip()
        return instruction

    @staticmethod
    def _is_post_review_done_command(instruction: str) -> bool:
        return instruction.strip().lower() in {
            "done",
            "complete",
            "close",
            "finish",
            "완료",
            "종료",
            "끝",
            "닫기",
        }

    def _select_post_review_items(self, instruction: str) -> list[str]:
        tokens = [token for token in re.split(r"[\s,]+", instruction.strip()) if token]
        if not tokens:
            return []
        items = self._post_review_items()
        selectable = [
            item
            for item in items
            if item.status
            in {PostReviewActionStatus.PROPOSED, PostReviewActionStatus.ACCEPTED}
        ]
        normalized_tokens = [token.lower() for token in tokens]
        if any(token in {"all", "*", "전체"} for token in normalized_tokens):
            return [item.id for item in selectable]
        if any(token in {"critical", "긴급"} for token in normalized_tokens):
            return [item.id for item in selectable if item.severity == "critical"]
        if any(token in {"high", "높음", "important", "중요"} for token in normalized_tokens):
            return [
                item.id
                for item in selectable
                if item.severity in {"critical", "high"}
            ]
        requested = {token.upper() for token in tokens}
        return [item.id for item in selectable if item.id.upper() in requested]

    @staticmethod
    def _looks_like_post_review_selector(instruction: str) -> bool:
        tokens = [token.lower() for token in re.split(r"[\s,]+", instruction.strip()) if token]
        if not tokens:
            return True
        selector_words = {
            "all",
            "*",
            "전체",
            "critical",
            "긴급",
            "high",
            "높음",
            "important",
            "중요",
        }
        return all(token in selector_words or re.fullmatch(r"ai-\d+", token) for token in tokens)

    def _next_post_review_item_id(
        self,
        existing: Iterable[PostReviewActionItem],
    ) -> str:
        used: set[int] = set()
        for item in existing:
            match = re.fullmatch(r"AI-(\d+)", item.id.strip().upper())
            if match:
                used.add(int(match.group(1)))
        index = 1
        while index in used:
            index += 1
        return f"AI-{index:03d}"

    def _next_supplemental_package_id(self) -> str:
        used: set[int] = set()
        for package in self.session.work_packages:
            match = re.fullmatch(r"WP-S(\d+)", package.id.strip().upper())
            if match:
                used.add(int(match.group(1)))
        index = 1
        while index in used:
            index += 1
        return f"WP-S{index:03d}"

    def _owner_for_post_review_item(
        self,
        item: PostReviewActionItem,
        active_agents: list[str],
        index: int,
    ) -> str:
        agents = [agent for agent in active_agents if agent]
        if item.suggested_owner and (not agents or item.suggested_owner in agents):
            return item.suggested_owner
        for package_id in item.related_wp_ids:
            owner = self._owner_for_related_package(package_id)
            if owner and (not agents or owner in agents):
                return owner
        if agents:
            return agents[index % len(agents)]
        return item.suggested_owner or "codex"

    def _owner_for_related_package(self, package_id: str) -> str:
        package = self._work_package_by_id(package_id)
        if package is None:
            return ""
        return package.last_executor or package.owner_agent

    def _record_follow_up_request(
        self,
        text: str,
        accepted_action_item_ids: Iterable[str],
        *,
        source_state: str | None = None,
    ) -> None:
        existing = self.session.follow_up_requests
        request = {
            "id": f"fur-{len(existing) + 1:03d}",
            "text": text,
            "source_state": source_state or self.session.state.value,
            "created_at": time.time(),
            "accepted_action_item_ids": [
                str(item_id) for item_id in accepted_action_item_ids
            ],
        }
        self.session.follow_up_requests.append(request)
        self.session.updated_at = time.time()
        self._persist("post_review_follow_up_requested", request)

    def _mark_post_review_items_done(self, item_ids: Iterable[str]) -> None:
        self._post_review_flow().mark_items_done(item_ids)

    @staticmethod
    def _supplemental_objective(item: PostReviewActionItem) -> str:
        parts = [
            f"Post-review action item {item.id}: {item.summary}",
            f"Source: {item.source}",
            f"Kind: {item.kind}",
            f"Severity: {item.severity}",
        ]
        if item.rationale:
            parts.append(f"Rationale: {item.rationale}")
        if item.related_wp_ids:
            parts.append(f"Related work packages: {', '.join(item.related_wp_ids)}")
        return "\n".join(parts)

    @staticmethod
    def _action_title(value: str, limit: int = 80) -> str:
        text = " ".join(value.strip().split())
        if not text:
            return "Post-review follow-up"
        sentence = re.split(r"[.!?\n]", text, maxsplit=1)[0].strip() or text
        if len(sentence) <= limit:
            return sentence
        return sentence[: limit - 3].rstrip() + "..."

    @staticmethod
    def _normalize_severity(value: str) -> str:
        normalized = str(value or "medium").strip().lower()
        return normalized if normalized in {"low", "medium", "high", "critical"} else "medium"

    @classmethod
    def _downgrade_optional_severity(cls, value: str) -> str:
        severity = cls._normalize_severity(value)
        if severity == "critical":
            return "high"
        if severity == "high":
            return "medium"
        return severity

    def _plan_review_packages(self) -> None:
        """Create peer review packages for completed execution results."""
        from trinity.workflow.review import PeerReviewPlanner

        planner = PeerReviewPlanner()
        reviewable_packages = [
            package
            for package in self.session.work_packages
            if package.requires_execution
            and package.status in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
            and not self._latest_review_is_approved(package.id)
        ]
        reviews = planner.plan_reviews(
            reviewable_packages,
            self._decomposition_agents(),
            self.session.execution_results,
        )
        self.session.review_packages = [review.to_dict() for review in reviews]

    def _upsert_subtask_result(self, result: SubtaskResult) -> None:
        """Insert or replace a subtask result by id."""
        for index, existing in enumerate(self.session.subtask_results):
            if existing.id == result.id:
                self.session.subtask_results[index] = result
                return
        self.session.subtask_results.append(result)

    def render_shared_ledger(
        self,
        provider_readiness: Any = None,
        *,
        round_opinions: str = "",
        response_diagnostics: str = "",
        session_history: str = "",
    ) -> str:
        """Render the human-readable shared.md ledger from structured state."""
        from trinity.workflow.ledger import render_shared_ledger

        return render_shared_ledger(
            self.session,
            provider_readiness=provider_readiness,
            round_opinions=round_opinions,
            response_diagnostics=response_diagnostics,
            session_history=session_history,
        )

    def sync_shared_ledger(
        self,
        shared: "SharedContextEngine",
        provider_readiness: Any = None,
    ) -> None:
        """Rewrite shared.md from session.json state while preserving log sections."""
        sections = self._extract_shared_preserved_sections(shared.read())
        shared.write(
            self.render_shared_ledger(
                provider_readiness=provider_readiness,
                round_opinions=sections["round_opinions"],
                response_diagnostics=sections["response_diagnostics"],
                session_history=sections["session_history"],
            )
        )

    @classmethod
    def _extract_shared_preserved_sections(cls, content: str) -> dict[str, str]:
        """Collect freeform shared.md sections that are not source-of-truth state."""
        sections = cls._parse_markdown_sections(content)
        round_sections = [
            body
            for heading, body in sections.items()
            if heading == "round opinions" or re.fullmatch(r"round\s+\d+\s+opinions", heading)
        ]
        return {
            "round_opinions": "\n\n".join(round_sections).strip(),
            "response_diagnostics": sections.get("response diagnostics", "").strip(),
            "session_history": sections.get("session history", "").strip(),
        }

    @staticmethod
    def _parse_markdown_sections(content: str) -> dict[str, str]:
        """Parse top-level markdown ## sections by normalized heading."""
        sections: dict[str, str] = {}
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in content.splitlines():
            if line.startswith("## ") and not line.startswith("### "):
                if current_heading is not None:
                    sections[current_heading] = "\n".join(current_lines).strip()
                current_heading = line[3:].strip().lower()
                current_lines = [line]
                continue
            if current_heading is not None:
                current_lines.append(line)

        if current_heading is not None:
            sections[current_heading] = "\n".join(current_lines).strip()
        return sections

    def set_state(self, state: WorkflowState, reason: str = "") -> None:
        """Set and persist workflow state."""
        old_state = self.session.state
        self.session.state = state
        self.session.updated_at = time.time()
        self._persist(
            "state_changed",
            {
                "from": old_state.value,
                "to": state.value,
                "reason": reason,
            },
        )

    def save(self) -> None:
        """Persist session.json."""
        self.persistence.save(self.session)

    def _persist(
        self,
        event_type: str,
        data: dict,
        *,
        timestamp: float | None = None,
    ) -> None:
        self.save()
        event_timestamp = self._event_timestamp(timestamp)
        event = {
            "timestamp": event_timestamp,
            "workflow_id": self.session.id,
            "event": event_type,
            "state": self.session.state.value,
            "data": data,
        }
        self.persistence.append_event(event)

    @staticmethod
    def _event_timestamp(timestamp: float | None) -> float:
        if timestamp is None:
            return time.time()
        try:
            return float(timestamp)
        except (TypeError, ValueError):
            return time.time()

    def _load_or_create(self) -> WorkflowSession:
        session = self.persistence.load()
        if session:
            return session
        return WorkflowSession(
            id=f"wf-{uuid4().hex[:12]}",
            goal="",
            state=WorkflowState.IDLE,
        )

    def _build_decision_continuation_prompt(self, decision: DecisionRecord) -> str:
        decisions = "\n".join(f"- {item.id}: {item.decision}" for item in self.session.decisions)
        return (
            "Continue the existing workflow using the user's decision below.\n\n"
            f"Original goal:\n{self.session.goal}\n\n"
            f"{self._target_workspace_prompt_block()}"
            f"Latest decision ({decision.id}):\n{decision.decision}\n\n"
            f"All decisions:\n{decisions}\n\n"
            "Update the design based on these decisions and continue deliberation. "
            "If a final blueprint is approved, include executable work packages "
            "covering the full deliverable graph, with owners, dependencies, "
            "expected files, acceptance criteria, risk, and parallelization metadata."
        )

    def _build_blueprint_continuation_prompt(self, instruction: str) -> str:
        blueprint = self.session.blueprint
        blueprint_title = blueprint.title if blueprint else "(none)"
        blueprint_summary = blueprint.summary if blueprint else "(none)"
        criteria = (
            "\n".join(f"- {item}" for item in blueprint.acceptance_criteria)
            if blueprint and blueprint.acceptance_criteria
            else "- none"
        )
        decisions = (
            "\n".join(f"- {item.id}: {item.decision}" for item in self.session.decisions)
            or "- none"
        )
        return (
            "Continue the existing workflow instead of starting a new one.\n\n"
            f"Original goal:\n{self.session.goal}\n\n"
            f"{self._target_workspace_prompt_block()}"
            "Current approved blueprint:\n"
            f"- Title: {blueprint_title}\n"
            f"- Summary: {blueprint_summary}\n"
            f"- Acceptance Criteria:\n{criteria}\n\n"
            f"User follow-up instruction:\n{instruction}\n\n"
            f"Recorded decisions:\n{decisions}\n\n"
            "Revise or confirm the blueprint using the user's follow-up. "
            "If the user is asking for implementation, produce an executable "
            "final blueprint and approve it. Preserve or regenerate a complete "
            "work package graph with owners, dependencies, expected files, "
            "acceptance criteria, risk, and parallelization metadata. If more "
            "user input is required, raise OPEN QUESTIONS."
        )

    def _target_workspace_prompt_block(self) -> str:
        target = self.session.target_workspace
        if target is None:
            return ""
        return (
            "Target Workspace Context:\n"
            f"- Target workspace: {target}\n"
            "- Scope project file references and implementation artifacts to this "
            "workspace.\n"
            "- The Trinity control repository is orchestration state unless it "
            "was explicitly selected as the target workspace.\n\n"
        )
