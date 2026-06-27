from __future__ import annotations

from trinity.textual_app.report_export import (
    build_report_markdown_export,
    export_report_markdown,
)
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


def test_export_report_markdown_writes_snapshot_report(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="session/with unsafe chars",
        goal="Build *quoted* report",
        decisions=["Ship the export helper"],
    )

    path = export_report_markdown(
        snapshot,
        state_dir=tmp_path,
        lang="en",
    )

    assert path is not None
    assert path.parent == tmp_path / "reports"
    assert path.exists()
    markdown = path.read_text(encoding="utf-8")
    assert "# Deliberation Report" in markdown
    assert "Build \\*quoted\\* report" in markdown
    assert "Ship the export helper" in markdown


def test_build_report_markdown_export_uses_korean_snapshot_labels(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="ko-session",
        goal="프로젝트 분석",
    )

    export = build_report_markdown_export(
        snapshot,
        state_dir=tmp_path,
        lang="ko",
    )

    assert export is not None
    assert export.path.parent == tmp_path / "reports"
    assert "# 워크플로우 리포트" in export.markdown
    assert "**목표**" in export.markdown


def test_export_report_markdown_returns_none_without_report_data(tmp_path) -> None:
    path = export_report_markdown(
        WorkflowNexusSnapshot(),
        state_dir=tmp_path,
    )

    assert path is None
    assert not (tmp_path / "reports").exists()
