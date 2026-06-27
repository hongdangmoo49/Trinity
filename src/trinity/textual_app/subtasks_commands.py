"""Pure helpers for Textual subtasks command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


@dataclass(frozen=True)
class SubtasksCommandPresentation:
    """Prepared local command result for `/subtasks`."""

    title: str
    body: str
    empty: bool
    action_hint: str
    table_columns: tuple[str, ...]
    table_rows: tuple[tuple[str, ...], ...]


def subtasks_command_presentation(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> SubtasksCommandPresentation:
    """Return the presentation payload for a Textual `/subtasks` command."""
    has_subtasks = bool(snapshot.subtasks)
    return SubtasksCommandPresentation(
        title=textual_presenters.subtasks_title(lang=lang),
        body=textual_presenters.subtasks_markdown(snapshot, lang=lang),
        empty=not has_subtasks,
        action_hint=textual_presenters.subtasks_action_hint(
            has_subtasks=has_subtasks,
            lang=lang,
        ),
        table_columns=textual_presenters.subtasks_table_columns(lang=lang),
        table_rows=textual_presenters.subtasks_rows(snapshot, lang=lang),
    )
