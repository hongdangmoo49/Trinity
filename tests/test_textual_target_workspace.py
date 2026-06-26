from pathlib import Path

from trinity.textual_app.target_workspace import (
    absolute_path,
    is_control_repo_target,
    resolve_target_path,
    safe_start_target_workspace,
)


def test_resolve_target_path_uses_base_dir_for_relative_path(tmp_path) -> None:
    resolved = resolve_target_path("project-a", tmp_path)

    assert resolved == tmp_path / "project-a"


def test_resolve_target_path_keeps_absolute_path(tmp_path) -> None:
    target = tmp_path / "external"

    resolved = resolve_target_path(str(target), tmp_path / "control")

    assert resolved == target


def test_is_control_repo_target_matches_control_repo_and_children(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"

    assert is_control_repo_target(control_repo, control_repo) is True
    assert is_control_repo_target(control_repo / "docs", control_repo) is True


def test_is_control_repo_target_rejects_sibling_workspace(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"

    assert is_control_repo_target(tmp_path / "msu", control_repo) is False


def test_safe_start_target_workspace_skips_empty_or_control_repo(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"

    assert safe_start_target_workspace(None, control_repo) is None
    assert safe_start_target_workspace(control_repo, control_repo) is None
    assert safe_start_target_workspace(control_repo / "docs", control_repo) is None


def test_safe_start_target_workspace_keeps_sibling_workspace(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"
    sibling = tmp_path / "msu"

    assert safe_start_target_workspace(sibling, control_repo) == sibling


def test_absolute_path_tolerates_missing_path(tmp_path) -> None:
    missing = tmp_path / "missing" / "child"

    resolved = absolute_path(missing)

    assert resolved.is_absolute()
    assert resolved.name == "child"
