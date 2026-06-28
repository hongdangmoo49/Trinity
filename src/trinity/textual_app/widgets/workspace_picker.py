"""Workspace picker and execute preflight modal."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Footer, Input, Static

from trinity.project_intake import (
    ProjectIntake,
    analyze_git_workspace,
    load_project_intake,
)
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.workspace_labels import PROJECT_INTAKE_STALE_AFTER_DAYS


WORKSPACE_PICKER_LABELS = {
    "en": {
        "branch": "Branch",
        "cancel": "Cancel",
        "confirm_execute": "Confirm Execute",
        "could_not_create_directory": "Could not create directory: {error}",
        "creatable": "Creatable",
        "current_session_snapshot": "current session snapshot",
        "directory": "Directory",
        "dirty_worktree": "Dirty worktree",
        "dirty_worktree_clean": "clean",
        "dirty_worktree_summary": "{changed} changed, {untracked} untracked",
        "enable": "Enable",
        "enable_create_copy": "The selected path is not currently marked creatable.",
        "enable_create_title": "Enable directory creation?",
        "enter_single_folder_name": "Enter a single folder name.",
        "exists": "Exists",
        "folder_already_exists": "Folder already exists: {path}",
        "folder_name": "Folder name",
        "git_repo": "Git repo",
        "intent_existing_directory": "Existing directory workspace",
        "intent_existing_git": "Existing Git workspace",
        "intent_invalid": "Invalid path",
        "intent_missing": "Missing path",
        "intent_new_directory": "New workspace folder",
        "invalid_missing_not_creatable": (
            "Enable Create missing directory or select an existing writable directory."
        ),
        "invalid_select_existing": (
            "Select an existing writable directory or a creatable new path."
        ),
        "dirty_execute_warning": (
            "Dirty Git workspace detected. Press Confirm Execute again to execute "
            "anyway, or cancel and plan first."
        ),
        "dirty_execute_reason": "dirty Git workspace",
        "execute_safety_warning": (
            "Execution safety warning: {reasons}. Press Confirm Execute again "
            "to execute anyway, or cancel and plan first."
        ),
        "invalid_writable_parent": (
            "Choose a path under a writable existing parent before creating it."
        ),
        "loading_folders": "Loading folders from {root}...",
        "new_folder": "New Folder",
        "new_folder_created": "New folder created: {path}",
        "none": "(none)",
        "parent": "Parent",
        "path": "Path",
        "path_exists_not_directory": (
            "Path already exists and is not a directory: {path}"
        ),
        "provider_readiness": "Provider readiness",
        "select_workspace_title": "Select Workspace",
        "target_workspace_path": "Target workspace path",
        "not_git_repo": "not a git repo",
        "project_intake_safety": "Project intake safety",
        "project_intake_safety_ok": "ok",
        "sparse_intake_reason": "sparse project intake",
        "stale_intake_reason": "stale project intake",
        "unknown": "unknown",
        "use_folder": "Use Folder",
        "use_workspace": "Use Workspace",
        "work_packages": "Work packages",
        "workspace_intent": "Workspace intent",
        "writable": "Writable",
        "cannot_create_under": "Cannot create folders under: {path}",
        "execute_preflight_title": "Execute Preflight",
    },
    "ko": {
        "branch": "브랜치",
        "cancel": "취소",
        "confirm_execute": "실행 확인",
        "could_not_create_directory": "디렉터리를 만들 수 없습니다: {error}",
        "creatable": "생성 가능",
        "current_session_snapshot": "현재 세션 스냅샷",
        "directory": "디렉터리",
        "dirty_worktree": "변경사항",
        "dirty_worktree_clean": "깨끗함",
        "dirty_worktree_summary": "변경 {changed}개, 추적 안 됨 {untracked}개",
        "enable": "활성화",
        "enable_create_copy": "선택한 경로는 현재 생성 가능으로 표시되어 있지 않습니다.",
        "enable_create_title": "디렉터리 생성을 활성화할까요?",
        "enter_single_folder_name": "폴더 이름 하나만 입력하세요.",
        "exists": "존재",
        "folder_already_exists": "이미 있는 폴더입니다: {path}",
        "folder_name": "폴더 이름",
        "git_repo": "Git 저장소",
        "intent_existing_directory": "기존 디렉터리 작업 폴더",
        "intent_existing_git": "기존 Git 작업 폴더",
        "intent_invalid": "잘못된 경로",
        "intent_missing": "없는 경로",
        "intent_new_directory": "새 작업 폴더 생성",
        "invalid_missing_not_creatable": (
            "누락된 디렉터리 생성을 활성화하거나 기존의 쓰기 가능한 디렉터리를 선택하세요."
        ),
        "invalid_select_existing": (
            "기존의 쓰기 가능한 디렉터리 또는 생성 가능한 새 경로를 선택하세요."
        ),
        "dirty_execute_warning": (
            "변경사항이 있는 Git 작업 폴더입니다. 그대로 실행하려면 실행 확인을 "
            "한 번 더 누르고, 아니면 취소 후 먼저 계획하세요."
        ),
        "dirty_execute_reason": "변경사항이 있는 Git 작업 폴더",
        "execute_safety_warning": (
            "실행 전 확인 필요: {reasons}. 그대로 실행하려면 실행 확인을 한 번 "
            "더 누르고, 아니면 취소 후 먼저 계획하세요."
        ),
        "invalid_writable_parent": (
            "생성하기 전에 쓰기 가능한 기존 상위 경로 아래를 선택하세요."
        ),
        "loading_folders": "폴더를 불러오는 중: {root}...",
        "new_folder": "새 폴더",
        "new_folder_created": "새 폴더를 만들었습니다: {path}",
        "none": "(없음)",
        "parent": "상위 폴더",
        "path": "경로",
        "path_exists_not_directory": "경로가 이미 있고 디렉터리가 아닙니다: {path}",
        "provider_readiness": "프로바이더 준비",
        "select_workspace_title": "작업 폴더 선택",
        "target_workspace_path": "작업 폴더 경로",
        "not_git_repo": "Git 저장소 아님",
        "project_intake_safety": "프로젝트 인테이크 안전",
        "project_intake_safety_ok": "정상",
        "sparse_intake_reason": "부족한 프로젝트 인테이크",
        "stale_intake_reason": "오래된 프로젝트 인테이크",
        "unknown": "알 수 없음",
        "use_folder": "폴더 사용",
        "use_workspace": "작업 폴더 사용",
        "work_packages": "작업 패키지",
        "workspace_intent": "작업 의도",
        "writable": "쓰기 가능",
        "cannot_create_under": "다음 위치 아래에는 폴더를 만들 수 없습니다: {path}",
        "execute_preflight_title": "실행 전 확인",
    },
}


def _label(lang: str, key: str) -> str:
    labels = WORKSPACE_PICKER_LABELS.get(lang, WORKSPACE_PICKER_LABELS["en"])
    return labels.get(key, WORKSPACE_PICKER_LABELS["en"][key])


def _format_label(lang: str, key: str, **values: object) -> str:
    return _label(lang, key).format(**values)


@dataclass(frozen=True)
class WorkspacePreflight:
    """Workspace preflight result shown before execution."""

    path: Path
    exists: bool
    is_dir: bool
    writable: bool
    git_repo: bool
    branch: str
    package_count: int
    creatable: bool = False
    changed_count: int | None = None
    untracked_count: int | None = None
    created: bool = False
    intake_safety_warnings: tuple[str, ...] = ()

    @property
    def can_execute(self) -> bool:
        return self.exists and self.is_dir and self.writable

    @property
    def can_create(self) -> bool:
        """Return whether the target directory can be created before execution."""
        return not self.exists and self.creatable

    @property
    def requires_execute_ack(self) -> bool:
        """Return whether execution should require an explicit second confirm."""
        return self.requires_dirty_execute_ack or bool(self.intake_safety_warnings)

    @property
    def requires_dirty_execute_ack(self) -> bool:
        """Return whether dirty Git state should require a second confirm."""
        if not self.git_repo:
            return False
        changed = self.changed_count or 0
        untracked = self.untracked_count or 0
        return changed > 0 or untracked > 0

    def render(self, *, lang: str = "en") -> str:
        branch = self._branch_label(lang=lang)
        dirty_worktree = self._dirty_worktree_label(lang=lang)
        intake_safety = self._intake_safety_label(lang=lang)
        return "\n".join(
            [
                f"{_label(lang, 'path')}: {self.path}",
                f"{_label(lang, 'workspace_intent')}: {self._workspace_intent_label(lang=lang)}",
                f"{_label(lang, 'exists')}: {self.exists}",
                f"{_label(lang, 'directory')}: {self.is_dir}",
                f"{_label(lang, 'writable')}: {self.writable}",
                f"{_label(lang, 'git_repo')}: {self.git_repo}",
                f"{_label(lang, 'creatable')}: {self.creatable}",
                f"{_label(lang, 'branch')}: {branch}",
                f"{_label(lang, 'dirty_worktree')}: {dirty_worktree}",
                f"{_label(lang, 'project_intake_safety')}: {intake_safety}",
                (
                    f"{_label(lang, 'provider_readiness')}: "
                    f"{_label(lang, 'current_session_snapshot')}"
                ),
                f"{_label(lang, 'work_packages')}: {self.package_count}",
            ]
        )

    def _branch_label(self, *, lang: str = "en") -> str:
        raw = str(self.branch or "").strip()
        if raw == "(none)":
            return _label(lang, "none")
        if not raw or raw.lower() == "unknown":
            return _label(lang, "unknown")
        return raw

    def _workspace_intent_label(self, *, lang: str = "en") -> str:
        if self.exists and not self.is_dir:
            return _label(lang, "intent_invalid")
        if self.exists and self.git_repo:
            return _label(lang, "intent_existing_git")
        if self.exists:
            return _label(lang, "intent_existing_directory")
        if self.creatable:
            return _label(lang, "intent_new_directory")
        return _label(lang, "intent_missing")

    def _dirty_worktree_label(self, *, lang: str = "en") -> str:
        if not self.git_repo:
            return _label(lang, "not_git_repo")
        if self.changed_count is None or self.untracked_count is None:
            return _label(lang, "unknown")
        if self.changed_count == 0 and self.untracked_count == 0:
            return _label(lang, "dirty_worktree_clean")
        return _format_label(
            lang,
            "dirty_worktree_summary",
            changed=self.changed_count,
            untracked=self.untracked_count,
        )

    def _intake_safety_label(self, *, lang: str = "en") -> str:
        if not self.intake_safety_warnings:
            return _label(lang, "project_intake_safety_ok")
        return ", ".join(
            _intake_safety_reason_label(warning, lang=lang)
            for warning in self.intake_safety_warnings
        )


class CreateMissingDirectoryPrompt(ModalScreen[bool]):
    """Ask whether the preflight should enable missing-directory creation."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    LOCALIZED_BINDINGS = {
        ("escape", "cancel"): ("binding_cancel", None),
    }

    def __init__(self, *, lang: str = "en") -> None:
        super().__init__()
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="workspace-create-prompt"):
            yield Static(self._label("enable_create_title"), id="workspace-create-title")
            yield Static(
                self._label("enable_create_copy"),
                id="workspace-create-copy",
            )
            with Horizontal(id="workspace-create-actions"):
                yield Button(self._label("cancel"), id="cancel-create-folder")
                yield Button(
                    self._label("enable"),
                    id="enable-create-folder",
                    variant="primary",
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-create-folder":
            event.stop()
            self.dismiss(False)
        elif event.button.id == "enable-create-folder":
            event.stop()
            self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _label(self, key: str) -> str:
        return _label(self.lang, key)


class FolderNamePrompt(ModalScreen[str | None]):
    """Collect a child folder name for the target workspace."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "submit", "Create"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "cancel"): ("binding_cancel", None),
        ("enter", "submit"): ("binding_create", None),
    }

    def __init__(self, parent: Path, *, lang: str = "en") -> None:
        super().__init__()
        self.folder_parent = parent
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="workspace-create-prompt"):
            yield Static(self._label("new_folder"), id="workspace-create-title")
            yield Static(
                f"{self._label('parent')}: {self.folder_parent}",
                id="workspace-create-copy",
            )
            yield Input(
                placeholder=self._label("folder_name"),
                id="workspace-folder-name",
            )
            with Horizontal(id="workspace-create-actions"):
                yield Button(self._label("cancel"), id="cancel-folder-name")
                yield Button(
                    self._label("use_folder"),
                    id="confirm-folder-name",
                    variant="primary",
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-folder-name":
            event.stop()
            self.dismiss(None)
        elif event.button.id == "confirm-folder-name":
            event.stop()
            self.action_submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "workspace-folder-name":
            return
        event.stop()
        self.action_submit()

    def action_submit(self) -> None:
        self.dismiss(self.query_one("#workspace-folder-name", Input).value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _label(self, key: str) -> str:
        return _label(self.lang, key)


class WorkspacePicker(ModalScreen[WorkspacePreflight | None]):
    """Confirm target workspace and execution preflight."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "confirm", "Execute"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "cancel"): ("binding_cancel", None),
        ("ctrl+enter", "confirm"): ("binding_execute", None),
    }

    def __init__(
        self,
        *,
        candidate: Path | None,
        snapshot: WorkflowNexusSnapshot,
        cwd: Path | None = None,
        tree_root: Path | None = None,
        intent: str = "execute",
        lang: str = "en",
        open_new_folder: bool = False,
        project_intake_state_dir: Path | None = None,
        today: date | None = None,
    ) -> None:
        super().__init__()
        self.candidate = candidate
        self.snapshot = snapshot
        self.cwd = cwd or Path.cwd()
        self.tree_root = tree_root or self.cwd
        self.intent = "select" if intent == "select" else "execute"
        self.lang = lang
        self.open_new_folder = open_new_folder
        self.project_intake_state_dir = project_intake_state_dir
        self.today = today
        self._tree_mounted = False
        localized_bindings = dict(self.LOCALIZED_BINDINGS)
        if self.intent == "select":
            localized_bindings[("ctrl+enter", "confirm")] = ("binding_apply", None)
        localize_bindings(self._bindings, self.lang, localized_bindings)
        self.preflight = build_preflight(
            candidate or self.cwd,
            snapshot,
            project_intake_state_dir=self.project_intake_state_dir,
            today=self.today,
        )
        self.create_missing = self.preflight.creatable
        self._preflight_render_key = self.preflight.render(lang=self.lang)
        self._status_key = ""
        self._path_input_widget: Input | None = None
        self._tree_pane_widget: Vertical | None = None
        self._tree_placeholder_widget: Static | None = None
        self._directory_tree_widget: DirectoryTree | None = None
        self._preflight_widget: Static | None = None
        self._status_widget: Static | None = None
        self._created_workspace_paths: set[Path] = set()
        self._execute_ack_key: tuple[object, ...] | None = None

    def compose(self) -> ComposeResult:
        self._reset_widget_cache()
        self._reset_render_cache()
        with Vertical(id="workspace-picker"):
            yield Static(self._title(), id="workspace-picker-title")
            path_input = Input(
                value=str(self.preflight.path),
                placeholder=self._label("target_workspace_path"),
                id="workspace-path-input",
            )
            self._path_input_widget = path_input
            yield path_input
            with Horizontal(id="workspace-picker-body"):
                tree_pane = Vertical(id="workspace-tree-pane")
                self._tree_pane_widget = tree_pane
                with tree_pane:
                    placeholder = Static(
                        self._format("loading_folders", root=self.tree_root),
                        id="workspace-directory-tree-placeholder",
                    )
                    self._tree_placeholder_widget = placeholder
                    yield placeholder
                preflight_text = self.preflight.render(lang=self.lang)
                preflight = Static(preflight_text, id="workspace-preflight")
                self._preflight_widget = preflight
                self._preflight_render_key = preflight_text
                yield preflight
            with Horizontal(id="workspace-picker-bottom"):
                with Horizontal(id="workspace-tree-actions"):
                    yield Button(self._label("new_folder"), id="new-workspace-folder")
                with Horizontal(id="workspace-picker-actions"):
                    yield Button(self._label("cancel"), id="cancel-execute")
                    yield Button(
                        self._confirm_label(),
                        id="confirm-execute",
                        variant="primary",
                    )
            status = Static("", id="workspace-picker-status")
            self._status_widget = status
            self._status_key = ""
            yield status
        yield Footer()

    def _title(self) -> str:
        if self.intent == "select":
            return self._label("select_workspace_title")
        return self._label("execute_preflight_title")

    def _confirm_label(self) -> str:
        if self.intent == "select":
            return self._label("use_workspace")
        return self._label("confirm_execute")

    def on_mount(self) -> None:
        self.set_timer(0.05, self._mount_directory_tree)
        if self.open_new_folder:
            self.set_timer(0.05, self.action_new_folder)

    def _mount_directory_tree(self) -> None:
        if self._tree_mounted or not self.is_mounted:
            return
        pane = self._tree_pane()
        placeholder = self._tree_placeholder()
        placeholder.remove()
        tree = DirectoryTree(self.tree_root, id="workspace-directory-tree")
        self._directory_tree_widget = tree
        pane.mount(tree)
        self._tree_mounted = True

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "workspace-path-input":
            return
        self._update_preflight(Path(event.value).expanduser())

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        event.stop()
        path = event.path.expanduser()
        self._path_input().value = str(path)
        self._update_preflight(path)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-execute":
            event.stop()
            self.action_cancel()
        elif event.button.id == "confirm-execute":
            event.stop()
            self.action_confirm()
        elif event.button.id == "new-workspace-folder":
            event.stop()
            self.action_new_folder()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_new_folder(self) -> None:
        self._open_folder_name_prompt()

    def _on_create_missing_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        self.create_missing = True
        self._update_preflight(self._input_path())
        if not self.preflight.exists and not self.preflight.can_create:
            self.create_missing = self.preflight.creatable
            self._show_invalid_preflight()
            return
        self._open_folder_name_prompt()

    def _open_folder_name_prompt(self, base: Path | None = None) -> None:
        folder_parent = base or self._folder_creation_base()
        if not _directory_accepts_child_creation(folder_parent):
            self._set_status(self._format("cannot_create_under", path=folder_parent))
            return
        self.app.push_screen(
            FolderNamePrompt(folder_parent, lang=self.lang),
            self._on_folder_name_submitted,
        )

    def _on_folder_name_submitted(self, folder_name: str | None) -> None:
        clean_name = self._clean_folder_name(folder_name or "")
        if not clean_name:
            self._set_status(self._label("enter_single_folder_name"))
            return
        target = self._folder_creation_base() / clean_name
        created = False
        try:
            if target.exists():
                if not target.is_dir():
                    self._set_status(
                        self._format("path_exists_not_directory", path=target)
                    )
                    return
                status = self._format("folder_already_exists", path=target)
            else:
                target.mkdir(parents=True, exist_ok=False)
                created = True
                self._created_workspace_paths.add(target)
                status = self._format("new_folder_created", path=target)
        except OSError as exc:
            self._set_status(self._format("could_not_create_directory", error=exc))
            return

        self._path_input().value = str(target)
        self._update_preflight(target)
        if created:
            self.preflight = replace(self.preflight, created=True)
        self._reload_tree()
        self._set_status(status)

    def action_confirm(self) -> None:
        path = self._input_path()
        created = self.preflight.created and self.preflight.path == path
        self._update_preflight(path)
        if self.preflight.can_create:
            try:
                self.preflight.path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._set_status(self._format("could_not_create_directory", error=exc))
                return
            created = True
            self._created_workspace_paths.add(self.preflight.path)
            self._update_preflight(self.preflight.path)

        if not self.preflight.can_execute:
            self._show_invalid_preflight()
            return
        if self.intent != "select" and self._needs_execute_ack():
            self._execute_ack_key = self._execute_ack_identity()
            self._set_status(self._execute_ack_warning())
            return
        if created:
            self.preflight = replace(self.preflight, created=True)
        self.dismiss(self.preflight)

    def _update_preflight(self, path: Path) -> None:
        self.preflight = build_preflight(
            path,
            self.snapshot,
            creatable=self.create_missing,
            project_intake_state_dir=self.project_intake_state_dir,
            today=self.today,
        )
        if self.preflight.path in self._created_workspace_paths:
            self.preflight = replace(self.preflight, created=True)
        if self._execute_ack_key != self._execute_ack_identity():
            self._execute_ack_key = None
        preflight_text = self.preflight.render(lang=self.lang)
        if self.is_mounted:
            self._set_preflight_text(preflight_text)
        else:
            self._preflight_render_key = preflight_text

    def _needs_execute_ack(self) -> bool:
        if not self.preflight.requires_execute_ack:
            return False
        return self._execute_ack_key != self._execute_ack_identity()

    def _execute_ack_identity(self) -> tuple[object, ...]:
        return (
            self.preflight.path,
            self.preflight.changed_count,
            self.preflight.untracked_count,
            self.preflight.intake_safety_warnings,
        )

    def _execute_ack_warning(self) -> str:
        if (
            self.preflight.requires_dirty_execute_ack
            and not self.preflight.intake_safety_warnings
        ):
            return self._label("dirty_execute_warning")
        reasons: list[str] = []
        if self.preflight.requires_dirty_execute_ack:
            reasons.append(self._label("dirty_execute_reason"))
        reasons.extend(
            _intake_safety_reason_label(warning, lang=self.lang)
            for warning in self.preflight.intake_safety_warnings
        )
        return self._format("execute_safety_warning", reasons=", ".join(reasons))

    def _input_path(self) -> Path:
        path = Path(self._path_input().value).expanduser()
        if path.is_absolute():
            return path
        return self.tree_root / path

    def _folder_creation_base(self) -> Path:
        path = self._input_path()
        if _same_resolved_path(path, self.cwd) and self.tree_root.exists():
            return self.tree_root
        if path.exists() and path.is_dir():
            return path
        return path.parent

    @staticmethod
    def _clean_folder_name(value: str) -> str:
        folder_name = value.strip()
        if not folder_name or folder_name in {".", ".."}:
            return ""
        if "/" in folder_name or "\\" in folder_name:
            return ""
        return folder_name

    def _set_status(self, message: str) -> None:
        if self.is_mounted:
            self._set_status_text(message)

    def _reload_tree(self) -> None:
        if not self.is_mounted:
            return
        if not self._tree_mounted:
            return
        self._directory_tree().reload()

    def _show_invalid_preflight(self) -> None:
        if not self.preflight.exists and not self.preflight.creatable:
            message = self._label("invalid_missing_not_creatable")
        elif (
            not self.preflight.exists
            and not _path_creation_supported(self.preflight.path)
        ):
            message = self._label("invalid_writable_parent")
        else:
            message = self._label("invalid_select_existing")
        self._set_status(message)

    def _set_preflight_text(self, text: str) -> None:
        if text == self._preflight_render_key:
            return
        self._preflight_static().update(text)
        self._preflight_render_key = text

    def _set_status_text(self, message: str) -> None:
        if message == self._status_key:
            return
        self._status_static().update(message)
        self._status_key = message

    def _reset_widget_cache(self) -> None:
        self._path_input_widget = None
        self._tree_pane_widget = None
        self._tree_placeholder_widget = None
        self._directory_tree_widget = None
        self._preflight_widget = None
        self._status_widget = None

    def _reset_render_cache(self) -> None:
        self._preflight_render_key = ""
        self._status_key = ""

    def _path_input(self) -> Input:
        if self._path_input_widget is None:
            self._path_input_widget = self.query_one("#workspace-path-input", Input)
        return self._path_input_widget

    def _tree_pane(self) -> Vertical:
        if self._tree_pane_widget is None:
            self._tree_pane_widget = self.query_one("#workspace-tree-pane", Vertical)
        return self._tree_pane_widget

    def _tree_placeholder(self) -> Static:
        if self._tree_placeholder_widget is None:
            self._tree_placeholder_widget = self.query_one(
                "#workspace-directory-tree-placeholder",
                Static,
            )
        return self._tree_placeholder_widget

    def _directory_tree(self) -> DirectoryTree:
        if self._directory_tree_widget is None:
            self._directory_tree_widget = self.query_one(
                "#workspace-directory-tree",
                DirectoryTree,
            )
        return self._directory_tree_widget

    def _preflight_static(self) -> Static:
        if self._preflight_widget is None:
            self._preflight_widget = self.query_one("#workspace-preflight", Static)
        return self._preflight_widget

    def _status_static(self) -> Static:
        if self._status_widget is None:
            self._status_widget = self.query_one("#workspace-picker-status", Static)
        return self._status_widget

    def _label(self, key: str) -> str:
        return _label(self.lang, key)

    def _format(self, key: str, **values: object) -> str:
        return _format_label(self.lang, key, **values)


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()


