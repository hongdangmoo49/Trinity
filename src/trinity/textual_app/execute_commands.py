"""Pure helpers for Textual execute command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.textual_app import presenters as textual_presenters


ExecuteSeverity = Literal["warning"]


@dataclass(frozen=True)
class ExecuteCommandPresentation:
    """Prepared local command result or notification for execute actions."""

    title: str
    body: str
    severity: ExecuteSeverity = "warning"
    empty: bool = True
    action_hint: str = ""


def execute_result_presentation(
    message: str | None,
    *,
    lang: str = "en",
) -> ExecuteCommandPresentation | None:
    """Return presentation state for an execute workflow outcome message."""
    if not message:
        return None
    return ExecuteCommandPresentation(
        title=textual_presenters.execute_title(lang=lang),
        body=textual_presenters.workflow_outcome_message_markdown(message, lang=lang),
        action_hint=textual_presenters.execute_finish_planning_action_hint(lang=lang),
    )


def execute_retry_no_packages_presentation(
    *,
    lang: str = "en",
) -> ExecuteCommandPresentation:
    """Return presentation state when execute retry has no work packages."""
    return ExecuteCommandPresentation(
        title=textual_presenters.execute_retry_title(lang=lang),
        body=textual_presenters.execute_retry_no_packages_markdown(lang=lang),
        action_hint=textual_presenters.execute_retry_no_packages_action_hint(
            lang=lang
        ),
    )
