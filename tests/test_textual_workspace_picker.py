from __future__ import annotations

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.workspace_picker import build_preflight


def test_build_preflight_accepts_existing_writable_directory(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(work_packages=["WP-001 codex: UI"])

    preflight = build_preflight(tmp_path, snapshot)

    assert preflight.can_execute is True
    assert preflight.exists is True
    assert preflight.is_dir is True
    assert preflight.package_count == 1


def test_build_preflight_detects_git_branch(tmp_path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/feature/ui\n", encoding="utf-8")

    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot())

    assert preflight.git_repo is True
    assert preflight.branch == "feature/ui"
