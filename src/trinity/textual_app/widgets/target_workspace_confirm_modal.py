"""Confirmation modal for unsafe target workspace selections."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static


class TargetWorkspaceConfirmModal(ModalScreen[bool]):
    """Ask before allowing the Trinity control repo as an implementation target."""

    DEFAULT_CSS = """
    TargetWorkspaceConfirmModal {
        align: center middle;
    }

    #target-confirm-modal {
        width: 78;
        max-width: 92%;
        height: auto;
        border: round $warning;
        padding: 1 2;
        background: $surface;
    }

    #target-confirm-title {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }

    #target-confirm-body {
        margin-bottom: 1;
    }

    #target-confirm-paths {
        color: $text-muted;
        margin-bottom: 1;
    }

    #target-confirm-actions {
        align-horizontal: right;
        height: auto;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, *, target_path: Path, control_repo: Path) -> None:
        super().__init__()
        self.target_path = target_path
        self.control_repo = control_repo

    def compose(self) -> ComposeResult:
        with Vertical(id="target-confirm-modal"):
            yield Static("Confirm Control Repo Target", id="target-confirm-title")
            yield Static(
                "The selected target is inside the Trinity control repository. "
                "Execution may write into Trinity itself.",
                id="target-confirm-body",
            )
            yield Static(
                f"Target: {self.target_path}\nControl repo: {self.control_repo}",
                id="target-confirm-paths",
            )
            with Horizontal(id="target-confirm-actions"):
                yield Button("Cancel", id="cancel-target-confirm")
                yield Button("Use Anyway", id="confirm-target", variant="warning")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-target":
            event.stop()
            self.dismiss(True)
        elif event.button.id == "cancel-target-confirm":
            event.stop()
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
