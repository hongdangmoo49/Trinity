"""Status modal for local Textual slash command output."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Static

from trinity.textual_app.snapshot import LocalCommandSnapshot


class StatusCommandModal(ModalScreen[None]):
    """Show the current Trinity status without starting a workflow."""

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, result: LocalCommandSnapshot) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        with Vertical(id="status-command-modal"):
            yield Static("Status", id="status-command-title")
            yield Static(
                "Current local status. No workflow or provider call was started.",
                id="status-command-body",
            )
            table = DataTable(id="status-command-table", show_header=True)
            yield table
            yield Button("Close", id="close-status-command")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#status-command-table", DataTable)
        table.add_columns(*self.result.table_columns)
        table.add_rows(self.result.table_rows)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-status-command":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
