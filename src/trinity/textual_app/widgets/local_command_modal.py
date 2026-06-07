"""Generic modal for local Textual slash command output."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Markdown, Static

from trinity.textual_app.snapshot import LocalCommandSnapshot


class LocalCommandModal(ModalScreen[None]):
    """Show a locally handled slash command result on the Start surface."""

    DEFAULT_CSS = """
    LocalCommandModal {
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
        with Vertical(id="local-command-modal"):
            yield Static(self.result.title, id="local-command-title")
            yield Markdown(self.result.body, id="local-command-body")
            if self.result.table_columns and self.result.table_rows:
                yield Static(
                    self._table_text(),
                    id="local-command-table",
                    classes="local-command-readonly-table",
                )
            if self.result.action_hint:
                yield Static(self.result.action_hint, id="local-command-hint")
            yield Button("Close", id="close-local-command")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-local-command":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def _table_text(self) -> str:
        rows = [tuple(self.result.table_columns), *self.result.table_rows]
        if not rows:
            return ""
        column_count = max(len(row) for row in rows)
        widths = [
            max(len(row[index]) if index < len(row) else 0 for row in rows)
            for index in range(column_count)
        ]
        lines: list[str] = []
        for row in rows:
            cells = [
                (row[index] if index < len(row) else "").ljust(widths[index])
                for index in range(column_count)
            ]
            lines.append("  ".join(cells).rstrip())
        return "\n".join(lines)
