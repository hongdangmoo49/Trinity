"""Pure helpers for Textual resume command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ResumeSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ResumeResultPresentation:
    """Presentation flags derived from a resume workflow outcome message."""

    message: str
    failed: bool
    severity: ResumeSeverity
    empty: bool
    start_modal: bool


def resume_result_presentation(
    message: str | None,
) -> ResumeResultPresentation | None:
    """Return local command presentation state for a resume outcome message."""
    if not message:
        return None
    failed = message.startswith("No ")
    return ResumeResultPresentation(
        message=message,
        failed=failed,
        severity="warning" if failed else "info",
        empty=failed,
        start_modal=failed,
    )


def should_continue_resumed_workflow(
    presentation: ResumeResultPresentation | None,
) -> bool:
    """Return whether a resumed workflow should switch back to Nexus."""
    return presentation is None or not presentation.failed
