from pathlib import Path

from trinity.project_intake import build_project_intake, write_project_intake
from trinity.textual_app.project_context_summary import build_project_context_summary


def test_project_context_summary_reports_missing_intake(tmp_path: Path) -> None:
    target = tmp_path / "target"

    summary = build_project_context_summary(tmp_path / ".trinity", target)

    assert summary.project_mode == "not recorded"
    assert summary.items == ("intake: not recorded",)


def test_project_context_summary_reports_existing_project_context(
    tmp_path: Path,
) -> None:
    state = tmp_path / ".trinity"
    target = tmp_path / "target"
    target.mkdir()
    (target / "README.md").write_text("# Target\n", encoding="utf-8")
    (target / "src" / "app").mkdir(parents=True)
    intake = build_project_intake(
        mode="existing",
        target_workspace=target,
        selected_scope="src/app",
        read_first_confirmed=True,
        validation_commands=("pytest",),
    )
    write_project_intake(state, intake)

    summary = build_project_context_summary(state, target)

    assert summary.project_mode == "workspace recorded"
    assert summary.items == (
        "scope: src/app",
        "read: README.md, src",
        "read-first: confirmed",
        "validation: pytest",
    )


def test_project_context_summary_reports_missing_existing_read_anchors(
    tmp_path: Path,
) -> None:
    state = tmp_path / ".trinity"
    target = tmp_path / "target"
    target.mkdir()
    intake = build_project_intake(
        mode="existing",
        target_workspace=target,
        validation_commands=("pytest",),
    )
    write_project_intake(state, intake)

    summary = build_project_context_summary(state, target)

    assert summary.items == (
        "scope: target root",
        "read: missing",
        "read-first: not required",
        "validation: pytest",
    )


def test_project_context_summary_reports_new_project_context(tmp_path: Path) -> None:
    state = tmp_path / ".trinity"
    target = tmp_path / "target"
    target.mkdir()
    intake = build_project_intake(
        mode="new",
        target_workspace=target,
        product_goal="Ship a local TUI",
        project_type="CLI tool",
        starter_profile="Textual TUI",
        target_users="developers",
        success_criteria="Can finish first workflow",
        first_milestone="First smoke",
        validation_commands=("uv run pytest",),
    )
    write_project_intake(state, intake)

    summary = build_project_context_summary(state, target)

    assert summary.project_mode == "workspace brief"
    assert summary.items == (
        "starter: Textual TUI",
        "brief: complete",
        "validation: uv run pytest",
    )


def test_project_context_summary_reports_target_mismatch(tmp_path: Path) -> None:
    state = tmp_path / ".trinity"
    target = tmp_path / "target"
    selected = tmp_path / "selected"
    target.mkdir()
    selected.mkdir()
    intake = build_project_intake(mode="existing", target_workspace=target)
    write_project_intake(state, intake)

    summary = build_project_context_summary(state, selected)

    assert summary.project_mode == "target mismatch"
    assert summary.items == ("intake: target mismatch", "scope: target root")
