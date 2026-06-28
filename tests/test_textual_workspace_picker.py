from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest
from textual.app import App
from textual.css.query import NoMatches
from textual.widgets import Button, DirectoryTree, Input, Static

from trinity.project_intake import build_project_intake, write_project_intake
from trinity.textual_app.widgets import workspace_picker as workspace_picker_module
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.workspace_picker import (
    CreateMissingDirectoryPrompt,
    FolderNamePrompt,
    WorkspacePicker,
    build_preflight,
    build_workspace_picker,
    default_workspace_tree_root,
)


class WorkspacePickerHarness(App[None]):
    pass


def _run_git(tmp_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )


async def _query_static_after_recompose(
    picker: WorkspacePicker,
    pilot,
    selector: str,
) -> Static:
    for _ in range(10):
        await pilot.pause(0.05)
        try:
            return picker.query_one(selector, Static)
        except NoMatches:
            continue
    return picker.query_one(selector, Static)


def test_build_preflight_accepts_existing_writable_directory(tmp_path) -> None:
    snapshot = WorkflowNexusSnapshot(work_packages=["WP-001 codex: UI"])

    preflight = build_preflight(tmp_path, snapshot)

    assert preflight.can_execute is True
    assert preflight.exists is True
    assert preflight.is_dir is True
    assert preflight.package_count == 1
    assert "Workspace intent: Existing directory workspace" in preflight.render()


def test_build_preflight_detects_git_branch(tmp_path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/feature/ui\n", encoding="utf-8")

    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot())

    assert preflight.git_repo is True
    assert preflight.branch == "feature/ui"
    assert "Workspace intent: Existing Git workspace" in preflight.render()


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


def test_build_preflight_reports_clean_git_worktree(tmp_path) -> None:
    _run_git(tmp_path, "init")

    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot())

    assert preflight.git_repo is True
    assert preflight.changed_count == 0
    assert preflight.untracked_count == 0
    assert preflight.requires_execute_ack is False
    assert "Dirty worktree: clean" in preflight.render()
    assert "변경사항: 깨끗함" in preflight.render(lang="ko")


def test_build_preflight_counts_changed_git_entries(tmp_path) -> None:
    _run_git(tmp_path, "init")
    (tmp_path / "tracked.txt").write_text("changed\n", encoding="utf-8")
    _run_git(tmp_path, "add", "tracked.txt")

    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot())

    assert preflight.changed_count == 1
    assert preflight.untracked_count == 0
    assert "Dirty worktree: 1 changed, 0 untracked" in preflight.render()


def test_build_preflight_counts_untracked_git_entries(tmp_path) -> None:
    _run_git(tmp_path, "init")
    (tmp_path / "notes.txt").write_text("new\n", encoding="utf-8")

    preflight = build_preflight(tmp_path, WorkflowNexusSnapshot())

    assert preflight.changed_count == 0
    assert preflight.untracked_count == 1
    assert preflight.requires_execute_ack is True
    assert "Dirty worktree: 0 changed, 1 untracked" in preflight.render()


def test_build_preflight_marks_missing_child_as_creatable(tmp_path) -> None:
    target = tmp_path / "new-app"

    preflight = build_preflight(target, WorkflowNexusSnapshot())

    assert preflight.exists is False
    assert preflight.can_execute is False
    assert preflight.can_create is True
    assert "Creatable: True" in preflight.render()
    assert "Workspace intent: New workspace folder" in preflight.render()
    assert "작업 의도: 새 작업 폴더 생성" in preflight.render(lang="ko")


def test_build_preflight_reports_invalid_path_intent(tmp_path) -> None:
    target = tmp_path / "not-a-directory"
    target.write_text("file\n", encoding="utf-8")

    preflight = build_preflight(target, WorkflowNexusSnapshot())

    assert preflight.exists is True
    assert preflight.is_dir is False
    assert preflight.can_execute is False
    assert "Workspace intent: Invalid path" in preflight.render()


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
    assert "변경사항: Git 저장소 아님" in rendered
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


def test_build_preflight_marks_sparse_existing_project_intake(tmp_path) -> None:
    state = tmp_path / ".trinity"
    target_workspace = tmp_path / "customer-app"
    target_workspace.mkdir()
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target_workspace,
            created_at="2026-06-29T00:00:00Z",
        ),
    )

    preflight = build_preflight(
        target_workspace,
        WorkflowNexusSnapshot(),
        project_intake_state_dir=state,
        today=date(2026, 6, 29),
    )

    assert preflight.intake_safety_warnings == ("sparse_project_intake",)
    assert preflight.requires_execute_ack is True
    assert "Project intake safety: sparse project intake" in preflight.render()
    assert "프로젝트 인테이크 안전: 부족한 프로젝트 인테이크" in preflight.render(
        lang="ko",
    )