def default_workspace_tree_root(control_repo_path: Path) -> Path:
    """Choose a browsing root broad enough to see sibling workspaces."""
    control_repo = control_repo_path.expanduser()
    parent = control_repo.parent
    return parent if parent != control_repo else control_repo


def build_workspace_picker(
    *,
    candidate: Path | None,
    snapshot: WorkflowNexusSnapshot,
    control_repo_path: Path,
    lang: str = "en",
    intent: str = "execute",
    open_new_folder: bool = False,
    project_intake_state_dir: Path | None = None,
    today: date | None = None,
) -> WorkspacePicker:
    """Build a workspace picker with Trinity's default browsing root."""
    return WorkspacePicker(
        candidate=candidate,
        lang=lang,
        snapshot=snapshot,
        cwd=control_repo_path,
        tree_root=default_workspace_tree_root(control_repo_path),
        intent=intent,
        open_new_folder=open_new_folder,
        project_intake_state_dir=project_intake_state_dir,
        today=today,
    )


def build_preflight(
    path: Path,
    snapshot: WorkflowNexusSnapshot,
    *,
    creatable: bool | None = None,
    project_intake_state_dir: Path | None = None,
    today: date | None = None,
) -> WorkspacePreflight:
    """Build a conservative cross-platform workspace preflight."""
    resolved = path.expanduser()
    exists = resolved.exists()
    is_dir = resolved.is_dir()
    writable = exists and is_dir and _directory_accepts_child_creation(resolved)
    create_supported = not exists and _path_creation_supported(resolved)
    create_requested = (
        create_supported if creatable is None else bool(creatable) and create_supported
    )
    git = analyze_git_workspace(resolved)
    return WorkspacePreflight(
        path=resolved,
        exists=exists,
        is_dir=is_dir,
        writable=writable,
        git_repo=git.git_repo,
        branch=git.branch,
        package_count=len(snapshot.work_packages),
        creatable=create_requested,
        changed_count=git.dirty_count,
        untracked_count=git.untracked_count,
        intake_safety_warnings=_project_intake_safety_warnings(
            project_intake_state_dir,
            resolved,
            today=today,
        ),
    )


