"""Workspace picker and execute preflight modal."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Footer, Input, Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot


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

    @property
    def can_execute(self) -> bool:
        return self.exists and self.is_dir and self.writable

    @property
    def can_create(self) -> bool:
        """Return whether the target directory can be created before execution."""
        return (
            not self.exists
            and self.creatable
            and _path_creation_supported(self.path)
        )

    def render(self) -> str:
        return "\n".join(
            [
                f"Path: {self.path}",
                f"Exists: {self.exists}",
                f"Directory: {self.is_dir}",
                f"Writable: {self.writable}",
                f"Git repo: {self.git_repo}",
                f"Creatable: {self.creatable}",
                f"Branch: {self.branch}",
                "Dirty worktree: unknown",
                "Provider readiness: current session snapshot",
                f"Work packages: {self.package_count}",
            ]
        )


class CreateMissingDirectoryPrompt(ModalScreen[bool]):
    """Ask whether the preflight should enable missing-directory creation."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="workspace-create-prompt"):
            yield Static("Enable directory creation?", id="workspace-create-title")
            yield Static(
                "The selected path is not currently marked creatable.",
                id="workspace-create-copy",
            )
            with Horizontal(id="workspace-create-actions"):
                yield Button("Cancel", id="cancel-create-folder")
                yield Button(
                    "Enable",
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


class FolderNamePrompt(ModalScreen[str | None]):
    """Collect a child folder name for the target workspace."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "submit", "Create"),
    ]

    def __init__(self, parent: Path) -> None:
        super().__init__()
        self.folder_parent = parent

    def compose(self) -> ComposeResult:
        with Vertical(id="workspace-create-prompt"):
            yield Static("New Folder", id="workspace-create-title")
            yield Static(f"Parent: {self.folder_parent}", id="workspace-create-copy")
            yield Input(placeholder="Folder name", id="workspace-folder-name")
            with Horizontal(id="workspace-create-actions"):
                yield Button("Cancel", id="cancel-folder-name")
                yield Button("Use Folder", id="confirm-folder-name", variant="primary")
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


class WorkspacePicker(ModalScreen[WorkspacePreflight | None]):
    """Confirm target workspace and execution preflight."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "confirm", "Execute"),
    ]

    def __init__(
        self,
        *,
        candidate: Path | None,
        snapshot: WorkflowNexusSnapshot,
        cwd: Path | None = None,
        tree_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.candidate = candidate
        self.snapshot = snapshot
        self.cwd = cwd or Path.cwd()
        self.tree_root = tree_root or self.cwd
        self.preflight = build_preflight(candidate or self.cwd, snapshot)
        self.create_missing = self.preflight.creatable

    def compose(self) -> ComposeResult:
        with Vertical(id="workspace-picker"):
            yield Static("Execute Preflight", id="workspace-picker-title")
            yield Input(
                value=str(self.preflight.path),
                placeholder="Target workspace path",
                id="workspace-path-input",
            )
            with Horizontal(id="workspace-picker-body"):
                yield DirectoryTree(self.tree_root, id="workspace-directory-tree")
                yield Static(self.preflight.render(), id="workspace-preflight")
            with Horizontal(id="workspace-picker-bottom"):
                with Horizontal(id="workspace-tree-actions"):
                    yield Button("New Folder", id="new-workspace-folder")
                with Horizontal(id="workspace-picker-actions"):
                    yield Button("Cancel", id="cancel-execute")
                    yield Button("Confirm Execute", id="confirm-execute", variant="primary")
            yield Static("", id="workspace-picker-status")
        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "workspace-path-input":
            return
        self._update_preflight(Path(event.value).expanduser())

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        event.stop()
        path = event.path.expanduser()
        self.query_one("#workspace-path-input", Input).value = str(path)
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
        if not self.create_missing:
            self.app.push_screen(
                CreateMissingDirectoryPrompt(),
                self._on_create_missing_confirmed,
            )
            return
        self._open_folder_name_prompt()

    def _on_create_missing_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        self.create_missing = True
        self._update_preflight(self._input_path())
        self._open_folder_name_prompt()

    def _open_folder_name_prompt(self) -> None:
        self.app.push_screen(
            FolderNamePrompt(self._folder_creation_base()),
            self._on_folder_name_submitted,
        )

    def _on_folder_name_submitted(self, folder_name: str | None) -> None:
        clean_name = self._clean_folder_name(folder_name or "")
        if not clean_name:
            self._set_status("Enter a single folder name.")
            return
        target = self._folder_creation_base() / clean_name
        try:
            if target.exists():
                if not target.is_dir():
                    self._set_status(
                        f"Path already exists and is not a directory: {target}"
                    )
                    return
                status = f"Folder already exists: {target}"
            else:
                target.mkdir(parents=True, exist_ok=False)
                status = f"New folder created: {target}"
        except OSError as exc:
            self._set_status(f"Could not create directory: {exc}")
            return

        self.query_one("#workspace-path-input", Input).value = str(target)
        self._update_preflight(target)
        self._reload_tree()
        self._set_status(status)

    def action_confirm(self) -> None:
        path = self._input_path()
        self._update_preflight(path)
        if self.preflight.can_create:
            try:
                self.preflight.path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.query_one("#workspace-picker-status", Static).update(
                    f"Could not create directory: {exc}"
                )
                return
            self._update_preflight(self.preflight.path)

        if not self.preflight.can_execute:
            self._show_invalid_preflight()
            return
        self.dismiss(self.preflight)

    def _update_preflight(self, path: Path) -> None:
        self.preflight = build_preflight(
            path,
            self.snapshot,
            creatable=self.create_missing,
        )
        if self.is_mounted:
            self.query_one("#workspace-preflight", Static).update(self.preflight.render())

    def _input_path(self) -> Path:
        return Path(self.query_one("#workspace-path-input", Input).value).expanduser()

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
            self.query_one("#workspace-picker-status", Static).update(message)

    def _reload_tree(self) -> None:
        if not self.is_mounted:
            return
        tree = self.query_one("#workspace-directory-tree", DirectoryTree)
        tree.reload()

    def _show_invalid_preflight(self) -> None:
        if not self.preflight.exists and not self.preflight.creatable:
            message = (
                "Enable Create missing directory or select an existing writable "
                "directory."
            )
        elif (
            not self.preflight.exists
            and not _path_creation_supported(self.preflight.path)
        ):
            message = (
                "Choose a path under a writable existing parent before creating it."
            )
        else:
            message = (
                "Select an existing writable directory or a creatable new path."
            )
        self.query_one("#workspace-picker-status", Static).update(message)


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


def build_preflight(
    path: Path,
    snapshot: WorkflowNexusSnapshot,
    *,
    creatable: bool | None = None,
) -> WorkspacePreflight:
    """Build a conservative cross-platform workspace preflight."""
    resolved = path.expanduser()
    exists = resolved.exists()
    is_dir = resolved.is_dir()
    writable = exists and is_dir and os.access(resolved, os.W_OK)
    create_supported = not exists and _path_creation_supported(resolved)
    create_requested = create_supported if creatable is None else bool(creatable)
    git_repo = (resolved / ".git").exists()
    return WorkspacePreflight(
        path=resolved,
        exists=exists,
        is_dir=is_dir,
        writable=writable,
        git_repo=git_repo,
        branch=_git_branch(resolved) if git_repo else "(none)",
        package_count=len(snapshot.work_packages),
        creatable=create_requested,
    )


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
    return current.is_dir() and os.access(current, os.W_OK)


def _git_branch(path: Path) -> str:
    head = path / ".git" / "HEAD"
    if not head.exists():
        return "unknown"
    try:
        text = head.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    prefix = "ref: refs/heads/"
    if text.startswith(prefix):
        return text[len(prefix):]
    return text[:12] if text else "unknown"
