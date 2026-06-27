"""Pure local slash-command state helpers for Textual surfaces."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


@dataclass(frozen=True)
class LocalCommandNotification:
    """Prepared notification payload for a local command result."""

    message: str
    title: str
    severity: str


@dataclass(frozen=True)
class LocalCommandResultEffect:
    """Prepared UI state changes for rendering a local slash-command result."""

    local_command_results: list[LocalCommandSnapshot]
    snapshot: WorkflowNexusSnapshot
    modal_result: LocalCommandSnapshot | None = None
    notification: LocalCommandNotification | None = None

    @property
    def show_modal(self) -> bool:
        """Return whether the result should be shown in a modal."""
        return self.modal_result is not None


def local_command_snapshot(
    command: str,
    title: str,
    body: str,
    *,
    severity: str = "info",
    result_kind: str = "markdown",
    empty: bool = False,
    action_hint: str = "",
    table_columns: tuple[str, ...] = (),
    table_rows: tuple[tuple[str, ...], ...] = (),
) -> LocalCommandSnapshot:
    """Build a local slash-command result snapshot."""
    return textual_presenters.local_command_snapshot(
        command,
        title,
        body,
        severity=severity,
        result_kind=result_kind,
        empty=empty,
        action_hint=action_hint,
        table_columns=table_columns,
        table_rows=table_rows,
    )


def local_command_notification(
    result: LocalCommandSnapshot,
    *,
    lang: str = "en",
) -> LocalCommandNotification:
    """Build the route notification shown after a local command result."""
    return LocalCommandNotification(
        message=result.title,
        title=textual_presenters.slash_command_notification_title(lang=lang),
        severity=textual_presenters.local_command_notification_severity(result),
    )


def recent_local_command_results(
    results: Sequence[LocalCommandSnapshot],
    *,
    limit: int = 8,
) -> list[LocalCommandSnapshot]:
    """Return the bounded local command history shown in Textual snapshots."""
    if limit <= 0:
        return []
    return list(results[-limit:])


def snapshot_with_local_command_results(
    snapshot: WorkflowNexusSnapshot,
    results: Sequence[LocalCommandSnapshot],
    *,
    limit: int = 8,
) -> WorkflowNexusSnapshot:
    """Attach bounded local command results to a workflow snapshot."""
    return replace(
        snapshot,
        local_commands=recent_local_command_results(results, limit=limit),
    )


def replace_local_command_result(
    results: Sequence[LocalCommandSnapshot],
    result: LocalCommandSnapshot,
) -> list[LocalCommandSnapshot]:
    """Keep only the latest result for a local slash command."""
    return [item for item in results if item.command != result.command] + [result]


def local_command_result_effect(
    result: LocalCommandSnapshot,
    snapshot: WorkflowNexusSnapshot,
    local_command_results: Sequence[LocalCommandSnapshot],
    *,
    current_route: str,
    start_modal: bool = True,
    notify: bool = True,
    lang: str = "en",
) -> LocalCommandResultEffect:
    """Return the UI state changes for rendering a local slash-command result."""
    updated_results = replace_local_command_result(local_command_results, result)
    updated_snapshot = snapshot_with_local_command_results(snapshot, updated_results)
    return LocalCommandResultEffect(
        local_command_results=updated_results,
        snapshot=updated_snapshot,
        modal_result=result if current_route == "start" and start_modal else None,
        notification=(
            local_command_notification(result, lang=lang)
            if notify and current_route != "start"
            else None
        ),
    )


def append_local_command_event(
    state_dir: Path,
    result: LocalCommandSnapshot,
    *,
    timestamp: float | None = None,
) -> bool:
    """Persist a local slash-command result as a central conversation event."""
    from trinity.workflow import WorkflowPersistence

    persistence = WorkflowPersistence(state_dir)
    session = persistence.load()
    if session is None or not session.id:
        return False

    event_timestamp = time.time() if timestamp is None else timestamp
    persistence.append_event(
        {
            "timestamp": event_timestamp,
            "workflow_id": session.id,
            "event": "central_conversation_recorded",
            "state": session.state.value,
            "data": {
                "message_id": f"cc-local-{int(event_timestamp * 1000)}",
                "role": "tool",
                "channel": "local_command",
                "title": result.title,
                "body": result.body,
                "command": result.command,
                "related_ids": [],
                "truncated": False,
            },
        }
    )
    return True
