"""Workspace picker and execute preflight modal."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DirectoryTree, Footer, Input, Static

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
    create_supported: bool = False

    @property
    def can_execute(self) -> bool:
        return self.exists and self.is_dir and self.writable

    @property
    def can_create(self) -> bool:
        """Return whether the target directory can be created before execution."""
        return not self.exists and self.creatable and self.create_supported

    def render(self) -> str:
        return "\n".join(
            [
                f"Path: {self.path}",
                f"Exists: {self.exists}",
                f"Directory: {self.is_dir}",
                f"Writable: {self.writable}",
                f"Git repo: {self.git_repo}",
                f"Creatable: {self.creatable}",
                f"Create supported: {self.create_supported}",
                f"Branch: {self.branch}",
                "Dirty worktree: unknown",
                "Provider readiness: current session snapshot",
                f"Work packages: {self.package_count}",
            ]
        )


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
            yield Checkbox(
                "Create missing directory",
                value=self.create_missing,
                id="workspace-creatable",
            )
            with Horizontal(id="workspace-picker-body"):
                yield DirectoryTree(self.tree_root, id="workspace-directory-tree")
                yield Static(self.preflight.render(), id="workspace-preflight")
            with Horizontal(id="workspace-picker-actions"):
                yield Button("Cancel", id="cancel-execute")
                yield Button("Confirm Execute", id="confirm-execute", variant="primary")
            yield Static("", id="workspace-picker-status")
        yield Footer()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "workspace-path-input":
            return
        self._update_preflight(Path(event.value).expanduser())

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "workspace-creatable":
            return
        event.stop()
        self.create_missing = bool(event.value)
        self._update_preflight(self._input_path())

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

    def action_cancel(self) -> None:
        self.dismiss(None)

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

    def _show_invalid_preflight(self) -> None:
        if not self.preflight.exists and not self.preflight.creatable:
            message = (
                "Enable Create missing directory or select an existing writable "
                "directory."
            )
        elif not self.preflight.exists and not self.preflight.create_supported:
            message = (
                "Choose a path under a writable existing parent before creating it."
            )
        else:
            message = (
                "Select an existing writable directory or a creatable new path."
            )
        self.query_one("#workspace-picker-status", Static).update(message)


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
        create_supported=create_supported,
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
