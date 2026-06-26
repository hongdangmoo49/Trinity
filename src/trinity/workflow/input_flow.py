"""User input routing helpers for WorkflowEngine."""

from __future__ import annotations

from typing import Any

from trinity.workflow.models import WorkflowState


class WorkflowInputFlow:
    """Route plain session input to the appropriate workflow operation."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def handle_user_input(
        self,
        text: str,
        active_agents: list[str],
        *,
        target_agents: list[str] | tuple[str, ...] | None = None,
        agent_model_overrides: dict[str, str] | None = None,
    ) -> Any:
        """Route plain session text through the current workflow state."""
        if self.engine.session.state == WorkflowState.POST_REVIEW_READY:
            return self.engine.handle_post_review_input(text, active_agents)
        if self.engine.session.state == WorkflowState.NEEDS_USER_DECISION:
            return self.engine.answer_pending_question(text)
        if self._can_continue_existing_blueprint():
            return self.engine.continue_from_blueprint(
                text,
                active_agents,
                target_agents=target_agents,
                agent_model_overrides=agent_model_overrides,
            )
        return self.engine.start(
            text,
            active_agents,
            target_agents=target_agents,
            agent_model_overrides=agent_model_overrides,
        )

    def _can_continue_existing_blueprint(self) -> bool:
        """Return whether free text should stay attached to this workflow."""
        return (
            self.engine.session.blueprint is not None
            and self.engine.session.state
            in {
                WorkflowState.BLUEPRINT_READY,
                WorkflowState.REVIEWING,
                WorkflowState.DONE,
                WorkflowState.FAILED,
            }
        )
