"""Modal for the full execution activity log."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, RichLog, Static

from trinity.textual_app.i18n import localize_bindings

_LABELS = {
    "ko": {
        "close": "닫기",
        "empty": "실행 로그가 아직 없습니다.",
        "empty_filtered": "일치하는 실행 로그가 없습니다.",
        "earlier_lines_hidden": "... 이전 로그 {count}줄 숨김",
        "match_count": "{visible}/{total}개 결과 표시",
        "no_matches": "0개 결과",
        "search_placeholder": "로그 검색",
        "line_count": "{visible}/{total}줄 표시",
        "title": "전체 실행 로그",
    },
    "en": {
        "close": "Close",
        "empty": "No execution log yet.",
        "empty_filtered": "No matching execution log lines.",
        "earlier_lines_hidden": "... {count} earlier log lines hidden",
        "match_count": "Showing {visible} of {total} matches",
        "no_matches": "0 matches",
        "search_placeholder": "Search log",
        "line_count": "Showing {visible} of {total} lines",
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
        self.filter_query = ""
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="execution-log-modal"):
            yield Static(self._label("title"), id="execution-log-modal-title")
            yield Input(
                placeholder=self._label("search_placeholder"),
                id="execution-log-search",
            )
            yield Static("", id="execution-log-search-status")
            yield RichLog(id="execution-log-modal-body", wrap=True, markup=False)
            yield Button(self._label("close"), id="close-execution-log")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_log()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "execution-log-search":
            return
        self.filter_query = event.value.strip()
        self._refresh_log()

    def _refresh_log(self) -> None:
        self.query_one("#execution-log-search-status", Static).update(
            self._status_text(self.filter_query)
        )
        log = self.query_one("#execution-log-modal-body", RichLog)
        log.clear()
        for line in self._render_lines(self.filter_query):
            log.write(line)

    def _render_lines(self, query: str = "") -> list[str]:
        if not query.strip():
            return self._render_unfiltered_lines()
        source = self._filtered_lines(query)
        if not source:
            return [self._label("empty_filtered")]
        hidden_count = max(0, len(source) - MAX_RENDERED_LOG_LINES)
        visible = source[-MAX_RENDERED_LOG_LINES:]
        if hidden_count:
            return [
                self._label("earlier_lines_hidden").format(count=hidden_count),
                *visible,
            ]
        return visible

    def _render_unfiltered_lines(self) -> list[str]:
        total = len(self.lines)
        if total <= 0:
            return [self._label("empty")]
        hidden_count = max(0, total - MAX_RENDERED_LOG_LINES)
        start = max(0, total - MAX_RENDERED_LOG_LINES)
        visible = [str(self.lines[index]) for index in range(start, total)]
        if hidden_count:
            return [
                self._label("earlier_lines_hidden").format(count=hidden_count),
                *visible,
            ]
        return visible

    def _filtered_lines(self, query: str) -> list[str]:
        needle = query.strip().lower()
        if not needle:
            return list(self.lines)
        return [line for line in self.lines if needle in str(line).lower()]

    def _status_text(self, query: str = "") -> str:
        if query.strip():
            total = len(self._filtered_lines(query))
            visible = min(total, MAX_RENDERED_LOG_LINES)
            if total == 0:
                return self._label("no_matches")
            return self._label("match_count").format(visible=visible, total=total)
        total = len(self.lines)
        visible = min(total, MAX_RENDERED_LOG_LINES)
        return self._label("line_count").format(visible=visible, total=total)

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
