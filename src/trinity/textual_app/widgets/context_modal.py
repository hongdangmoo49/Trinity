"""Context modal for current-session Textual slash command output."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Markdown, Static

from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import LocalCommandSnapshot


CONTEXT_MODAL_LABELS = {
    "en": {
        "close": "Close",
        "title": "Current Session Context",
    },
    "ko": {
        "close": "닫기",
        "title": "현재 세션 컨텍스트",
    },
}


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

    LOCALIZED_BINDINGS = {
        ("escape", "close"): ("binding_close", None),
    }

    def __init__(self, result: LocalCommandSnapshot, *, lang: str = "en") -> None:
        super().__init__()
        self.result = result
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="context-command-modal"):
            yield Static(self._label("title"), id="context-command-title")
            with VerticalScroll(id="context-command-content"):
                yield Markdown(self.result.body, id="context-command-body")
            yield Button(self._label("close"), id="close-context-command")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-context-command":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def _label(self, key: str) -> str:
        labels = CONTEXT_MODAL_LABELS.get(self.lang, CONTEXT_MODAL_LABELS["en"])
        return labels.get(key, CONTEXT_MODAL_LABELS["en"][key])
