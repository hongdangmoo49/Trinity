from pathlib import Path

from trinity.textual_app.report_commands import (
    report_open_presentation,
    report_save_presentation,
)
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


def test_report_save_presentation_warns_without_export_data() -> None:
    presentation = report_save_presentation(None)

    assert presentation.title == "Report"
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == "Start or resume a workflow before exporting a report."
    assert presentation.switch_to_report is False


def test_report_save_presentation_renders_saved_path() -> None:
    path = Path("/tmp/report.md")
    path_text = str(path)
    presentation = report_save_presentation(path)

    assert presentation.body == f"Report saved: `{path_text}`"
    assert presentation.result_kind == "path"
    assert presentation.table_columns == ("Item", "Value")
    assert presentation.table_rows == (("Path", path_text),)


def test_report_open_presentation_warns_without_report_data() -> None:
    presentation = report_open_presentation(WorkflowNexusSnapshot())

    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == "Start or resume a workflow before opening a report."
    assert presentation.switch_to_report is False


def test_report_open_presentation_switches_to_report_for_data() -> None:
    snapshot = WorkflowNexusSnapshot(session_id="wf-1", goal="ship it")

    presentation = report_open_presentation(snapshot)

    assert presentation.body == "Report screen opened."
    assert presentation.start_modal is False
    assert presentation.switch_to_report is True
    assert ("Workflow", "wf-1") in presentation.table_rows
