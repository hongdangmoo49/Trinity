"""Stateful workflow engine for Trinity TUI sessions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable
from uuid import uuid4

from trinity.models import (
    AgentSpec,
    DeliberationResult,
)
from trinity.workflow.decomposer import (
    BlueprintDecomposer,
    classify_execution_intent,
)
from trinity.workflow.collection_flow import WorkflowCollectionFlow
from trinity.workflow.central_flow import WorkflowCentralFlow
from trinity.workflow.execution_flow import WorkflowExecutionFlow
from trinity.workflow.input_flow import WorkflowInputFlow
from trinity.workflow.lifecycle_flow import WorkflowLifecycleFlow
from trinity.workflow.ledger_sync import WorkflowLedgerSync
from trinity.workflow.post_review_flow import WorkflowPostReviewFlow
from trinity.workflow.provider_observations import WorkflowProviderObservations
from trinity.workflow.quality_flow import WorkflowQualityFlow
from trinity.workflow.question_flow import WorkflowQuestionFlow
from trinity.workflow.review_flow import WorkflowReviewFlow
from trinity.workflow.targeting_flow import WorkflowTargetingFlow
from trinity.workflow.workspace_flow import WorkflowWorkspaceFlow
from trinity.workflow.models import (
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    PostReviewActionItem,
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
    ReviewPackage,
    ReviewResult,
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
        return self._quality_flow().quality_summaries()

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
        return self._review_flow()._review_results()

    @property
    def post_review_items(self) -> list[PostReviewActionItem]:
        return self._post_review_flow()._post_review_items()

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

    def _central_flow(self) -> WorkflowCentralFlow:
        return WorkflowCentralFlow(self)

    def _collection_flow(self) -> WorkflowCollectionFlow:
        return WorkflowCollectionFlow(self)

    def _provider_observations(self) -> WorkflowProviderObservations:
        return WorkflowProviderObservations(self)

    def _question_flow(self) -> WorkflowQuestionFlow:
        return WorkflowQuestionFlow(self)

    def _quality_flow(self) -> WorkflowQualityFlow:
        return WorkflowQualityFlow(self)

    def _input_flow(self) -> WorkflowInputFlow:
        return WorkflowInputFlow(self)

    def _lifecycle_flow(self) -> WorkflowLifecycleFlow:
        return WorkflowLifecycleFlow(self)

    def _execution_flow(self) -> WorkflowExecutionFlow:
        return WorkflowExecutionFlow(self)

    def _review_flow(self) -> WorkflowReviewFlow:
        return WorkflowReviewFlow(self)

    def _post_review_flow(self) -> WorkflowPostReviewFlow:
        return WorkflowPostReviewFlow(self)

    def _ledger_sync(self) -> WorkflowLedgerSync:
        return WorkflowLedgerSync(self)

    def _workspace_flow(self) -> WorkflowWorkspaceFlow:
        return WorkflowWorkspaceFlow(self)

    @staticmethod
    def _effective_target_agents(
        active_agents: list[str],
        target_agents: list[str] | tuple[str, ...] | None,
    ) -> tuple[str, ...]:
        return WorkflowTargetingFlow.effective_target_agents(
            active_agents,
            target_agents,
        )

    @staticmethod
    def _normalized_model_overrides(
        agent_model_overrides: dict[str, str] | None,
        allowed_agents: tuple[str, ...] | list[str] = (),
    ) -> dict[str, str]:
        return WorkflowTargetingFlow.normalized_model_overrides(
            agent_model_overrides,
            allowed_agents,
        )

    def handle_user_input(
        self,
        text: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> WorkflowInputAction:
        """Route plain session text through the current workflow state."""
        return self._input_flow().handle_user_input(
            text,
            active_agents,
            target_agents=target_agents,
            agent_model_overrides=agent_model_overrides,
        )

    def _can_continue_existing_blueprint(self) -> bool:
        """Return whether free text should stay attached to this workflow."""
        return self._input_flow()._can_continue_existing_blueprint()

    def start(
        self,
        goal: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> WorkflowInputAction:
        """Start a new workflow for a user goal."""
        return self._lifecycle_flow().start(
            goal,
            active_agents,
            target_agents=target_agents,
            agent_model_overrides=agent_model_overrides,
        )

    def _should_carry_target_workspace_into_new_workflow(self) -> bool:
        """Return whether an idle preselected target should survive workflow start."""
        return self._lifecycle_flow()._should_carry_target_workspace_into_new_workflow()

    def answer_pending_question(self, answer: str) -> WorkflowInputAction:
        """Record an answer to the oldest open question and continue deliberation."""
        return self._question_flow().answer_pending_question(answer)

    def answer_question(
        self,
        selector: str,
        answer: str,
        *,
        replace: bool = False,
    ) -> WorkflowInputAction:
        """Record or replace a user answer for a selected workflow question."""
        return self._question_flow().answer_question(
            selector,
            answer,
            replace=replace,
        )

    def answer_question_option(
        self,
        option_selector: str,
        *,
        question_selector: str = "next",
        replace: bool = False,
    ) -> WorkflowInputAction:
        """Record a numbered option for a selected workflow question."""
        return self._question_flow().answer_question_option(
            option_selector,
            question_selector=question_selector,
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
        return self._lifecycle_flow().continue_from_blueprint(
            instruction,
            active_agents,
            target_agents=target_agents,
            agent_model_overrides=agent_model_overrides,
        )

    def enable_execution_for_current_blueprint(
        self,
        instruction: str = "",
    ) -> WorkflowInputAction:
        """Regenerate current blueprint packages as executable work packages."""
        return self._lifecycle_flow().enable_execution_for_current_blueprint(instruction)

    def _freeze_current_blueprint(self) -> Path | None:
        """Persist the approved blueprint as an immutable execution artifact."""
        return self._lifecycle_flow()._freeze_current_blueprint()

    def resolve_question(
        self,
        selector: str,
        *,
        include_answered: bool = False,
    ) -> OpenQuestion | None:
        """Resolve a question id, 1-based index, or ``next`` selector."""
        return self._question_flow().resolve_question(
            selector,
            include_answered=include_answered,
        )

    def _decision_for_question(self, question_id: str) -> DecisionRecord | None:
        """Return the existing decision attached to a question."""
        return self._question_flow()._decision_for_question(question_id)

    def _next_decision_id(self) -> str:
        return self._question_flow()._next_decision_id()

    def set_target_workspace(
        self,
        path: Path,
        *,
        control_repo_confirmed: bool = False,
    ) -> None:
        """Persist the workspace where provider implementation may write files."""
        self._workspace_flow().set_target_workspace(
            path,
            control_repo_confirmed=control_repo_confirmed,
        )

    def clear_target_workspace(self) -> None:
        """Clear the selected implementation workspace."""
        self._workspace_flow().clear_target_workspace()

    def add_open_question(self, question: OpenQuestion) -> None:
        """Add a pending question and move workflow to waiting state."""
        self._question_flow().add_open_question(question)

    def mark_deliberation_result(self, result: DeliberationResult) -> None:
        """Update workflow state after a deliberation completes."""
        self.session.current_round = result.rounds_completed
        self._record_provider_observations(result.metadata)
        provider_gate = self._provider_error_gate_flow()
        if provider_gate.should_open(result):
            provider_gate.open(result)
            return

        central_flow = self._central_flow()
        if self._apply_structured_deliberation_result(result, central_flow):
            return

        if self._apply_consensus_deliberation_result(result, central_flow):
            return

        self.set_state(WorkflowState.FAILED, reason="deliberation ended without consensus")

    def _apply_structured_deliberation_result(
        self,
        result: DeliberationResult,
        central_flow: WorkflowCentralFlow,
    ) -> bool:
        structured = result.metadata.get("structured_consensus")
        if not isinstance(structured, dict):
            return False
        if central_flow._apply_structured_questions(structured):
            self.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="structured deliberation requires user decision",
            )
            return True

        blueprint = structured.get("final_blueprint")
        if not structured.get("reached") or not isinstance(blueprint, dict):
            return False

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
        central_flow._record_central_conversation(
            title="Central Agent Response",
            body=WorkflowCentralFlow._central_blueprint_body(self.session.blueprint),
            related_ids=[package.id for package in self.session.work_packages],
        )
        self.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="structured blueprint reached consensus",
        )
        return True

    def _apply_consensus_deliberation_result(
        self,
        result: DeliberationResult,
        central_flow: WorkflowCentralFlow,
    ) -> bool:
        if not result.has_consensus:
            return False

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
        central_flow._record_central_conversation(
            title="Central Agent Response",
            body=WorkflowCentralFlow._central_blueprint_body(self.session.blueprint),
            related_ids=[package.id for package in self.session.work_packages],
        )
        self.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="deliberation reached consensus",
        )
        return True

    def _record_provider_observations(self, metadata: dict[str, Any]) -> None:
        self._provider_observations().record_provider_observations(metadata)

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

    def _record_review_result(self, result: ReviewResult) -> None:
        self._review_flow().record_review_result(result)

    def _record_execution_quality(self, result: ExecutionResult) -> None:
        self._quality_flow().record_execution_quality(result)

    def _record_review_quality(self, result: ReviewResult) -> None:
        self._quality_flow().record_review_quality(result)

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

    def mark_interrupted_execution(self) -> dict[str, Any] | None:
        """Turn stale running packages into blocked work that needs user review."""
        return self._execution_recovery_flow().mark_interrupted_execution()

    def abort_interrupted_execution(self) -> dict[str, Any] | None:
        """Abort a stale execution and require an explicit user decision."""
        return self._execution_recovery_flow().abort_interrupted_execution()

    def _review_repair_metadata_from_events(self) -> dict[str, dict[str, Any]]:
        return self._review_flow()._review_repair_metadata_from_events()

    def _plan_review_packages(self) -> None:
        self._review_flow()._plan_review_packages()

    def _upsert_subtask_result(self, result: SubtaskResult) -> None:
        """Insert or replace a subtask result by id."""
        self._collection_flow().upsert_subtask_result(result)

    def render_shared_ledger(
        self,
        provider_readiness: Any = None,
        *,
        round_opinions: str = "",
        response_diagnostics: str = "",
        session_history: str = "",
    ) -> str:
        """Render the human-readable shared.md ledger from structured state."""
        return self._ledger_sync().render_shared_ledger(
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
        self._ledger_sync().sync_shared_ledger(
            shared,
            provider_readiness=provider_readiness,
        )

    @classmethod
    def _extract_shared_preserved_sections(cls, content: str) -> dict[str, str]:
        return WorkflowLedgerSync._extract_shared_preserved_sections(content)

    @staticmethod
    def _parse_markdown_sections(content: str) -> dict[str, str]:
        return WorkflowLedgerSync._parse_markdown_sections(content)

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
        return self._central_flow()._build_decision_continuation_prompt(decision)

    def _build_blueprint_continuation_prompt(self, instruction: str) -> str:
        return self._central_flow()._build_blueprint_continuation_prompt(instruction)

    def _target_workspace_prompt_block(self) -> str:
        return self._central_flow()._target_workspace_prompt_block()
