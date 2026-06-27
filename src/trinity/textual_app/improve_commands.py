"""Pure helpers for Textual improve command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


ImproveSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ImproveResultPresentation:
    """Presentation flags derived from an improve workflow outcome message."""

    message: str
    severity: ImproveSeverity


@dataclass(frozen=True)
class ImproveCommandPresentation:
    """Prepared local command result for `/improve`."""

    title: str
    body: str
    severity: ImproveSeverity
    table_columns: tuple[str, str]
    table_rows: tuple[tuple[str, str], ...]
    action_hint: str


@dataclass(frozen=True)
class ImproveCommandEffect:
    """UI effect derived from an improve workflow outcome."""

    presentation: ImproveCommandPresentation | None = None


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


def improve_result_command_presentation(
    presentation: ImproveResultPresentation,
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> ImproveCommandPresentation:
    """Return the local command result payload for an improve outcome."""
    return ImproveCommandPresentation(
        title=textual_presenters.improve_title(lang=lang),
        body=textual_presenters.workflow_outcome_message_markdown(
            presentation.message,
            lang=lang,
        ),
        severity=presentation.severity,
        table_columns=textual_presenters.improve_table_columns(lang=lang),
        table_rows=textual_presenters.improve_rows(snapshot, lang=lang),
        action_hint=textual_presenters.improve_action_hint(lang=lang),
    )


def improve_command_effect(
    message: str | None,
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> ImproveCommandEffect:
    """Return the local command effect for an improve workflow outcome."""
    presentation = improve_result_presentation(message)
    if presentation is None:
        return ImproveCommandEffect()
    return ImproveCommandEffect(
        presentation=improve_result_command_presentation(
            presentation,
            snapshot,
            lang=lang,
        )
    )
