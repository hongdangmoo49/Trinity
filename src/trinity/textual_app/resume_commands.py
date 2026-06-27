"""Pure helpers for Textual resume command handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


ResumeSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ResumeResultPresentation:
    """Presentation flags derived from a resume workflow outcome message."""

    message: str
    failed: bool
    severity: ResumeSeverity
    empty: bool
    start_modal: bool


@dataclass(frozen=True)
class ResumeCommandPresentation:
    """Prepared local command result for `/resume`."""

    title: str
    body: str
    severity: ResumeSeverity = "info"
    empty: bool = False
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()
    start_modal: bool = True


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


def resume_no_saved_presentation(*, lang: str = "en") -> ResumeCommandPresentation:
    """Return presentation state when there are no saved workflows."""
    return ResumeCommandPresentation(
        title=textual_presenters.resume_title(lang=lang),
        body=textual_presenters.resume_no_saved_markdown(lang=lang),
        empty=True,
        action_hint=textual_presenters.resume_no_saved_action_hint(lang=lang),
    )


def resume_archives_presentation(
    archives: list[object],
    *,
    lang: str = "en",
) -> ResumeCommandPresentation:
    """Return presentation state for saved workflow archive choices."""
    return ResumeCommandPresentation(
        title=textual_presenters.resume_title(lang=lang),
        body=textual_presenters.resume_archives_markdown(archives, lang=lang),
        table_columns=textual_presenters.resume_archive_table_columns(lang=lang),
        table_rows=textual_presenters.resume_archive_rows(archives, lang=lang),
        action_hint=textual_presenters.resume_pick_action_hint(lang=lang),
        start_modal=False,
    )


def resume_cancelled_presentation(*, lang: str = "en") -> ResumeCommandPresentation:
    """Return presentation state when the resume picker is cancelled."""
    return ResumeCommandPresentation(
        title=textual_presenters.resume_title(lang=lang),
        body=textual_presenters.resume_cancelled_markdown(lang=lang),
        empty=True,
        action_hint=textual_presenters.resume_cancel_action_hint(lang=lang),
    )


def resume_result_command_presentation(
    presentation: ResumeResultPresentation,
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> ResumeCommandPresentation:
    """Return the local command result payload for a resume outcome."""
    return ResumeCommandPresentation(
        title=textual_presenters.resume_title(lang=lang),
        body=textual_presenters.workflow_outcome_message_markdown(
            presentation.message,
            lang=lang,
        ),
        severity=presentation.severity,
        empty=presentation.empty,
        table_columns=textual_presenters.resume_result_table_columns(lang=lang),
        table_rows=textual_presenters.resume_result_rows(snapshot, lang=lang),
        start_modal=presentation.start_modal,
    )


def should_continue_resumed_workflow(
    presentation: ResumeResultPresentation | None,
) -> bool:
    """Return whether a resumed workflow should switch back to Nexus."""
    return presentation is None or not presentation.failed
