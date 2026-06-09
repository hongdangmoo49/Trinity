"""Workflow session persistence for Trinity v0.7.0."""

from __future__ import annotations

import json
import logging
import shutil
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trinity.workflow.models import WorkflowSession
from trinity.workflow.models import WorkflowState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowArchive:
    """A saved workflow session available for explicit resume."""

    session: WorkflowSession
    path: Path
    events_path: Path | None = None


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

    @property
    def history_dir(self) -> Path:
        """Return the directory containing archived workflow sessions."""
        return self.workflow_dir / "history"

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

    def load_events_for_workflow(
        self,
        workflow_id: str,
        *,
        tail: int | None = None,
        event_names: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Read events for one workflow, optionally filtered and tail-limited."""
        normalized_workflow_id = str(workflow_id).strip()
        if not normalized_workflow_id:
            return []

        names = {str(name) for name in event_names or ()}
        events = [
            event
            for event in self.load_events()
            if str(event.get("workflow_id", "")) == normalized_workflow_id
            and (not names or str(event.get("event", "")) in names)
        ]
        if tail is None:
            return events
        limit = max(0, int(tail or 0))
        if limit == 0:
            return []
        return events[-limit:]

    def last_event_for_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Return the latest persisted event for one workflow."""
        events = self.load_events_for_workflow(workflow_id, tail=1)
        return events[-1] if events else None

    def clear(self) -> None:
        """Remove persisted workflow files."""
        for path in (self.session_path, self.events_path):
            if path.exists():
                path.unlink()

    def archive_active_session(self, *, force: bool = False) -> WorkflowArchive | None:
        """Move the current active session into workflow history.

        Returns the archive metadata, or None when there is no meaningful active
        session to preserve.
        """
        session = self.load()
        if session is None:
            self.clear()
            return None
        if not force and not self._has_meaningful_session(session):
            self.clear()
            return None

        self.history_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time() * 1000)
        session_id = self._safe_name(session.id or "workflow")
        archive_path = self.history_dir / f"{timestamp}-{session_id}.json"
        archive_events_path = self.history_dir / f"{timestamp}-{session_id}.events.jsonl"

        archive_path.write_text(
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        events_path: Path | None = None
        if self.events_path.exists():
            shutil.copyfile(self.events_path, archive_events_path)
            events_path = archive_events_path

        self.clear()
        return WorkflowArchive(session=session, path=archive_path, events_path=events_path)

    def list_archives(self) -> list[WorkflowArchive]:
        """Return archived workflow sessions, newest first."""
        if not self.history_dir.exists():
            return []

        archives: list[WorkflowArchive] = []
        for path in self.history_dir.glob("*.json"):
            if path.name.endswith(".events.jsonl"):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                session = WorkflowSession.from_dict(data)
            except (json.JSONDecodeError, OSError, ValueError):
                logger.exception("Failed to load workflow archive from %s", path)
                continue

            events_path = path.with_suffix(".events.jsonl")
            archives.append(
                WorkflowArchive(
                    session=session,
                    path=path,
                    events_path=events_path if events_path.exists() else None,
                )
            )

        return sorted(
            archives,
            key=lambda archive: archive.session.updated_at,
            reverse=True,
        )

    def restore_archive(self, archive: WorkflowArchive) -> WorkflowSession:
        """Restore an archive into the active workflow files."""
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive.path, self.session_path)
        if archive.events_path and archive.events_path.exists():
            shutil.copyfile(archive.events_path, self.events_path)
        elif self.events_path.exists():
            self.events_path.unlink()
        return archive.session

    @staticmethod
    def _has_meaningful_session(session: WorkflowSession) -> bool:
        """Return whether a session should be preserved in history."""
        return any(
            (
                bool(session.goal.strip()),
                session.state != WorkflowState.IDLE,
                bool(session.active_agents),
                bool(session.pending_questions),
                bool(session.decisions),
                bool(session.work_packages),
                bool(session.execution_results),
                bool(session.subtask_results),
                bool(session.review_packages),
            )
        )

    @staticmethod
    def _safe_name(value: str) -> str:
        """Return a filesystem-safe identifier fragment."""
        cleaned = []
        for char in value:
            if char.isalnum() or char in {"-", "_"}:
                cleaned.append(char)
            else:
                cleaned.append("-")
        return "".join(cleaned).strip("-") or "workflow"
