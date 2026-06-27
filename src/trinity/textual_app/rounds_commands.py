"""Pure helpers for Textual rounds command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from trinity.textual_app.command_parsers import parse_rounds_args
from trinity.textual_app import presenters as textual_presenters


class RoundsCommandState(Protocol):
    """Mutable `/rounds` session setting subset."""

    max_deliberation_rounds: int


@dataclass(frozen=True)
class RoundsCommandPresentation:
    """Prepared local command result for `/rounds`."""

    title: str
    body: str
    severity: str = "info"
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


def rounds_command_presentation(
    state: RoundsCommandState,
    args: list[str],
    *,
    lang: str = "en",
) -> RoundsCommandPresentation:
    """Apply `/rounds` args and return the resulting presentation."""
    parsed = parse_rounds_args(args, lang=lang)
    if parsed.rounds is None and not parsed.error:
        return rounds_current_presentation(
            state.max_deliberation_rounds,
            lang=lang,
        )
    if parsed.error:
        return rounds_error_presentation(
            parsed.error,
            parsed.action_hint,
            lang=lang,
        )

    state.max_deliberation_rounds = parsed.rounds or state.max_deliberation_rounds
    return rounds_set_presentation(
        state.max_deliberation_rounds,
        lang=lang,
    )


def rounds_current_presentation(
    value: int,
    *,
    lang: str = "en",
) -> RoundsCommandPresentation:
    """Return the presentation payload for current `/rounds` settings."""
    return RoundsCommandPresentation(
        title=textual_presenters.rounds_title(lang=lang),
        body=textual_presenters.session_setting_body(
            textual_presenters.rounds_current_markdown(value, lang=lang)
        ),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.rounds_rows(value, lang=lang),
        action_hint=textual_presenters.rounds_change_action_hint(lang=lang),
    )


def rounds_set_presentation(
    value: int,
    *,
    lang: str = "en",
) -> RoundsCommandPresentation:
    """Return the presentation payload for a changed `/rounds` setting."""
    return RoundsCommandPresentation(
        title=textual_presenters.rounds_title(lang=lang),
        body=textual_presenters.session_setting_body(
            textual_presenters.rounds_set_markdown(value, lang=lang)
        ),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.rounds_rows(value, lang=lang),
    )


def rounds_error_presentation(
    error: str,
    action_hint: str,
    *,
    lang: str = "en",
) -> RoundsCommandPresentation:
    """Return the warning presentation payload for invalid `/rounds` input."""
    return RoundsCommandPresentation(
        title=textual_presenters.rounds_title(lang=lang),
        body=error,
        severity="warning",
        action_hint=action_hint,
    )
