"""Stateful provider error retry gate flow for WorkflowEngine."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

from trinity.models import DeliberationResult
from trinity.workflow import provider_error_gate
from trinity.workflow.models import (
    DecisionRecord,
    OpenQuestion,
    WorkflowSession,
    WorkflowState,
)
from trinity.workflow.provider_error_gate import PROVIDER_ERROR_GATE_QUESTION_ID


PersistCallback = Callable[..., None]
SetStateCallback = Callable[..., None]
ActionFactory = Callable[..., Any]
NormalizeModelOverridesCallback = Callable[[dict[str, str] | None, Iterable[str]], dict[str, str]]
MarkDeliberationResultCallback = Callable[[DeliberationResult], None]


class ProviderErrorGateFlow:
    """Stateful helper for provider error retry/continue/stop decisions."""

    def __init__(
        self,
        *,
        session: WorkflowSession,
        persist: PersistCallback,
        set_state: SetStateCallback,
        action_type: ActionFactory,
        normalize_model_overrides: NormalizeModelOverridesCallback,
        mark_deliberation_result: MarkDeliberationResultCallback,
    ) -> None:
        self.session = session
        self.persist = persist
        self.set_state = set_state
        self.action_type = action_type
        self.normalize_model_overrides = normalize_model_overrides
        self.mark_deliberation_result = mark_deliberation_result

    def should_open(self, result: DeliberationResult) -> bool:
        """Return whether provider failures should pause for user decision."""
        return provider_error_gate.should_open_provider_error_gate(result)

    def open(self, result: DeliberationResult) -> None:
        """Open a retry/continue/stop gate for retryable provider errors."""
        plan = provider_error_gate.build_provider_error_gate_plan(
            result,
            active_agents=self.session.active_agents,
            created_at=time.time(),
        )
        self.session.pending_questions = [
            item
            for item in self.session.pending_questions
            if item.id != PROVIDER_ERROR_GATE_QUESTION_ID
        ]
        self.session.pending_questions.append(plan.question)
        self.session.provider_error_gate = dict(plan.gate)
        self.session.updated_at = time.time()
        self.persist(
            "provider_error_gate_opened",
            {
                "question_id": plan.question.id,
                "failed_agents": plan.failed_agents,
                "can_continue": plan.can_continue,
                "failures": plan.failures,
            },
        )
        self.set_state(
            WorkflowState.NEEDS_USER_DECISION,
            reason="provider errors need retry decision",
        )

    def handle_answer(
        self,
        answer: str,
        decision: DecisionRecord,
        *,
        replaced_decision: bool,
    ) -> Any:
        """Resolve a provider error gate answer into a workflow input action."""
        choice = provider_error_gate.provider_error_gate_choice(answer)
        gate = dict(self.session.provider_error_gate)
        failed_agents = tuple(
            str(agent)
            for agent in gate.get("failed_agents", [])
            if str(agent).strip()
        )

        if choice == "continue":
            return self._continue_without_failed_providers(
                gate,
                failed_agents,
                decision,
                replaced_decision=replaced_decision,
            )

        if choice == "stop":
            return self._stop_after_provider_errors(
                failed_agents,
                decision,
                replaced_decision=replaced_decision,
            )

        return self._retry_failed_providers(
            gate,
            failed_agents,
            decision,
            replaced_decision=replaced_decision,
        )

    @staticmethod
    def is_gate_question(question: OpenQuestion) -> bool:
        """Return whether an open question belongs to provider error gate flow."""
        return provider_error_gate.is_provider_error_gate_question(question)

    def _continue_without_failed_providers(
        self,
        gate: dict[str, Any],
        failed_agents: tuple[str, ...],
        decision: DecisionRecord,
        *,
        replaced_decision: bool,
    ) -> Any:
        if not bool(gate.get("can_continue", False)):
            self.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="provider error gate continue is unavailable",
            )
            return self.action_type(
                should_deliberate=False,
                decision_record=decision,
                replaced_decision=replaced_decision,
                message="Continue is not available because no usable consensus exists.",
            )
        result = provider_error_gate.deliberation_result_from_dict(
            gate.get("result", {}) if isinstance(gate.get("result", {}), dict) else {}
        )
        result.metadata["provider_error_gate_bypassed"] = True
        self.session.provider_error_gate = {}
        self.persist(
            "provider_error_gate_resolved",
            {"action": "continue", "failed_agents": list(failed_agents)},
        )
        self.mark_deliberation_result(result)
        return self.action_type(
            should_deliberate=False,
            decision_record=decision,
            replaced_decision=replaced_decision,
            message="Continuing without failed providers.",
        )

    def _stop_after_provider_errors(
        self,
        failed_agents: tuple[str, ...],
        decision: DecisionRecord,
        *,
        replaced_decision: bool,
    ) -> Any:
        self.session.provider_error_gate = {}
        self.persist(
            "provider_error_gate_resolved",
            {"action": "stop", "failed_agents": list(failed_agents)},
        )
        self.set_state(WorkflowState.FAILED, reason="provider error gate stopped")
        return self.action_type(
            should_deliberate=False,
            decision_record=decision,
            replaced_decision=replaced_decision,
            message="Workflow stopped after provider errors.",
        )

    def _retry_failed_providers(
        self,
        gate: dict[str, Any],
        failed_agents: tuple[str, ...],
        decision: DecisionRecord,
        *,
        replaced_decision: bool,
    ) -> Any:
        self.session.provider_error_gate = {
            **gate,
            "state": "retry_requested",
            "retry_requested_at": time.time(),
        }
        self.persist(
            "provider_error_gate_resolved",
            {"action": "retry", "failed_agents": list(failed_agents)},
        )
        self.set_state(
            WorkflowState.DELIBERATING,
            reason="retrying failed provider responses",
        )
        return self.action_type(
            should_deliberate=True,
            prompt=provider_error_gate.provider_error_retry_prompt(gate),
            target_agents=failed_agents,
            agent_model_overrides=self.normalize_model_overrides(
                self.session.agent_model_overrides,
                failed_agents,
            ),
            agent_selection_mode="targeted",
            provider_retry_merge_context=provider_error_gate.provider_error_retry_context(gate),
            decision_record=decision,
            replaced_decision=replaced_decision,
            message="Retrying failed providers.",
        )
