"""Pure helpers for Textual context command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import LocalCommandSnapshot, WorkflowNexusSnapshot


ContextCommandAction = Literal["notify", "record", "modal", "apply_snapshot"]
ContextSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ContextCommandPresentation:
    """Prepared route action for `/context`."""

    action: ContextCommandAction
    command: str
    title: str
    body: str
    severity: ContextSeverity = "info"
    result: LocalCommandSnapshot | None = None


def context_command_presentation(
    command: str,
    snapshot: WorkflowNexusSnapshot,
    *,
    route: str,
    lang: str = "en",
) -> ContextCommandPresentation:
    """Return the presentation action for a Textual `/context` command."""
    title = textual_presenters.context_title(lang=lang)
    body = textual_presenters.snapshot_context_markdown(snapshot, lang=lang)
    if not textual_presenters.snapshot_has_current_context(snapshot):
        if route == "start":
            return ContextCommandPresentation(
                action="notify",
                command=command,
                title=title,
                body=textual_presenters.context_no_current_markdown(lang=lang),
                severity="warning",
            )
        return ContextCommandPresentation(
            action="record",
            command=command,
            title=title,
            body=body,
        )

    result = textual_presenters.local_command_snapshot(command, title, body)
    return ContextCommandPresentation(
        action="modal" if route == "start" else "apply_snapshot",
        command=command,
        title=title,
        body=body,
        result=result,
    )
