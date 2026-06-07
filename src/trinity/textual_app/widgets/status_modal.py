"""Status modal for local Textual slash command output."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.textual_app.snapshot import LocalCommandSnapshot


class StatusCommandModal(ModalScreen[None]):
    """Show the current Trinity status without starting a workflow."""

    DEFAULT_CSS = """
    StatusCommandModal {
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
        with Vertical(id="status-command-modal"):
            yield Static("Status", id="status-command-title")
            yield Static(
                "Current local status. No workflow or provider call was started.",
                id="status-command-body",
            )
            yield Static(
                self._status_table_text(),
                id="status-command-table",
                classes="status-readonly-table",
            )
            yield Button("Close", id="close-status-command")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-status-command":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def _status_table_text(self) -> str:
        """Render a non-interactive status table as aligned plain text."""
        rows = [tuple(self.result.table_columns), *self.result.table_rows]
        if not rows:
            return "(no status rows)"
        item_width = max(len(row[0]) for row in rows if row)
        return "\n".join(
            f"{item:<{item_width}}  {value}"
            for item, value, *_ in rows
        )
