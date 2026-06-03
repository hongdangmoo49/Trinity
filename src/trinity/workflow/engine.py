"""Workflow engine state machine for Trinity v0.7.0."""

from __future__ import annotations

import logging
import uuid
from dataclasses import replace

from trinity.models import (
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    WorkflowSession,
    WorkflowState,
    WorkPackage,
)

logger = logging.getLogger(__name__)

# Valid state transitions: current state -> set of allowed target states
_VALID_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.IDLE: {WorkflowState.PREFLIGHT},
    WorkflowState.PREFLIGHT: {WorkflowState.DELIBERATING, WorkflowState.FAILED},
    WorkflowState.DELIBERATING: {
        WorkflowState.NEEDS_USER_DECISION,
        WorkflowState.BLUEPRINT_READY,
        WorkflowState.FAILED,
    },
    WorkflowState.NEEDS_USER_DECISION: {WorkflowState.DELIBERATING},
    WorkflowState.BLUEPRINT_READY: {WorkflowState.EXECUTING, WorkflowState.DONE},
    WorkflowState.EXECUTING: {WorkflowState.REVIEWING, WorkflowState.DONE, WorkflowState.FAILED},
    WorkflowState.REVIEWING: {
        WorkflowState.NEEDS_USER_DECISION,
        WorkflowState.DONE,
        WorkflowState.FAILED,
    },
    WorkflowState.DONE: set(),
    WorkflowState.FAILED: set(),
}


class WorkflowEngine:
    """State machine that drives the Trinity workflow lifecycle."""

    def __init__(self) -> None:
        self._session: WorkflowSession | None = None

    # -- public transition methods -------------------------------------------

    def start(self, goal: str, active_agents: list[str]) -> WorkflowSession:
        """Create a new session and transition IDLE -> PREFLIGHT."""
        if self._session is not None:
            raise RuntimeError("Session already active; call restore() to replace it")
        session = WorkflowSession(
            id=uuid.uuid4().hex[:8],
            goal=goal,
            state=WorkflowState.IDLE,
            active_agents=list(active_agents),
        )
        self._session = session
        self._transition(WorkflowState.PREFLIGHT)
        logger.info("Workflow started: session=%s goal=%s", session.id, goal)
        return self._session

    def transition_preflight(self, ready_agents: list[str]) -> WorkflowSession:
        """Transition PREFLIGHT -> DELIBERATING (or FAILED if no agents ready).

        Filters session.active_agents to only those present in ready_agents.
        """
        self._ensure_session()
        self._ensure_state(WorkflowState.PREFLIGHT)
        if not ready_agents:
            self._transition(WorkflowState.FAILED)
            logger.info("Preflight failed: no ready agents, session=%s", self._session.id)
            return self._session

        # Keep only agents that are ready
        ready_set = set(ready_agents)
        filtered = [a for a in self._session.active_agents if a in ready_set]
        self._session = replace(self._session, active_agents=filtered)
        self._transition(WorkflowState.DELIBERATING)
        logger.info(
            "Preflight passed: %d agents ready, session=%s",
            len(filtered),
            self._session.id,
        )
        return self._session

    def transition_needs_user_decision(
        self, questions: list[OpenQuestion]
    ) -> WorkflowSession:
        """Transition DELIBERATING|REVIEWING -> NEEDS_USER_DECISION, storing questions."""
        self._ensure_session()
        if self._session.state not in (
            WorkflowState.DELIBERATING,
            WorkflowState.REVIEWING,
        ):
            self._raise_invalid(WorkflowState.NEEDS_USER_DECISION)
        self._session = replace(
            self._session,
            pending_questions=list(questions),
        )
        self._transition(WorkflowState.NEEDS_USER_DECISION)
        logger.info(
            "Needs user decision: %d questions, session=%s",
            len(questions),
            self._session.id,
        )
        return self._session

    def transition_user_answered(self, decision: DecisionRecord) -> WorkflowSession:
        """Transition NEEDS_USER_DECISION -> DELIBERATING, recording the decision."""
        self._ensure_session()
        self._ensure_state(WorkflowState.NEEDS_USER_DECISION)
        # Remove the answered question
        remaining = [
            q for q in self._session.pending_questions if q.id != decision.question_id
        ]
        self._session = replace(
            self._session,
            pending_questions=remaining,
            decisions=self._session.decisions + [decision],
        )
        self._transition(WorkflowState.DELIBERATING)
        logger.info("User answered: question_id=%s, session=%s", decision.question_id, self._session.id)
        return self._session

    def transition_blueprint_ready(self, blueprint: Blueprint) -> WorkflowSession:
        """Transition DELIBERATING -> BLUEPRINT_READY, storing the blueprint."""
        self._ensure_session()
        self._ensure_state(WorkflowState.DELIBERATING)
        self._session = replace(self._session, blueprint=blueprint)
        self._transition(WorkflowState.BLUEPRINT_READY)
        logger.info("Blueprint ready: %s, session=%s", blueprint.title, self._session.id)
        return self._session

    def transition_executing(self, work_packages: list[WorkPackage]) -> WorkflowSession:
        """Transition BLUEPRINT_READY -> EXECUTING, storing work packages."""
        self._ensure_session()
        self._ensure_state(WorkflowState.BLUEPRINT_READY)
        self._session = replace(self._session, work_packages=list(work_packages))
        self._transition(WorkflowState.EXECUTING)
        logger.info(
            "Executing: %d work packages, session=%s",
            len(work_packages),
            self._session.id,
        )
        return self._session

    def transition_done(self, results: list[ExecutionResult]) -> WorkflowSession:
        """Transition to DONE from EXECUTING, BLUEPRINT_READY, or REVIEWING."""
        self._ensure_session()
        if self._session.state not in (
            WorkflowState.EXECUTING,
            WorkflowState.BLUEPRINT_READY,
            WorkflowState.REVIEWING,
        ):
            self._raise_invalid(WorkflowState.DONE)
        self._session = replace(self._session, execution_results=list(results))
        self._transition(WorkflowState.DONE)
        logger.info("Workflow done: session=%s", self._session.id)
        return self._session

    def transition_failed(self, reason: str = "") -> WorkflowSession:
        """Transition to FAILED from any non-terminal state."""
        self._ensure_session()
        self._transition(WorkflowState.FAILED)
        logger.info("Workflow failed: session=%s reason=%s", self._session.id, reason)
        return self._session

    def restore(self, session: WorkflowSession) -> None:
        """Restore a previously saved session."""
        self._session = session
        logger.info("Session restored: session=%s state=%s", session.id, session.state.value)

    # -- internal helpers ----------------------------------------------------

    def _transition(self, target: WorkflowState) -> None:
        """Validate and apply a state transition. Raises ValueError if invalid."""
        assert self._session is not None  # guaranteed by callers
        current = self._session.state
        allowed = _VALID_TRANSITIONS.get(current, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {current.value} -> {target.value}"
            )
        self._session = replace(self._session, state=target)

    def _ensure_session(self) -> None:
        """Raise RuntimeError if no active session."""
        if self._session is None:
            raise RuntimeError("No active workflow session")

    def _ensure_state(self, expected: WorkflowState) -> None:
        """Raise ValueError if the session is not in the expected state."""
        assert self._session is not None
        if self._session.state != expected:
            raise ValueError(
                f"Expected state {expected.value}, got {self._session.state.value}"
            )

    def _raise_invalid(self, target: WorkflowState) -> None:
        """Raise ValueError for an invalid transition (used by transition_done)."""
        assert self._session is not None
        raise ValueError(
            f"Invalid transition: {self._session.state.value} -> {target.value}"
        )
