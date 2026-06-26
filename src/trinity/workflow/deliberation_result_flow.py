"""Deliberation-result state transitions for WorkflowEngine."""

from __future__ import annotations

from typing import Any

from trinity.models import DeliberationResult
from trinity.workflow.central_flow import WorkflowCentralFlow
from trinity.workflow.intent import requires_execution_for_deliberation
from trinity.workflow.models import Blueprint, WorkflowState


class WorkflowDeliberationResultFlow:
    """Apply completed deliberation results to a workflow session."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def mark_deliberation_result(self, result: DeliberationResult) -> None:
        """Update workflow state after a deliberation completes."""
        self.engine.session.current_round = result.rounds_completed
        self.engine._provider_observations().record_provider_observations(
            result.metadata
        )
        provider_gate = self.engine._provider_error_gate_flow()
        if provider_gate.should_open(result):
            provider_gate.open(result)
            return

        central_flow = self.engine._central_flow()
        if self._apply_structured_deliberation_result(result, central_flow):
            return

        if self._apply_consensus_deliberation_result(result, central_flow):
            return

        self.engine.set_state(
            WorkflowState.FAILED,
            reason="deliberation ended without consensus",
        )

    def _apply_structured_deliberation_result(
        self,
        result: DeliberationResult,
        central_flow: WorkflowCentralFlow,
    ) -> bool:
        structured = result.metadata.get("structured_consensus")
        if not isinstance(structured, dict):
            return False
        if central_flow._apply_structured_questions(structured):
            self.engine.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="structured deliberation requires user decision",
            )
            return True

        blueprint = structured.get("final_blueprint")
        if not structured.get("reached") or not isinstance(blueprint, dict):
            return False

        self.engine.session.blueprint = Blueprint.from_dict(blueprint)
        self.engine.session.work_packages = self.engine.decomposer.decompose(
            self.engine.session.blueprint,
            self.engine._decomposition_agents(),
            requires_execution=requires_execution_for_deliberation(
                self.engine.session.goal,
                result,
            ),
        )
        self._clear_result_collections()
        central_flow._record_central_conversation(
            title="Central Agent Response",
            body=WorkflowCentralFlow._central_blueprint_body(
                self.engine.session.blueprint
            ),
            related_ids=[package.id for package in self.engine.session.work_packages],
        )
        self.engine.set_state(
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
        self.engine.session.blueprint = Blueprint(
            title="Consensus Blueprint",
            summary=summary,
            acceptance_criteria=[summary] if summary else [],
        )
        self.engine.session.work_packages = []
        self._clear_result_collections()
        central_flow._record_central_conversation(
            title="Central Agent Response",
            body=WorkflowCentralFlow._central_blueprint_body(
                self.engine.session.blueprint
            ),
            related_ids=[package.id for package in self.engine.session.work_packages],
        )
        self.engine.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="deliberation reached consensus",
        )
        return True

    def _clear_result_collections(self) -> None:
        self.engine.session.execution_results = []
        self.engine.session.subtask_results = []
        self.engine.session.review_packages = []
        self.engine.session.review_results = []
