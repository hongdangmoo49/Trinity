"""Pure helpers for Textual decisions command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


@dataclass(frozen=True)
class DecisionsCommandPresentation:
    """Prepared local command result for `/decisions`."""

    title: str
    body: str
    empty: bool
    action_hint: str
    table_columns: tuple[str, ...]
    table_rows: tuple[tuple[str, ...], ...]


def decisions_command_presentation(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> DecisionsCommandPresentation:
    """Return the presentation payload for a Textual `/decisions` command."""
    has_decisions = bool(snapshot.decisions)
    return DecisionsCommandPresentation(
        title=textual_presenters.decisions_title(lang=lang),
        body=textual_presenters.decisions_markdown(snapshot, lang=lang),
        empty=not has_decisions,
        action_hint=textual_presenters.decisions_action_hint(
            has_decisions=has_decisions,
            lang=lang,
        ),
        table_columns=textual_presenters.decisions_table_columns(lang=lang),
        table_rows=textual_presenters.decisions_rows(snapshot, lang=lang),
    )
