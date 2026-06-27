from pathlib import Path

from trinity.textual_app.target_workspace import (
    absolute_path,
    default_launch_cwd,
    is_control_repo_target,
    prepare_target_workspace,
    resolve_target_path,
    safe_start_target_workspace,
)


def test_default_launch_cwd_resolves_explicit_launch_dir(tmp_path) -> None:
    launch_dir = tmp_path / "project"
    launch_dir.mkdir()

    assert default_launch_cwd(launch_dir) == launch_dir.resolve()


def test_default_launch_cwd_tolerates_missing_explicit_launch_dir(tmp_path) -> None:
    missing = tmp_path / "missing" / "project"

    resolved = default_launch_cwd(missing)

    assert resolved.is_absolute()
    assert resolved.name == "project"


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


def test_prepare_target_workspace_creates_missing_directory(tmp_path) -> None:
    target = tmp_path / "new-project"

    prepared = prepare_target_workspace(target)

    assert prepared.error is None
    assert prepared.resolved_path == target.resolve()
    assert target.is_dir()


def test_prepare_target_workspace_rejects_existing_file(tmp_path) -> None:
    target = tmp_path / "not-a-directory"
    target.write_text("file", encoding="utf-8")

    prepared = prepare_target_workspace(target)

    assert prepared.error == "not_directory"
    assert prepared.resolved_path is None
    assert prepared.message == str(target)


def test_prepare_target_workspace_reports_os_error(tmp_path, monkeypatch) -> None:
    target = tmp_path / "denied"
    original_mkdir = Path.mkdir

    def fail_mkdir(self, *args, **kwargs):
        if self == target:
            raise OSError("permission denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    prepared = prepare_target_workspace(target)

    assert prepared.error == "os_error"
    assert prepared.resolved_path is None
    assert "permission denied" in prepared.message


def test_absolute_path_tolerates_missing_path(tmp_path) -> None:
    missing = tmp_path / "missing" / "child"

    resolved = absolute_path(missing)

    assert resolved.is_absolute()
    assert resolved.name == "child"