def test_build_preflight_marks_stale_existing_project_intake(tmp_path) -> None:
    state = tmp_path / ".trinity"
    target_workspace = tmp_path / "customer-app"
    target_workspace.mkdir()
    (target_workspace / "README.md").write_text("docs\n", encoding="utf-8")
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target_workspace,
            created_at="2026-06-01T00:00:00Z",
        ),
    )

    preflight = build_preflight(
        target_workspace,
        WorkflowNexusSnapshot(),
        project_intake_state_dir=state,
        today=date(2026, 6, 29),
    )

    assert preflight.intake_safety_warnings == ("stale_project_intake",)
    assert preflight.requires_execute_ack is True
    assert "Project intake safety: stale project intake" in preflight.render()


def test_default_workspace_tree_root_uses_control_repo_parent(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"

    assert default_workspace_tree_root(control_repo) == tmp_path


def test_build_workspace_picker_uses_control_repo_defaults(tmp_path) -> None:
    control_repo = tmp_path / "Trinity"
    candidate = tmp_path / "project"
    snapshot = WorkflowNexusSnapshot(session_id="wf-picker")

    picker = build_workspace_picker(
        candidate=candidate,
        snapshot=snapshot,
        control_repo_path=control_repo,
        lang="ko",
        intent="select",
    )

    assert picker.candidate == candidate
    assert picker.snapshot is snapshot
    assert picker.cwd == control_repo
    assert picker.tree_root == tmp_path
    assert picker.intent == "select"
    assert picker.lang == "ko"


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

        status = await _query_static_after_recompose(
            picker,
            pilot,
            "#workspace-picker-status",
        )
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
async def test_workspace_picker_requires_second_confirm_for_dirty_git_execution(
    tmp_path,
) -> None:
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    target_workspace.mkdir()
    _run_git(target_workspace, "init")
    (target_workspace / "notes.txt").write_text("new\n", encoding="utf-8")

    picker = WorkspacePicker(
        candidate=target_workspace,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
    )
    dismissed: list[object] = []
    picker.dismiss = dismissed.append  # type: ignore[method-assign]
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker.action_confirm()
        await pilot.pause()

        status = picker.query_one("#workspace-picker-status", Static)
        assert dismissed == []
        assert "Dirty Git workspace detected" in str(status.content)

        picker.action_confirm()
        await pilot.pause()

        assert dismissed == [picker.preflight]


@pytest.mark.asyncio
async def test_workspace_picker_requires_second_confirm_for_stale_intake(
    tmp_path,
) -> None:
    state = tmp_path / ".trinity"
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    target_workspace.mkdir()
    (target_workspace / "README.md").write_text("docs\n", encoding="utf-8")
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target_workspace,
            created_at="2026-06-01T00:00:00Z",
        ),
    )

    picker = WorkspacePicker(
        candidate=target_workspace,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
        project_intake_state_dir=state,
        today=date(2026, 6, 29),
    )
    dismissed: list[object] = []
    picker.dismiss = dismissed.append  # type: ignore[method-assign]
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker.action_confirm()
        await pilot.pause()

        status = picker.query_one("#workspace-picker-status", Static)
        assert dismissed == []
        assert "stale project intake" in str(status.content)

        picker.action_confirm()
        await pilot.pause()

        assert dismissed == [picker.preflight]


@pytest.mark.asyncio
async def test_workspace_picker_select_mode_skips_dirty_execution_gate(
    tmp_path,
) -> None:
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    target_workspace.mkdir()
    _run_git(target_workspace, "init")
    (target_workspace / "notes.txt").write_text("new\n", encoding="utf-8")

    picker = WorkspacePicker(
        candidate=target_workspace,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
        intent="select",
    )
    dismissed: list[object] = []
    picker.dismiss = dismissed.append  # type: ignore[method-assign]
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker.action_confirm()
        await pilot.pause()

        assert dismissed == [picker.preflight]


@pytest.mark.asyncio
async def test_workspace_picker_select_mode_skips_intake_safety_gate(
    tmp_path,
) -> None:
    state = tmp_path / ".trinity"
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    target_workspace.mkdir()
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target_workspace,
            created_at="2026-06-01T00:00:00Z",
        ),
    )

    picker = WorkspacePicker(
        candidate=target_workspace,
        snapshot=WorkflowNexusSnapshot(),
        cwd=control_repo,
        tree_root=tmp_path,
        intent="select",
        project_intake_state_dir=state,
        today=date(2026, 6, 29),
    )
    dismissed: list[object] = []
    picker.dismiss = dismissed.append  # type: ignore[method-assign]
    app = WorkspacePickerHarness()

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        picker.action_confirm()
        await pilot.pause()

        assert picker.preflight.requires_execute_ack is True
        assert dismissed == [picker.preflight]


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
        assert picker.preflight.created is True
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
