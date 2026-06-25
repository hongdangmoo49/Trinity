from __future__ import annotations

from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button, DirectoryTree, Input, Static

from trinity.textual_app.widgets import workspace_picker as workspace_picker_module
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.workspace_picker import (
    CreateMissingDirectoryPrompt,
    FolderNamePrompt,
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


def test_build_preflight_detects_git_worktree_file_branch(tmp_path) -> None:
    worktree = tmp_path / "worktree"
    gitdir = tmp_path / "repo" / ".git" / "worktrees" / "worktree"
    worktree.mkdir()
    gitdir.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: ../repo/.git/worktrees/worktree\n", encoding="utf-8")
    (gitdir / "HEAD").write_text("ref: refs/heads/feature/worktree\n", encoding="utf-8")

    preflight = build_preflight(worktree, WorkflowNexusSnapshot())

    assert preflight.git_repo is True
    assert preflight.branch == "feature/worktree"


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


def test_workspace_preflight_render_uses_korean_labels(tmp_path) -> None:
    preflight = build_preflight(tmp_path / "new-app", WorkflowNexusSnapshot())

    rendered = preflight.render(lang="ko")

    assert f"경로: {tmp_path / 'new-app'}" in rendered
    assert "존재: False" in rendered
    assert "생성 가능: True" in rendered
    assert "변경사항: 알 수 없음" in rendered
    assert "프로바이더 준비: 현재 세션 스냅샷" in rendered
    assert "작업 패키지: 0" in rendered


def test_workspace_preflight_render_localizes_unknown_branch(tmp_path) -> None:
    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot())
    preflight = workspace_picker_module.WorkspacePreflight(
        path=preflight.path,
        exists=preflight.exists,
        is_dir=preflight.is_dir,
        writable=preflight.writable,
        git_repo=True,
        branch="unknown",
        package_count=preflight.package_count,
        creatable=preflight.creatable,
    )

    assert "Branch: unknown" in preflight.render()
    assert "브랜치: 알 수 없음" in preflight.render(lang="ko")


def test_build_preflight_supports_nested_missing_directories(tmp_path) -> None:
    preflight = build_preflight(tmp_path / "new-app" / "src", WorkflowNexusSnapshot())

    assert preflight.can_create is True


def test_path_creation_supported_cleans_up_probe_directory(tmp_path) -> None:
    target = tmp_path / "new-app"

    assert workspace_picker_module._path_creation_supported(target) is True
    assert list(tmp_path.glob(".trinity-preflight-*")) == []


