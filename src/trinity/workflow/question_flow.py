"""Open-question and decision-answer helpers for WorkflowEngine."""

from __future__ import annotations

import time
from typing import Any

from trinity.workflow.models import DecisionRecord, OpenQuestion, WorkflowState
from trinity.workflow.targeting_flow import WorkflowTargetingFlow


class WorkflowQuestionFlow:
    """Handle workflow open questions and user decisions."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def add_open_question(self, question: OpenQuestion) -> None:
        """Add a pending question and move workflow to waiting state."""
        self.engine.session.pending_questions.append(question)
        self.engine.set_state(
            WorkflowState.NEEDS_USER_DECISION,
            reason=f"question added: {question.id}",
        )

    def answer_pending_question(self, answer: str) -> Any:
        """Record an answer to the oldest open question and continue deliberation."""
        return self.answer_question("next", answer)

    def answer_question(
        self,
        selector: str,
        answer: str,
        *,
        replace: bool = False,
    ) -> Any:
        """Record or replace a user answer for a selected workflow question."""
        action_type = self.engine.input_action_type
        answer = answer.strip()
        if not answer:
            return action_type(
                should_deliberate=False,
                message="Answer cannot be empty.",
            )

        question = self.resolve_question(selector, include_answered=replace)
        if question is None:
            return action_type(
                should_deliberate=False,
                message=f"No matching workflow question: {selector}",
            )
        if question.status != "open" and not replace:
            return action_type(
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
                id=f"dec-{len(self.engine.session.decisions) + 1:03d}",
                question_id=question.id,
                decision=answer,
                decided_by="user",
                rationale=f"Answer to: {question.question}",
            )
            self.engine.session.decisions.append(decision)
            event_type = "decision_recorded"
            replaced = False

        self.engine.session.updated_at = time.time()
        self.engine._persistence_flow().persist(
            event_type,
            {
                "decision_id": decision.id,
                "question_id": question.id,
                "decision": answer,
                "replaced": replaced,
            },
        )

        if self.engine.pending_questions:
            self.engine.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="more blocking questions remain",
            )
            return action_type(
                should_deliberate=False,
                decision_record=decision,
                replaced_decision=replaced,
            )

        provider_gate = self.engine._provider_error_gate_flow()
        if provider_gate.is_gate_question(question):
            return provider_gate.handle_answer(
                answer,
                decision,
                replaced_decision=replaced,
            )

        self.engine.set_state(
            WorkflowState.DELIBERATING,
            reason="user decision answered",
        )
        target_agents = WorkflowTargetingFlow.effective_target_agents(
            self.engine.session.active_agents,
            self.engine.session.last_target_agents,
        )
        model_overrides = WorkflowTargetingFlow.normalized_model_overrides(
            self.engine.session.agent_model_overrides,
            target_agents,
        )
        active_agent_set = {
            str(agent).strip()
            for agent in self.engine.session.active_agents
            if str(agent).strip()
        }
        return action_type(
            should_deliberate=True,
            prompt=self.engine._central_flow().build_decision_continuation_prompt(
                decision
            ),
            target_agents=target_agents,
            agent_model_overrides=dict(model_overrides),
            agent_selection_mode=(
                "targeted" if set(target_agents) != active_agent_set else "all"
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
    ) -> Any:
        """Record a numbered option for a selected workflow question."""
        action_type = self.engine.input_action_type
        question = self.resolve_question(
            question_selector,
            include_answered=replace,
        )
        if question is None:
            return action_type(
                should_deliberate=False,
                message=f"No matching workflow question: {question_selector}",
            )
        if not option_selector.isdigit():
            return action_type(
                should_deliberate=False,
                message=f"Option must be a number: {option_selector}",
            )
        index = int(option_selector) - 1
        if index < 0 or index >= len(question.options):
            return action_type(
                should_deliberate=False,
                message=f"Question {question.id} has no option {option_selector}.",
            )
        return self.answer_question(
            question.id,
            question.options[index],
            replace=replace,
        )

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
        open_questions = self.engine.pending_questions
        questions = (
            self.engine.session.pending_questions
            if include_answered
            else open_questions
        )

        if normalized in {"next", "first"}:
            return open_questions[0] if open_questions else None

        if normalized.isdigit():
            index = int(normalized) - 1
            if 0 <= index < len(questions):
                return questions[index]
            return None

        if include_answered and normalized.startswith("dec-"):
            decision = next(
                (
                    item
                    for item in self.engine.session.decisions
                    if item.id.lower() == normalized
                ),
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
                for decision in self.engine.session.decisions
                if decision.question_id == question_id
            ),
            None,
        )

    def _next_decision_id(self) -> str:
        return f"dec-{len(self.engine.session.decisions) + 1:03d}"
