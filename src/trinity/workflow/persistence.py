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


@dataclass(frozen=True)
class WorkflowEventSlice:
    """A bounded event view plus the total matching event count."""

    events: list[dict[str, Any]]
    total: int


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
        self._cached_events_key: tuple[int, int] | None = None
        self._cached_events: list[dict[str, Any]] | None = None

    @property
    def workflow_dir(self) -> Path:
        """Return the directory containing workflow persistence files."""
        return self.session_path.parent

    @property
    def history_dir(self) -> Path:
        """Return the directory containing archived workflow sessions."""
        return self.workflow_dir / "history"

    @property
    def archive_manifest_path(self) -> Path:
        """Return the summary manifest path for archived workflow sessions."""
        return self.history_dir / "manifest.json"

    @property
    def event_index_path(self) -> Path:
        """Return the workflow event offset index path."""
        return self.workflow_dir / "events.index.jsonl"

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
        line = json.dumps(dict(event), ensure_ascii=False) + "\n"
        encoded = line.encode("utf-8")
        try:
            offset = self.events_path.stat().st_size
        except OSError:
            offset = 0
        with self.events_path.open("ab") as fh:
            fh.write(encoded)
        self._append_event_index(dict(event), offset=offset, size=len(encoded))
        self._invalidate_events_cache()

    def load_events(self) -> list[dict[str, Any]]:
        """Read event dictionaries from the JSONL event log."""
        if not self.events_path.exists():
            self._invalidate_events_cache()
            return []

        cache_key = self._events_cache_key()
        if (
            cache_key is not None
            and self._cached_events_key == cache_key
            and self._cached_events is not None
        ):
            return self._clone_events(self._cached_events)

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

        self._cached_events_key = cache_key
        self._cached_events = self._clone_events(events)
        return events

    def load_events_for_workflow(
        self,
        workflow_id: str,
        *,
        tail: int | None = None,
        event_names: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Read events for one workflow, optionally filtered and tail-limited."""
        return self.load_event_slice_for_workflow(
            workflow_id,
            tail=tail,
            event_names=event_names,
        ).events

    def load_event_slice_for_workflow(
        self,
        workflow_id: str,
        *,
        tail: int | None = None,
        event_names: Iterable[str] | None = None,
    ) -> WorkflowEventSlice:
        """Read a bounded event slice and keep the total matching count."""
        normalized_workflow_id = str(workflow_id).strip()
        if not normalized_workflow_id:
            return WorkflowEventSlice(events=[], total=0)

        names = {str(name) for name in event_names or ()}
        indexed = self._load_indexed_event_slice_for_workflow(
            normalized_workflow_id,
            tail=tail,
            event_names=names,
        )
        if indexed is not None:
            return indexed

        events = [
            event
            for event in self.load_events()
            if str(event.get("workflow_id", "")) == normalized_workflow_id
            and (not names or str(event.get("event", "")) in names)
        ]
        total = len(events)
        if tail is None:
            return WorkflowEventSlice(events=events, total=total)
        limit = max(0, int(tail or 0))
        if limit == 0:
            return WorkflowEventSlice(events=[], total=total)
        return WorkflowEventSlice(events=events[-limit:], total=total)

    def last_event_for_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Return the latest persisted event for one workflow."""
        events = self.load_events_for_workflow(workflow_id, tail=1)
        return events[-1] if events else None

    def clear(self) -> None:
        """Remove persisted workflow files."""
        for path in (self.session_path, self.events_path, self.event_index_path):
            if path.exists():
                path.unlink()
        self._invalidate_events_cache()

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

        archive = WorkflowArchive(session=session, path=archive_path, events_path=events_path)
        self._refresh_archive_manifest()
        self.clear()
        return archive

    def list_archives(self) -> list[WorkflowArchive]:
        """Return archived workflow sessions, newest first."""
        if not self.history_dir.exists():
            return []
        manifest_archives = self._load_archives_from_manifest()
        if manifest_archives is not None:
            return manifest_archives
        return self._refresh_archive_manifest()

    def _scan_archives(self) -> list[WorkflowArchive]:
        archives: list[WorkflowArchive] = []
        for path in self.history_dir.glob("*.json"):
            if path == self.archive_manifest_path:
                continue
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
        if self.event_index_path.exists():
            self.event_index_path.unlink()
        self._invalidate_events_cache()
        return self.load() or archive.session

    def _refresh_archive_manifest(self) -> list[WorkflowArchive]:
        archives = self._scan_archives()
        self._write_archive_manifest(archives)
        return archives

    def _load_archives_from_manifest(self) -> list[WorkflowArchive] | None:
        path = self.archive_manifest_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to load workflow archive manifest from %s", path)
            return None
        if not isinstance(data, dict):
            return None
        entries = data.get("archives")
        if not isinstance(entries, list):
            return None

        archives: list[WorkflowArchive] = []
        seen_paths: set[Path] = set()
        for item in entries:
            if not isinstance(item, dict):
                return None
            archive = self._archive_from_manifest_entry(item)
            if archive is None:
                return None
            seen_paths.add(archive.path)
            archives.append(archive)

        actual_paths = {
            path
            for path in self.history_dir.glob("*.json")
            if path != self.archive_manifest_path and not path.name.endswith(".events.jsonl")
        }
        if seen_paths != actual_paths:
            return None
        return sorted(
            archives,
            key=lambda archive: archive.session.updated_at,
            reverse=True,
        )

    def _archive_from_manifest_entry(self, item: Mapping[str, Any]) -> WorkflowArchive | None:
        path_name = str(item.get("path", ""))
        if not path_name:
            return None
        archive_path = self.history_dir / path_name
        if not self._matches_manifest_file(
            archive_path,
            item.get("size_bytes"),
            item.get("mtime_ns"),
        ):
            return None

        events_path: Path | None = None
        events_name = str(item.get("events_path", "") or "")
        if events_name:
            candidate = self.history_dir / events_name
            if not self._matches_manifest_file(
                candidate,
                item.get("events_size_bytes"),
                item.get("events_mtime_ns"),
            ):
                return None
            events_path = candidate

        state_value = str(item.get("state", WorkflowState.IDLE.value))
        try:
            state = WorkflowState(state_value)
        except ValueError:
            state = WorkflowState.IDLE
        session = WorkflowSession(
            id=str(item.get("id", "")),
            goal=str(item.get("goal", "")),
            state=state,
            current_round=int(item.get("current_round", 0) or 0),
            created_at=float(item.get("created_at", 0.0) or 0.0),
            updated_at=float(item.get("updated_at", 0.0) or 0.0),
        )
        return WorkflowArchive(session=session, path=archive_path, events_path=events_path)

    def _write_archive_manifest(self, archives: list[WorkflowArchive]) -> None:
        self.history_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": 1,
            "generated_at": time.time(),
            "archives": [
                self._archive_manifest_entry(archive)
                for archive in sorted(
                    archives,
                    key=lambda item: item.session.updated_at,
                    reverse=True,
                )
            ],
        }
        self.archive_manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _archive_manifest_entry(self, archive: WorkflowArchive) -> dict[str, Any]:
        stat = archive.path.stat()
        events_stat = archive.events_path.stat() if archive.events_path else None
        return {
            "id": archive.session.id,
            "goal": archive.session.goal,
            "state": archive.session.state.value,
            "current_round": archive.session.current_round,
            "created_at": archive.session.created_at,
            "updated_at": archive.session.updated_at,
            "path": archive.path.name,
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "events_path": archive.events_path.name if archive.events_path else "",
            "events_size_bytes": events_stat.st_size if events_stat else 0,
            "events_mtime_ns": events_stat.st_mtime_ns if events_stat else 0,
        }

    @staticmethod
    def _matches_manifest_file(
        path: Path,
        size_bytes: Any,
        mtime_ns: Any,
    ) -> bool:
        try:
            stat = path.stat()
        except OSError:
            return False
        try:
            expected_size = int(size_bytes)
            expected_mtime = int(mtime_ns)
        except (TypeError, ValueError):
            return False
        return stat.st_size == expected_size and stat.st_mtime_ns == expected_mtime

    def _invalidate_events_cache(self) -> None:
        """Drop cached JSONL events after a local write or remove operation."""
        self._cached_events_key = None
        self._cached_events = None

    def _append_event_index(
        self,
        event: Mapping[str, Any],
        *,
        offset: int,
        size: int,
    ) -> None:
        workflow_id = str(event.get("workflow_id", "")).strip()
        try:
            stat = self.events_path.stat()
        except OSError:
            return
        self.event_index_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "version": 1,
            "workflow_id": workflow_id,
            "offset": int(offset),
            "size": int(size),
            "event": str(event.get("event", "")),
            "events_size_bytes": stat.st_size,
            "events_mtime_ns": stat.st_mtime_ns,
        }
        with self.event_index_path.open("ab") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False).encode("utf-8") + b"\n")
            return

    def _load_indexed_event_slice_for_workflow(
        self,
        workflow_id: str,
        *,
        tail: int | None,
        event_names: set[str],
    ) -> WorkflowEventSlice | None:
        index = self._load_event_index(rebuild=True)
        if index is None:
            return None
        entries = index.get(workflow_id, [])
        if not isinstance(entries, list):
            return None
        selected = [
            item
            for item in entries
            if isinstance(item, dict)
            and (not event_names or str(item.get("event", "")) in event_names)
        ]
        total = len(selected)
        if tail is not None:
            limit = max(0, int(tail or 0))
            if limit == 0:
                return WorkflowEventSlice(events=[], total=total)
            selected = selected[-limit:]
        if not selected:
            return WorkflowEventSlice(events=[], total=total)
        events = self._read_indexed_events(selected)
        if events is None:
            return None
        return WorkflowEventSlice(events=events, total=total)

    def _read_indexed_events(
        self,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | None:
        if not entries:
            return []
        events: list[dict[str, Any]] = []
        try:
            with self.events_path.open("rb") as fh:
                for item in entries:
                    offset = int(item.get("offset", -1))
                    size = int(item.get("size", 0))
                    if offset < 0 or size <= 0:
                        return None
                    fh.seek(offset)
                    raw = fh.read(size)
                    event = json.loads(raw.decode("utf-8").strip())
                    if not isinstance(event, dict):
                        return None
                    events.append(event)
        except (OSError, ValueError, json.JSONDecodeError):
            logger.exception("Failed to load workflow events from index: %s", self.events_path)
            return None
        return events

    def _load_event_index(self, *, rebuild: bool) -> dict[str, Any] | None:
        data = self._read_event_index_unchecked()
        if data is None:
            return self._rebuild_event_index() if rebuild else None
        if not self._event_index_matches(data):
            return self._rebuild_event_index() if rebuild else None
        return data

    def _read_event_index_unchecked(self) -> dict[str, list[dict[str, Any]]] | None:
        if not self.event_index_path.exists():
            return None
        entries: list[dict[str, Any]] = []
        try:
            with self.event_index_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    item = json.loads(stripped)
                    if not isinstance(item, dict):
                        return None
                    if int(item.get("version", 0) or 0) != 1:
                        return None
                    entries.append(item)
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to load workflow event index from %s", self.event_index_path)
            return None
        if not entries:
            return None
        if not self._event_index_entries_match(entries):
            return None
        return self._group_event_index_entries(entries)

    def _rebuild_event_index(self) -> dict[str, list[dict[str, Any]]]:
        if not self.events_path.exists():
            if self.event_index_path.exists():
                self.event_index_path.unlink()
            return {}
        entries: list[dict[str, Any]] = []
        try:
            with self.events_path.open("rb") as fh:
                while True:
                    offset = fh.tell()
                    raw = fh.readline()
                    if not raw:
                        break
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    event = json.loads(stripped.decode("utf-8"))
                    if not isinstance(event, dict):
                        continue
                    workflow_id = str(event.get("workflow_id", "")).strip()
                    entries.append(
                        {
                            "version": 1,
                            "workflow_id": workflow_id,
                            "offset": offset,
                            "size": len(raw),
                            "event": str(event.get("event", "")),
                        }
                    )
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to rebuild workflow event index from %s", self.events_path)
            return {}
        self._write_event_index_entries(entries)
        return self._group_event_index_entries(entries)

    def _write_event_index_entries(self, entries: list[dict[str, Any]]) -> None:
        if not entries:
            if self.event_index_path.exists():
                self.event_index_path.unlink()
            return
        try:
            stat = self.events_path.stat()
        except OSError:
            return
        normalized: list[dict[str, Any]] = []
        for entry in entries:
            item = dict(entry)
            item["version"] = 1
            item["events_size_bytes"] = stat.st_size
            item["events_mtime_ns"] = stat.st_mtime_ns
            normalized.append(item)
        self.event_index_path.parent.mkdir(parents=True, exist_ok=True)
        self.event_index_path.write_text(
            "".join(
                json.dumps(entry, ensure_ascii=False) + "\n"
                for entry in normalized
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _group_event_index_entries(
        entries: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            workflow_id = str(entry.get("workflow_id", "")).strip()
            if not workflow_id:
                continue
            grouped.setdefault(workflow_id, []).append(
                {
                    "offset": int(entry.get("offset", -1)),
                    "size": int(entry.get("size", 0)),
                    "event": str(entry.get("event", "")),
                }
            )
        return grouped

    def _event_index_matches(self, index: Mapping[str, Any]) -> bool:
        # A grouped index has already been validated while reading the JSONL file.
        return isinstance(index, dict)

    def _event_index_entries_match(self, entries: list[dict[str, Any]]) -> bool:
        try:
            stat = self.events_path.stat()
        except OSError:
            return False
        latest = entries[-1]
        try:
            return (
                int(latest.get("events_size_bytes")) == stat.st_size
                and int(latest.get("events_mtime_ns")) == stat.st_mtime_ns
            )
        except (TypeError, ValueError):
            return False

    def _events_cache_key(self) -> tuple[int, int] | None:
        try:
            stat = self.events_path.stat()
        except OSError:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    @staticmethod
    def _clone_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [dict(event) for event in events]

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
