"""Pure helpers for Textual report command presentation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.command_parsers import parse_report_args
from trinity.textual_app.report_export import snapshot_has_report_data
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


ReportSeverity = Literal["info", "warning"]
ReportExporter = Callable[[WorkflowNexusSnapshot], Path | None]


@dataclass(frozen=True)
class ReportCommandPresentation:
    """Prepared local command result for `/report`."""

    title: str
    body: str
    severity: ReportSeverity = "info"
    result_kind: str = "markdown"
    empty: bool = False
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()
    start_modal: bool = True
    switch_to_report: bool = False


@dataclass(frozen=True)
class ReportExportNotification:
    """Prepared Textual notification for report export actions."""

    title: str
    message: str
    severity: str = ""


@dataclass(frozen=True)
class ReportExportEffect:
    """Prepared UI effect after attempting a Markdown report export."""

    path: Path | None
    notification: ReportExportNotification

    @property
    def show_export_path(self) -> bool:
        """Return whether the report screen should show the exported path."""
        return self.path is not None


def report_save_presentation(
    path: Path | None,
    *,
    lang: str = "en",
) -> ReportCommandPresentation:
    """Return presentation state for `/report save`."""
    title = textual_presenters.report_title(lang=lang)
    if path is None:
        return ReportCommandPresentation(
            title=title,
            body=textual_presenters.report_no_export_data_markdown(lang=lang),
            severity="warning",
            empty=True,
            action_hint=textual_presenters.report_export_action_hint(lang=lang),
        )
    path_text = str(path)
    return ReportCommandPresentation(
        title=title,
        body=textual_presenters.report_saved_markdown(path_text, lang=lang),
        result_kind="path",
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.report_saved_rows(path_text, lang=lang),
    )


def report_open_presentation(
    snapshot: WorkflowNexusSnapshot,
    *,
    lang: str = "en",
) -> ReportCommandPresentation:
    """Return presentation state for opening the report route."""
    title = textual_presenters.report_title(lang=lang)
    if not snapshot_has_report_data(snapshot):
        return ReportCommandPresentation(
            title=title,
            body=textual_presenters.report_no_open_data_markdown(lang=lang),
            severity="warning",
            empty=True,
            action_hint=textual_presenters.report_open_action_hint(lang=lang),
        )
    return ReportCommandPresentation(
        title=title,
        body=textual_presenters.report_opened_markdown(lang=lang),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=textual_presenters.report_summary_rows(snapshot, lang=lang),
        start_modal=False,
        switch_to_report=True,
    )


def report_command_presentation(
    args: list[str],
    snapshot: WorkflowNexusSnapshot,
    export_report: ReportExporter,
    *,
    lang: str = "en",
) -> ReportCommandPresentation:
    """Return the local command payload for `/report` arguments."""
    parsed = parse_report_args(args)
    if parsed.action == "save":
        return report_save_presentation(export_report(snapshot), lang=lang)
    return report_open_presentation(snapshot, lang=lang)


def report_export_unavailable_notification(
    *,
    lang: str = "en",
) -> ReportExportNotification:
    """Return the warning notification shown when report export has no data."""
    return ReportExportNotification(
        title=textual_presenters.report_export_unavailable_title(lang=lang),
        message=textual_presenters.report_no_export_data_markdown(lang=lang),
        severity="warning",
    )


def report_export_complete_notification(
    path: Path,
    *,
    lang: str = "en",
) -> ReportExportNotification:
    """Return the notification shown after a report is saved."""
    path_text = str(path)
    return ReportExportNotification(
        title=textual_presenters.report_export_complete_title(lang=lang),
        message=textual_presenters.report_saved_notification(path_text, lang=lang),
    )


def report_export_effect(
    path: Path | None,
    *,
    lang: str = "en",
) -> ReportExportEffect:
    """Return the UI effect after attempting a Markdown report export."""
    if path is None:
        return ReportExportEffect(
            path=None,
            notification=report_export_unavailable_notification(lang=lang),
        )
    return ReportExportEffect(
        path=path,
        notification=report_export_complete_notification(path, lang=lang),
    )
