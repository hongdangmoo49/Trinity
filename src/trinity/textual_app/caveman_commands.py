"""Pure helpers for Textual caveman command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class CavemanCommandPresentation:
    """Prepared local command result for `/caveman`."""

    title: str
    body: str
    severity: str = "info"
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


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
