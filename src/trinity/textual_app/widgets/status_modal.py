"""Status modal for local Textual slash command output."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import LocalCommandSnapshot


STATUS_MODAL_LABELS = {
    "en": {
        "body": "Current local status. No workflow or provider call was started.",
        "close": "Close",
        "empty": "(no status rows)",
        "title": "Status",
    },
    "ko": {
        "body": "현재 로컬 상태입니다. 워크플로우나 프로바이더 호출은 시작하지 않았습니다.",
        "close": "닫기",
        "empty": "(상태 행 없음)",
        "title": "상태",
    },
}


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

    LOCALIZED_BINDINGS = {
        ("escape", "close"): ("binding_close", None),
    }

    def __init__(self, result: LocalCommandSnapshot, *, lang: str = "en") -> None:
        super().__init__()
        self.result = result
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="status-command-modal"):
            yield Static(self._label("title"), id="status-command-title")
            yield Static(
                self._label("body"),
                id="status-command-body",
            )
            yield Static(
                self.status_table_text(),
                id="status-command-table",
                classes="status-readonly-table",
            )
            yield Button(self._label("close"), id="close-status-command")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-status-command":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def status_table_text(self) -> str:
        """Render a non-interactive status table as aligned plain text."""
        rows = [tuple(self.result.table_columns), *self.result.table_rows]
        rows = [row for row in rows if row]
        if not rows:
            return self._label("empty")
        item_width = max(len(row[0]) for row in rows)
        return "\n".join(
            f"{item:<{item_width}}  {value}"
            for item, value, *_ in rows
        )

    def _label(self, key: str) -> str:
        labels = STATUS_MODAL_LABELS.get(self.lang, STATUS_MODAL_LABELS["en"])
        return labels.get(key, STATUS_MODAL_LABELS["en"][key])