def _intake_safety_reason_label(warning: str, *, lang: str = "en") -> str:
    if warning == "sparse_project_intake":
        return _label(lang, "sparse_intake_reason")
    if warning == "stale_project_intake":
        return _label(lang, "stale_intake_reason")
    return warning


def _project_intake_safety_warnings(
    state_dir: Path | None,
    target: Path,
    *,
    today: date | None = None,
) -> tuple[str, ...]:
    if state_dir is None:
        return ()
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ()
    if intake is None or intake.mode != "existing":
        return ()
    if not _same_resolved_path(target, intake.target_workspace):
        return ()
    warnings: list[str] = []
    if _project_intake_analysis_is_sparse_for_preflight(intake):
        warnings.append("sparse_project_intake")
    if _project_intake_analysis_stale_days_for_preflight(
        intake,
        today=today,
    ) is not None:
        warnings.append("stale_project_intake")
    return tuple(warnings)


def _project_intake_analysis_is_sparse_for_preflight(
    intake: ProjectIntake,
) -> bool:
    if intake.mode != "existing":
        return False
    return not (intake.test_commands or intake.source_roots or intake.docs_found)


def _project_intake_analysis_stale_days_for_preflight(
    intake: ProjectIntake,
    *,
    today: date | None = None,
) -> int | None:
    if intake.mode != "existing":
        return None
    text = intake.created_at.strip()
    if len(text) < 10:
        return None
    try:
        created_on = date.fromisoformat(text[:10])
    except ValueError:
        return None
    age_days = ((today or date.today()) - created_on).days
    if age_days <= PROJECT_INTAKE_STALE_AFTER_DAYS:
        return None
    return age_days


def _path_creation_supported(path: Path) -> bool:
    """Return whether mkdir(parents=True) has a writable ancestor to start from."""
    current = path
    seen: set[Path] = set()
    while not current.exists():
        if current in seen:
            return False
        seen.add(current)
        parent = current.parent
        if parent == current:
            return False
        current = parent
    return _directory_accepts_child_creation(current)


def _directory_accepts_child_creation(directory: Path) -> bool:
    """Return whether the OS allows creating a child directory here."""
    if not directory.is_dir():
        return False
    try:
        with tempfile.TemporaryDirectory(
            prefix=".trinity-preflight-",
            dir=directory,
        ):
            return True
    except (OSError, ValueError):
        return False
