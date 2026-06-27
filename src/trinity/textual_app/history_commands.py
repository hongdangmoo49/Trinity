"""Pure helpers for Textual history command presentation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


@dataclass(frozen=True)
class HistoryCommandPresentation:
    """Prepared local command result for `/history`."""

    title: str
    body: str
    empty: bool
    action_hint: str
    table_columns: tuple[str, ...]
    table_rows: tuple[tuple[str, ...], ...]


def history_command_presentation(
    snapshot: WorkflowNexusSnapshot,
    local_command_results: Sequence[LocalCommandSnapshot],
    *,
    lang: str = "en",
) -> HistoryCommandPresentation:
    """Return the presentation payload for a Textual `/history` command."""
    rows = textual_presenters.history_rows(
        snapshot,
        local_command_results,
        lang=lang,
    )
    return HistoryCommandPresentation(
        title=textual_presenters.history_title(lang=lang),
        body=textual_presenters.history_markdown(snapshot, rows, lang=lang),
        empty=not rows,
        action_hint=textual_presenters.history_action_hint(
            has_history=bool(rows),
            lang=lang,
        ),
        table_columns=textual_presenters.history_table_columns(lang=lang),
        table_rows=rows,
    )
