"""Pure helpers for Textual help command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class HelpCommandPresentation:
    """Prepared local command result for `/help`."""

    title: str
    body: str
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


def help_command_presentation(*, lang: str = "en") -> HelpCommandPresentation:
    """Return the presentation payload for registry-backed `/help` output."""
    return HelpCommandPresentation(
        title=textual_presenters.help_title(lang=lang),
        body=textual_presenters.help_markdown(lang=lang),
        table_columns=textual_presenters.help_table_columns(lang=lang),
        table_rows=textual_presenters.help_rows(lang=lang),
    )
