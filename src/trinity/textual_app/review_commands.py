"""Pure helpers for Textual review command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


ReviewSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ReviewResultPresentation:
    """Presentation flags derived from a review workflow outcome message."""

    message: str
    severity: ReviewSeverity


@dataclass(frozen=True)
class ReviewCommandPresentation:
    """Prepared local command result for `/review`."""

    title: str
    body: str
    severity: ReviewSeverity
    table_columns: tuple[str, str]
    table_rows: tuple[tuple[str, str], ...]
    action_hint: str


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


def review_result_command_presentation(
    presentation: ReviewResultPresentation,
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> ReviewCommandPresentation:
    """Return the local command result payload for a review outcome."""
    return ReviewCommandPresentation(
        title=textual_presenters.review_title(lang=lang),
        body=textual_presenters.workflow_outcome_message_markdown(
            presentation.message,
            lang=lang,
        ),
        severity=presentation.severity,
        table_columns=textual_presenters.review_table_columns(lang=lang),
        table_rows=textual_presenters.review_rows(snapshot, lang=lang),
        action_hint=textual_presenters.review_action_hint(lang=lang),
    )
