"""Pure helpers for Textual improve command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ImproveSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ImproveResultPresentation:
    """Presentation flags derived from an improve workflow outcome message."""

    message: str
    severity: ImproveSeverity


def improve_result_presentation(
    message: str | None,
) -> ImproveResultPresentation | None:
    """Return local command presentation state for an improve outcome message."""
    if not message:
        return None
    warning = message.startswith("No matching") or "required" in message
    return ImproveResultPresentation(
        message=message,
        severity="warning" if warning else "info",
    )
