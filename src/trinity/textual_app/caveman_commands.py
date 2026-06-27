"""Pure helpers for Textual caveman command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from trinity.textual_app.command_parsers import parse_caveman_args
from trinity.textual_app import presenters as textual_presenters


class CavemanCommandState(Protocol):
    """Mutable `/caveman` session setting subset."""

    caveman_mode: bool
    caveman_intensity: str


@dataclass(frozen=True)
class CavemanCommandPresentation:
    """Prepared local command result for `/caveman`."""

    title: str
    body: str
    severity: str = "info"
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


def caveman_command_presentation(
    state: CavemanCommandState,
    args: list[str],
    *,
    lang: str = "en",
) -> CavemanCommandPresentation:
    """Apply `/caveman` args and return the resulting presentation."""
    if not args:
        return caveman_current_presentation(
            _mode_label(state.caveman_mode),
            state.caveman_intensity,
            lang=lang,
        )

    parsed = parse_caveman_args(args, lang=lang)
    if parsed.error:
        return caveman_error_presentation(
            parsed.error,
            parsed.action_hint,
            lang=lang,
        )

    if parsed.enabled is not None:
        state.caveman_mode = parsed.enabled
    if parsed.intensity:
        state.caveman_intensity = parsed.intensity
    return caveman_set_presentation(
        _mode_label(state.caveman_mode),
        state.caveman_intensity,
        lang=lang,
    )


def caveman_current_presentation(
    mode: str,
    intensity: str,
    *,
    lang: str = "en",
) -> CavemanCommandPresentation:
    """Return the presentation payload for current `/caveman` settings."""
    return CavemanCommandPresentation(
        title=textual_presenters.caveman_title(lang=lang),
        body=textual_presenters.session_setting_body(
            textual_presenters.caveman_current_markdown(
                mode,
                intensity,
                lang=lang,
            )
        ),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.caveman_rows(
            mode,
            intensity,
            lang=lang,
        ),
        action_hint=textual_presenters.caveman_change_action_hint(lang=lang),
    )


def caveman_set_presentation(
    mode: str,
    intensity: str,
    *,
    lang: str = "en",
) -> CavemanCommandPresentation:
    """Return the presentation payload for a changed `/caveman` setting."""
    return CavemanCommandPresentation(
        title=textual_presenters.caveman_title(lang=lang),
        body=textual_presenters.session_setting_body(
            textual_presenters.caveman_set_markdown(
                mode,
                intensity,
                lang=lang,
            )
        ),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.caveman_rows(
            mode,
            intensity,
            lang=lang,
        ),
    )


def caveman_error_presentation(
    error: str,
    action_hint: str,
    *,
    lang: str = "en",
) -> CavemanCommandPresentation:
    """Return the warning presentation payload for invalid `/caveman` input."""
    return CavemanCommandPresentation(
        title=textual_presenters.caveman_title(lang=lang),
        body=error,
        severity="warning",
        action_hint=action_hint,
    )


def _mode_label(enabled: bool) -> str:
    return "on" if enabled else "off"
