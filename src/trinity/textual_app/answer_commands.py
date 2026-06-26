"""Pure helpers for Textual answer command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AnswerSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class AnswerResultPresentation:
    """Presentation flags derived from an answer workflow outcome message."""

    message: str
    severity: AnswerSeverity
    empty: bool


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
