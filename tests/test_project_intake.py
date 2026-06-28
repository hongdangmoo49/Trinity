from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from trinity.project_intake import (
    analyze_git_workspace,
    build_project_intake,
    detect_package_managers,
    load_project_intake,
    load_project_intake_markdown,
    project_intake_prompt_block,
    suggest_test_commands,
    write_project_intake,
)


def _run_git(tmp_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_analyze_git_workspace_reports_non_git_path(tmp_path) -> None:
    analysis = analyze_git_workspace(tmp_path)

    assert analysis.git_repo is False
    assert analysis.branch == "(none)"
    assert analysis.dirty_count is None
    assert analysis.untracked_count is None


def test_analyze_git_workspace_counts_dirty_and_untracked_entries(tmp_path) -> None:
    _run_git(tmp_path, "init")
    (tmp_path / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("new\n", encoding="utf-8")
    _run_git(tmp_path, "add", "tracked.txt")

    analysis = analyze_git_workspace(tmp_path)

    assert analysis.git_repo is True
    assert analysis.branch != "(none)"
    assert analysis.dirty_count == 1
    assert analysis.untracked_count == 1


def test_detect_package_managers_and_test_commands(tmp_path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}),
        encoding="utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")

    managers = detect_package_managers(tmp_path)

    assert managers == ("uv", "pnpm")
    assert suggest_test_commands(tmp_path, managers) == (
        "pnpm test",
        "uv run pytest",
    )


def test_build_project_intake_normalizes_metadata(tmp_path) -> None:
    _run_git(tmp_path, "init")
    (tmp_path / "notes.txt").write_text("new\n", encoding="utf-8")

    intake = build_project_intake(
        mode=" Existing ",
        target_workspace=tmp_path,
        notes="Review before write.",
        created_at="2026-06-28T00:00:00Z",
    )

    assert intake.mode == "existing"
    assert intake.target_workspace == tmp_path.resolve()
    assert intake.created_at == "2026-06-28T00:00:00Z"
    assert intake.git_repo is True
    assert intake.dirty_count == 0
    assert intake.untracked_count == 1
    assert intake.notes == "Review before write."


def test_build_project_intake_rejects_unknown_mode(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unsupported project intake mode"):
        build_project_intake(mode="repair", target_workspace=tmp_path)


def test_write_project_intake_writes_json_and_markdown(tmp_path) -> None:
    intake = build_project_intake(
        mode="new",
        target_workspace=tmp_path / "new-app",
        created_at="2026-06-28T00:00:00Z",
    )

    paths = write_project_intake(tmp_path / ".trinity", intake)

    data = json.loads(paths.json_path.read_text(encoding="utf-8"))
    markdown = paths.markdown_path.read_text(encoding="utf-8")
    assert data["mode"] == "new"
    assert data["target_workspace"] == str((tmp_path / "new-app").resolve())
    assert data["git_repo"] is False
    assert paths.json_path.name == "project-intake.json"
    assert paths.markdown_path.name == "project-intake.md"
    assert "# Project Intake" in markdown
    assert "- Mode: new" in markdown
    assert "- Git repo: False" in markdown


def test_load_project_intake_reads_persisted_json(tmp_path) -> None:
    intake = build_project_intake(
        mode="existing",
        target_workspace=tmp_path,
        notes="Use recorded context.",
        created_at="2026-06-28T00:00:00Z",
    )
    paths = write_project_intake(tmp_path / ".trinity", intake)

    loaded = load_project_intake(paths.json_path.parent)

    assert loaded is not None
    assert loaded.mode == "existing"
    assert loaded.target_workspace == tmp_path.resolve()
    assert loaded.created_at == "2026-06-28T00:00:00Z"
    assert loaded.notes == "Use recorded context."


def test_project_intake_prompt_block_loads_and_truncates_markdown(tmp_path) -> None:
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "project-intake.md").write_text(
        "# Project Intake\n\n" + ("x" * 20),
        encoding="utf-8",
    )

    assert load_project_intake_markdown(state, max_chars=10).endswith("[truncated]")
    block = project_intake_prompt_block(state, max_chars=10)
    assert block.startswith("Project Intake Context:\n# Project")
    assert "[truncated]" in block


def test_project_intake_prompt_block_returns_empty_when_missing(tmp_path) -> None:
    assert project_intake_prompt_block(tmp_path / ".trinity") == ""
