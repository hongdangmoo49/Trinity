"""Pure helpers for Textual report command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.report_export import snapshot_has_report_data
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


ReportSeverity = Literal["info", "warning"]


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
