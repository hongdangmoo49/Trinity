"""Workflow session persistence for Trinity v0.7.0."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trinity.workflow.models import WorkflowSession

logger = logging.getLogger(__name__)


class WorkflowPersistence:
    """Serialize workflow sessions and append-only event logs."""

    def __init__(
        self,
        state_dir: Path,
        *,
        state_file: Path | None = None,
        events_file: Path | None = None,
    ) -> None:
        workflow_dir = state_dir / "workflow"
        self.session_path = state_file or workflow_dir / "session.json"
        self.events_path = events_file or workflow_dir / "events.jsonl"

    @property
    def workflow_dir(self) -> Path:
        """Return the directory containing workflow persistence files."""
        return self.session_path.parent

    def save(self, session: WorkflowSession) -> None:
        """Write the session to disk as JSON."""
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.debug("Workflow session saved: %s", session.id)

    def load(self) -> WorkflowSession | None:
        """Load a persisted session, returning None when unavailable or invalid."""
        if not self.session_path.exists():
            return None
        try:
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            return WorkflowSession.from_dict(data)
        except (json.JSONDecodeError, OSError, ValueError):
            logger.exception("Failed to load workflow session from %s", self.session_path)
            return None

    def append_event(self, event: Mapping[str, Any]) -> None:
        """Append one event dictionary to the JSONL event log."""
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(event), ensure_ascii=False) + "\n")

    def load_events(self) -> list[dict[str, Any]]:
        """Read event dictionaries from the JSONL event log."""
        if not self.events_path.exists():
            return []

        events: list[dict[str, Any]] = []
        try:
            with self.events_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    event = json.loads(stripped)
                    if isinstance(event, dict):
                        events.append(event)
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to load workflow events from %s", self.events_path)
        return events

    def clear(self) -> None:
        """Remove persisted workflow files."""
        for path in (self.session_path, self.events_path):
            if path.exists():
                path.unlink()
