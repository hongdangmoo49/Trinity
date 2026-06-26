"""Workflow session/event persistence helpers."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from trinity.workflow.models import WorkflowSession, WorkflowState


class WorkflowPersistenceFlow:
    """Persist workflow sessions and append workflow events."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def save(self) -> None:
        """Persist session.json."""
        self.engine.persistence.save(self.engine.session)

    def persist(
        self,
        event_type: str,
        data: dict,
        *,
        timestamp: float | None = None,
    ) -> None:
        """Persist the current session and append one workflow event."""
        self.save()
        event = {
            "timestamp": self.event_timestamp(timestamp),
            "workflow_id": self.engine.session.id,
            "event": event_type,
            "state": self.engine.session.state.value,
            "data": data,
        }
        self.engine.persistence.append_event(event)

    @staticmethod
    def event_timestamp(timestamp: float | None) -> float:
        if timestamp is None:
            return time.time()
        try:
            return float(timestamp)
        except (TypeError, ValueError):
            return time.time()

    def load_or_create(self) -> WorkflowSession:
        session = self.engine.persistence.load()
        if session:
            return session
        return WorkflowSession(
            id=f"wf-{uuid4().hex[:12]}",
            goal="",
            state=WorkflowState.IDLE,
        )
