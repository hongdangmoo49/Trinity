"""Pure helpers for Textual ask command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class AskCommandPresentation:
    """Prepared local command result for `/ask` errors."""

    title: str
    body: str
    severity: str = "info"
    empty: bool = False
    action_hint: str = ""


def ask_error_presentation(
    error: str,
    *,
    lang: str = "en",
) -> AskCommandPresentation:
    """Return the warning presentation payload for invalid `/ask` input."""
    return AskCommandPresentation(
        title=textual_presenters.ask_title(lang=lang),
        body=error,
        severity="warning",
        empty=True,
        action_hint=textual_presenters.ask_action_hint(lang=lang),
    )
