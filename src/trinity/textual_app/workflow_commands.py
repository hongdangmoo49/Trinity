"""Pure helpers for Textual workflow command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


@dataclass(frozen=True)
class WorkflowCommandPresentation:
    """Prepared local command result for `/workflow`."""

    title: str
    body: str
    table_columns: tuple[str, ...]
    table_rows: tuple[tuple[str, ...], ...]


def workflow_command_presentation(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> WorkflowCommandPresentation:
    """Return the presentation payload for a Textual `/workflow` command."""
    return WorkflowCommandPresentation(
        title=textual_presenters.workflow_title(lang=lang),
        body=textual_presenters.snapshot_workflow_markdown(snapshot, lang=lang),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.snapshot_workflow_rows(snapshot, lang=lang),
    )
