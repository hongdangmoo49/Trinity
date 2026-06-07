"""Context modal for current-session Textual slash command output."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Markdown, Static

from trinity.textual_app.snapshot import LocalCommandSnapshot


class ContextCommandModal(ModalScreen[None]):
    """Show the current session context without starting a workflow."""

    DEFAULT_CSS = """
    ContextCommandModal {
        align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, result: LocalCommandSnapshot) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        with Vertical(id="context-command-modal"):
            yield Static("Current Session Context", id="context-command-title")
            yield Markdown(self.result.body, id="context-command-body")
            yield Button("Close", id="close-context-command")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-context-command":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
