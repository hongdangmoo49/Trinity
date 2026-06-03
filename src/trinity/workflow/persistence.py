"""Workflow session persistence for Trinity v0.7.0."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from trinity.models import WorkflowEvent, WorkflowSession

logger = logging.getLogger(__name__)


class WorkflowPersistence:
    """Serialize and persist workflow sessions and event logs."""

    def __init__(self, state_dir: Path) -> None:
        self.workflow_dir = state_dir / "workflow"
        self.session_path = self.workflow_dir / "session.json"
        self.events_path = self.workflow_dir / "events.jsonl"

    def save(self, session: WorkflowSession) -> None:
        """Write the session to disk as JSON."""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        data = session.to_dict()
        self.session_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Session saved: session=%s", session.id)

    def load(self) -> WorkflowSession | None:
        """Load a session from disk. Returns None if no session file exists."""
        if not self.session_path.exists():
            return None
        try:
            raw = self.session_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            session = WorkflowSession.from_dict(data)
            logger.info("Session loaded: session=%s", session.id)
            return session
        except Exception:
            logger.exception("Failed to load session from %s", self.session_path)
            return None

    def append_event(self, event: WorkflowEvent) -> None:
        """Append a single event to the JSONL event log."""
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        logger.debug("Event appended: %s", event.event_type)

    def load_events(self) -> list[WorkflowEvent]:
        """Read all events from the JSONL event log."""
        if not self.events_path.exists():
            return []
        events: list[WorkflowEvent] = []
        try:
            with self.events_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    events.append(WorkflowEvent.from_dict(data))
        except Exception:
            logger.exception("Failed to load events from %s", self.events_path)
        return events

    def clear(self) -> None:
        """Remove session and events files."""
        for path in (self.session_path, self.events_path):
            if path.exists():
                path.unlink()
                logger.info("Removed %s", path)
