from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DirectoryTree, Input, Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.workspace_picker import (
    WorkspacePicker,
    build_preflight,
    default_workspace_tree_root,
)


class WorkspacePickerHarness(App[None]):
    pass


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


def test_build_preflight_marks_missing_child_as_creatable(tmp_path) -> None:
    target = tmp_path / "new-app"

    preflight = build_preflight(target, WorkflowNexusSnapshot())

    assert preflight.exists is False
    assert preflight.can_execute is False
    assert preflight.can_create is True
    assert "Creatable: True" in preflight.render()


def test_build_preflight_respects_creatable_override(tmp_path) -> None:
    target = tmp_path / "new-app"

    preflight = build_preflight(
        target,
        WorkflowNexusSnapshot(),
        creatable=False,
    )

    assert preflight.exists is False
    assert preflight.creatable is False
    assert preflight.can_create is False
    assert "Creatable: False" in preflight.render()
    assert "Create supported" not in preflight.render()


def test_build_preflight_supports_nested_missing_directories(tmp_path) -> None:
    preflight = build_preflight(tmp_path / "new-app" / "src", WorkflowNexusSnapshot())

    assert preflight.can_create is True


def test_default_workspace_tree_root_uses_control_repo_parent(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"

    assert default_workspace_tree_root(control_repo) == tmp_path


@pytest.mark.asyncio
async def test_workspace_picker_tree_root_can_differ_from_selected_path(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"
    selected_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    selected_workspace.mkdir()

    picker = WorkspacePicker(
        candidate=selected_workspace,
        snapshot=WorkflowNexusSnapshot(work_packages=["WP-001 codex: UI"]),
        cwd=control_repo,
        tree_root=tmp_path,
    )
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause(0.25)

        tree = app.screen.query_one("#workspace-directory-tree", DirectoryTree)
        path_input = app.screen.query_one("#workspace-path-input", Input)
        preflight_panel = app.screen.query_one("#workspace-preflight", Static)

        assert Path(tree.path) == tmp_path
        assert Path(path_input.value) == selected_workspace
        assert picker.preflight.path == selected_workspace
        assert str(selected_workspace) in str(preflight_panel.content)


@pytest.mark.asyncio
async def test_workspace_picker_tree_selection_updates_input_and_preflight(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"
    tree_root = tmp_path / "workspaces"
    selected_workspace = tree_root / "target-app"
    control_repo.mkdir()
    selected_workspace.mkdir(parents=True)

    picker = WorkspacePicker(
        candidate=control_repo,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tree_root,
    )
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause(0.25)

        tree = app.screen.query_one("#workspace-directory-tree", DirectoryTree)
        tree.post_message(
            DirectoryTree.DirectorySelected(tree.root, selected_workspace)
        )
        await pilot.pause()

        path_input = app.screen.query_one("#workspace-path-input", Input)
        preflight_panel = app.screen.query_one("#workspace-preflight", Static)

        assert Path(path_input.value) == selected_workspace
        assert picker.preflight.path == selected_workspace
        assert picker.preflight.can_execute is True
        assert str(selected_workspace) in str(preflight_panel.content)


@pytest.mark.asyncio
async def test_workspace_picker_confirm_creates_missing_directory(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "new-project"
    control_repo.mkdir()

    picker = WorkspacePicker(
        candidate=target_workspace,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
    )
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker.action_confirm()
        await pilot.pause()

        assert target_workspace.exists()
        assert target_workspace.is_dir()
        assert picker.preflight.path == target_workspace
        assert picker.preflight.can_execute is True


@pytest.mark.asyncio
async def test_workspace_picker_new_folder_flow_targets_tree_root_from_control_repo(
    tmp_path,
) -> None:
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "new-project"
    control_repo.mkdir()

    picker = WorkspacePicker(
        candidate=control_repo,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
    )
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker._on_create_missing_confirmed(True)
        picker._on_folder_name_submitted("new-project")

        await pilot.pause()

        path_input = picker.query_one("#workspace-path-input", Input)
        preflight_panel = picker.query_one("#workspace-preflight", Static)
        status = picker.query_one("#workspace-picker-status", Static)

        assert Path(path_input.value) == target_workspace
        assert picker.create_missing is True
        assert picker.preflight.path == target_workspace
        assert target_workspace.exists()
        assert target_workspace.is_dir()
        assert picker.preflight.can_execute is True
        assert str(target_workspace) in str(preflight_panel.content)
        assert "New folder created" in str(status.content)


@pytest.mark.asyncio
async def test_workspace_picker_rejects_invalid_new_folder_name(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"
    control_repo.mkdir()

    picker = WorkspacePicker(
        candidate=control_repo,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
    )
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker._on_folder_name_submitted("../nope")
        await pilot.pause()

        status = picker.query_one("#workspace-picker-status", Static)
        assert "Enter a single folder name." in str(status.content)
