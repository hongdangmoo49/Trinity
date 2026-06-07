"""Confirmation modal for Textual quit slash commands."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static


class ConfirmQuitModal(ModalScreen[bool]):
    """Ask the user to confirm exiting the Textual workbench."""

    DEFAULT_CSS = """
    ConfirmQuitModal {
        align: center middle;
    }

    #confirm-quit-modal {
        width: 64;
        max-width: 90%;
        height: auto;
        border: round $warning;
        padding: 1 2;
        background: $surface;
    }

    #confirm-quit-title {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }

    #confirm-quit-body {
        margin-bottom: 1;
    }

    #confirm-quit-actions {
        align-horizontal: right;
        height: auto;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, *, running: bool = False) -> None:
        super().__init__()
        self.running = running

    def compose(self) -> ComposeResult:
        body = "Exit Trinity Textual workbench?"
        if self.running:
            body = "A workflow is still running. Exit Trinity Textual workbench?"
        with Vertical(id="confirm-quit-modal"):
            yield Static("Quit Trinity", id="confirm-quit-title")
            yield Static(body, id="confirm-quit-body")
            with Horizontal(id="confirm-quit-actions"):
                yield Button("Cancel", id="cancel-quit")
                yield Button("Quit", id="confirm-quit", variant="warning")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-quit":
            event.stop()
            self.dismiss(True)
        elif event.button.id == "cancel-quit":
            event.stop()
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
