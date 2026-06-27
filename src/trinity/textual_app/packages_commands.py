"""Pure helpers for Textual packages command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


@dataclass(frozen=True)
class PackagesCommandPresentation:
    """Prepared local command result for `/packages`."""

    title: str
    body: str
    empty: bool
    action_hint: str
    table_columns: tuple[str, ...]
    table_rows: tuple[tuple[str, ...], ...]


def packages_command_presentation(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> PackagesCommandPresentation:
    """Return the presentation payload for a Textual `/packages` command."""
    has_packages = bool(snapshot.work_packages or snapshot.central_work_packages)
    return PackagesCommandPresentation(
        title=textual_presenters.packages_title(lang=lang),
        body=textual_presenters.packages_markdown(snapshot, lang=lang),
        empty=not has_packages,
        action_hint=textual_presenters.packages_action_hint(
            has_packages=has_packages,
            lang=lang,
        ),
        table_columns=textual_presenters.packages_table_columns(lang=lang),
        table_rows=textual_presenters.packages_rows(snapshot, lang=lang),
    )
