"""Pure helpers for Textual review command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReviewSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ReviewResultPresentation:
    """Presentation flags derived from a review workflow outcome message."""

    message: str
    severity: ReviewSeverity


def review_result_presentation(
    message: str | None,
) -> ReviewResultPresentation | None:
    """Return local command presentation state for a review outcome message."""
    if not message:
        return None
    warning = message.startswith("No review") or "not connected" in message
    return ReviewResultPresentation(
        message=message,
        severity="warning" if warning else "info",
    )