def test_path_creation_supported_returns_false_when_probe_is_denied(
    tmp_path,
    monkeypatch,
) -> None:
    def deny_temp_directory(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(
        workspace_picker_module.tempfile,
        "TemporaryDirectory",
        deny_temp_directory,
    )

    assert (
        workspace_picker_module._path_creation_supported(tmp_path / "new-app") is False
    )


def test_build_preflight_does_not_force_creatable_when_creation_unsupported(
    tmp_path,
    monkeypatch,
) -> None:
    target = tmp_path / "new-app"
    monkeypatch.setattr(
        workspace_picker_module,
        "_path_creation_supported",
        lambda path: False,
    )

    preflight = build_preflight(
        target,
        WorkflowNexusSnapshot(),
        creatable=True,
    )

    assert preflight.exists is False
    assert preflight.creatable is False
    assert preflight.can_create is False


def test_default_workspace_tree_root_uses_control_repo_parent(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"

    assert default_workspace_tree_root(control_repo) == tmp_path


@pytest.mark.asyncio
async def test_workspace_picker_reuses_composed_fixed_widgets(
    tmp_path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "Trinity"
    selected_workspace = tmp_path / "customer-app"
    next_workspace = tmp_path / "next-app"
    control_repo.mkdir()
    selected_workspace.mkdir()
    next_workspace.mkdir()

    picker = WorkspacePicker(
        candidate=control_repo,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
    )
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause(0.25)
        query_calls: list[str] = []
        original_query_one = picker.query_one
        fixed_selectors = {
            "#workspace-path-input",
            "#workspace-tree-pane",
            "#workspace-directory-tree-placeholder",
            "#workspace-directory-tree",
            "#workspace-preflight",
            "#workspace-picker-status",
        }

        def counted_query_one(selector, *args, **kwargs):
            if selector in fixed_selectors:
                query_calls.append(selector)
            return original_query_one(selector, *args, **kwargs)

        monkeypatch.setattr(picker, "query_one", counted_query_one)

        picker._update_preflight(next_workspace)
        picker._set_status("Ready")
        picker._on_folder_name_submitted("created-cache")
        await pilot.pause()

        assert query_calls == []


@pytest.mark.asyncio
async def test_workspace_picker_rebinds_status_key_after_recompose(tmp_path) -> None:
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

        picker._set_status("Ready")
        await pilot.pause()
        status = picker.query_one("#workspace-picker-status", Static)
        assert "Ready" in str(status.content)

        picker.refresh(recompose=True)
        await pilot.pause()

        status = picker.query_one("#workspace-picker-status", Static)
        assert str(status.content) == ""

        picker._set_status("Ready")
        await pilot.pause()

        status = picker.query_one("#workspace-picker-status", Static)
        assert "Ready" in str(status.content)


@pytest.mark.asyncio
async def test_workspace_picker_uses_korean_labels(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"
    selected_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    selected_workspace.mkdir()

    picker = WorkspacePicker(
        candidate=selected_workspace,
        snapshot=WorkflowNexusSnapshot(work_packages=["WP-001 codex: UI"]),
        cwd=control_repo,
        tree_root=tmp_path,
        lang="ko",
    )
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause(0.25)

        assert str(picker.query_one("#workspace-picker-title", Static).content) == (
            "실행 전 확인"
        )
        assert picker.query_one("#workspace-path-input", Input).placeholder == (
            "작업 폴더 경로"
        )
        assert str(picker.query_one("#new-workspace-folder", Button).label) == "새 폴더"
        assert str(picker.query_one("#cancel-execute", Button).label) == "취소"
        assert str(picker.query_one("#confirm-execute", Button).label) == "실행 확인"
        assert "경로:" in str(picker.query_one("#workspace-preflight", Static).content)

    select_picker = WorkspacePicker(
        candidate=selected_workspace,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
        intent="select",
        lang="ko",
    )
    assert select_picker._title() == "작업 폴더 선택"
    assert select_picker._confirm_label() == "작업 폴더 사용"


@pytest.mark.asyncio
async def test_workspace_folder_prompts_use_korean_labels(tmp_path) -> None:
    app = WorkspacePickerHarness()

    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(FolderNamePrompt(tmp_path, lang="ko"))
        await pilot.pause()

        assert str(app.screen.query_one("#workspace-create-title", Static).content) == (
            "새 폴더"
        )
        assert str(app.screen.query_one("#workspace-create-copy", Static).content) == (
            f"상위 폴더: {tmp_path}"
        )
        assert app.screen.query_one("#workspace-folder-name", Input).placeholder == (
            "폴더 이름"
        )
        assert str(app.screen.query_one("#cancel-folder-name", Button).label) == "취소"
        assert str(app.screen.query_one("#confirm-folder-name", Button).label) == (
            "폴더 사용"
        )


@pytest.mark.asyncio
async def test_create_missing_directory_prompt_uses_korean_labels() -> None:
    app = WorkspacePickerHarness()

    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(CreateMissingDirectoryPrompt(lang="ko"))
        await pilot.pause()

        assert str(app.screen.query_one("#workspace-create-title", Static).content) == (
            "디렉터리 생성을 활성화할까요?"
        )
        assert str(app.screen.query_one("#workspace-create-copy", Static).content) == (
            "선택한 경로는 현재 생성 가능으로 표시되어 있지 않습니다."
        )
        assert str(app.screen.query_one("#cancel-create-folder", Button).label) == "취소"
        assert str(app.screen.query_one("#enable-create-folder", Button).label) == (
            "활성화"
        )


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
async def test_workspace_picker_skips_unchanged_status_and_preflight_updates(
    tmp_path,
) -> None:
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

        preflight_panel = picker.query_one("#workspace-preflight", Static)
        status = picker.query_one("#workspace-picker-status", Static)
        preflight_updates: list[str] = []
        status_updates: list[str] = []
        original_preflight_update = preflight_panel.update
        original_status_update = status.update

        def counted_preflight_update(content) -> None:
            preflight_updates.append(str(content))
            original_preflight_update(content)

        def counted_status_update(content) -> None:
            status_updates.append(str(content))
            original_status_update(content)

        preflight_panel.update = counted_preflight_update
        status.update = counted_status_update

        picker._update_preflight(control_repo)
        picker._set_status("Ready")
        picker._set_status("Ready")
        await pilot.pause()

        assert preflight_updates == []
        assert status_updates == ["Ready"]


@pytest.mark.asyncio
async def test_workspace_picker_new_folder_blocks_unwritable_base(
    tmp_path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "Trinity"
    control_repo.mkdir()

    picker = WorkspacePicker(
        candidate=control_repo,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
    )
    app = WorkspacePickerHarness()
    monkeypatch.setattr(
        workspace_picker_module,
        "_directory_accepts_child_creation",
        lambda directory: False,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker.action_new_folder()
        await pilot.pause()

        status = picker.query_one("#workspace-picker-status", Static)
        assert "Cannot create folders under" in str(status.content)
        assert isinstance(app.screen, WorkspacePicker)


@pytest.mark.asyncio
async def test_workspace_picker_uses_korean_status_messages(
    tmp_path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "Trinity"
    control_repo.mkdir()

    picker = WorkspacePicker(
        candidate=control_repo,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
        lang="ko",
    )
    app = WorkspacePickerHarness()
    monkeypatch.setattr(
        workspace_picker_module,
        "_directory_accepts_child_creation",
        lambda directory: False,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker.action_new_folder()
        await pilot.pause()

        status = picker.query_one("#workspace-picker-status", Static)
        assert "폴더를 만들 수 없습니다" in str(status.content)

        picker._on_folder_name_submitted("../nope")
        await pilot.pause()

        assert "폴더 이름 하나만 입력하세요." in str(status.content)


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
