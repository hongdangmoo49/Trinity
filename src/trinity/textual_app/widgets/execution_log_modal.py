"""Modal for the full execution activity log."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, RichLog, Static

from trinity.textual_app.i18n import localize_bindings

_LABELS = {
    "ko": {
        "close": "닫기",
        "empty": "실행 로그가 아직 없습니다.",
        "earlier_lines_hidden": "... 이전 로그 {count}줄 숨김",
        "title": "전체 실행 로그",
    },
    "en": {
        "close": "Close",
        "empty": "No execution log yet.",
        "earlier_lines_hidden": "... {count} earlier log lines hidden",
        "title": "Full Execution Log",
    },
}

MAX_RENDERED_LOG_LINES = 500


class ExecutionLogModal(ModalScreen[None]):
    """Show the full execution log without expanding the execution page."""

    DEFAULT_CSS = """
    ExecutionLogModal {
        align: center middle;
    }

    #execution-log-modal {
        width: 88;
        max-width: 96%;
        height: 30;
        max-height: 90%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    #execution-log-modal-title {
        height: 1;
        text-style: bold;
        color: $accent;
    }

    #execution-log-modal-body {
        height: 1fr;
        margin-top: 1;
        border: round $primary;
        padding: 0 1;
    }

    #close-execution-log {
        width: 12;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "close"): ("binding_close", None),
    }

    def __init__(self, lines: list[str], *, lang: str = "en") -> None:
        super().__init__()
        self.lines = list(lines)
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="execution-log-modal"):
            yield Static(self._label("title"), id="execution-log-modal-title")
            yield RichLog(id="execution-log-modal-body", wrap=True, markup=False)
            yield Button(self._label("close"), id="close-execution-log")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#execution-log-modal-body", RichLog)
        for line in self._render_lines():
            log.write(line)

    def _render_lines(self) -> list[str]:
        if not self.lines:
            return [self._label("empty")]
        hidden_count = max(0, len(self.lines) - MAX_RENDERED_LOG_LINES)
        visible = self.lines[-MAX_RENDERED_LOG_LINES:]
        if hidden_count:
            return [
                self._label("earlier_lines_hidden").format(count=hidden_count),
                *visible,
            ]
        return visible

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-execution-log":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def _label(self, key: str) -> str:
        labels = _LABELS.get(self.lang, _LABELS["en"])
        return labels.get(key, _LABELS["en"].get(key, key))
