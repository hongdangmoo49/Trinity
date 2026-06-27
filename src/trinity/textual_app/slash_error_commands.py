"""Pure helpers for Textual slash command error presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class SlashErrorCommandPresentation:
    """Prepared local command result for slash command parsing/routing errors."""

    title: str
    body: str
    severity: str = "warning"
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


def slash_syntax_error_presentation(
    error: str,
    *,
    lang: str = "en",
) -> SlashErrorCommandPresentation:
    """Return the warning presentation payload for slash command syntax errors."""
    return SlashErrorCommandPresentation(
        title=textual_presenters.syntax_error_title(lang=lang),
        body=error,
    )


def unknown_slash_command_presentation(
    command_token: str,
    *,
    lang: str = "en",
) -> SlashErrorCommandPresentation:
    """Return the warning presentation payload for unknown slash commands."""
    suggestions = textual_presenters.slash_command_suggestions(command_token)
    return SlashErrorCommandPresentation(
        title=textual_presenters.unknown_command_title(lang=lang),
        body=textual_presenters.unknown_command_markdown(
            command_token,
            suggestions,
            lang=lang,
        ),
        table_columns=textual_presenters.unknown_command_table_columns(lang=lang),
        table_rows=textual_presenters.unknown_command_rows(
            suggestions,
            lang=lang,
        ),
    )
