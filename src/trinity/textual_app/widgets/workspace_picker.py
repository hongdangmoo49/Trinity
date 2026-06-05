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

    @property
    def can_execute(self) -> bool:
        return self.exists and self.is_dir and self.writable

    def render(self) -> str:
        return "\n".join(
            [
                f"Path: {self.path}",
                f"Exists: {self.exists}",
                f"Directory: {self.is_dir}",
                f"Writable: {self.writable}",
                f"Git repo: {self.git_repo}",
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

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_confirm(self) -> None:
        path = Path(self.query_one("#workspace-path-input", Input).value).expanduser()
        self._update_preflight(path)
        if not self.preflight.can_execute:
            self.query_one("#workspace-picker-status", Static).update(
                "Select an existing writable directory."
            )
            return
        self.dismiss(self.preflight)

    def _update_preflight(self, path: Path) -> None:
        self.preflight = build_preflight(path, self.snapshot)
        if self.is_mounted:
            self.query_one("#workspace-preflight", Static).update(self.preflight.render())


def default_workspace_tree_root(control_repo_path: Path) -> Path:
    """Choose a browsing root broad enough to see sibling workspaces."""
    control_repo = control_repo_path.expanduser()
    parent = control_repo.parent
    return parent if parent != control_repo else control_repo


def build_preflight(path: Path, snapshot: WorkflowNexusSnapshot) -> WorkspacePreflight:
    """Build a conservative cross-platform workspace preflight."""
    resolved = path.expanduser()
    exists = resolved.exists()
    is_dir = resolved.is_dir()
    writable = exists and is_dir and os.access(resolved, os.W_OK)
    git_repo = (resolved / ".git").exists()
    return WorkspacePreflight(
        path=resolved,
        exists=exists,
        is_dir=is_dir,
        writable=writable,
        git_repo=git_repo,
        branch=_git_branch(resolved) if git_repo else "(none)",
        package_count=len(snapshot.work_packages),
    )


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
