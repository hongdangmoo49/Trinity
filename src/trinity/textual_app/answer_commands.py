"""Pure helpers for Textual answer command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.textual_app import presenters as textual_presenters


AnswerSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class AnswerResultPresentation:
    """Presentation flags derived from an answer workflow outcome message."""

    message: str
    severity: AnswerSeverity
    empty: bool


@dataclass(frozen=True)
class AnswerCommandPresentation:
    """Prepared local command result for `/answer`."""

    title: str
    body: str
    severity: AnswerSeverity
    empty: bool = False
    action_hint: str = ""


def answer_result_presentation(
    message: str | None,
) -> AnswerResultPresentation | None:
    """Return local command presentation state for an answer outcome message."""
    if not message:
        return None
    failed = message.startswith("No ")
    return AnswerResultPresentation(
        message=message,
        severity="warning" if failed else "info",
        empty=failed,
    )


def answer_error_command_presentation(
    error: str,
    action_hint: str,
    *,
    lang: str = "en",
) -> AnswerCommandPresentation:
    """Return the local command result payload for an answer parse error."""
    return AnswerCommandPresentation(
        title=textual_presenters.answer_title(lang=lang),
        body=error,
        severity="warning",
        empty=True,
        action_hint=action_hint,
    )


def answer_result_command_presentation(
    presentation: AnswerResultPresentation,
    *,
    lang: str = "en",
) -> AnswerCommandPresentation:
    """Return the local command result payload for an answer outcome."""
    return AnswerCommandPresentation(
        title=textual_presenters.answer_title(lang=lang),
        body=textual_presenters.workflow_outcome_message_markdown(
            presentation.message,
            lang=lang,
        ),
        severity=presentation.severity,
        empty=presentation.empty,
    )
