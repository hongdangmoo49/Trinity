"""Confirmation modal for Textual quit slash commands."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.textual_app.i18n import localize_bindings


CONFIRM_QUIT_LABELS = {
    "en": {
        "body": "Exit Trinity Textual workbench?",
        "cancel": "Cancel",
        "quit": "Quit",
        "running_body": "A workflow is still running. Exit Trinity Textual workbench?",
        "title": "Quit Trinity",
    },
    "ko": {
        "body": "Trinity 워크벤치를 종료할까요?",
        "cancel": "취소",
        "quit": "종료",
        "running_body": "워크플로우가 아직 실행 중입니다. Trinity 워크벤치를 종료할까요?",
        "title": "Trinity 종료",
    },
}


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

    LOCALIZED_BINDINGS = {
        ("escape", "cancel"): ("binding_cancel", None),
    }

    def __init__(self, *, running: bool = False, lang: str = "en") -> None:
        super().__init__()
        self.running = running
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        body = self._label("body")
        if self.running:
            body = self._label("running_body")
        with Vertical(id="confirm-quit-modal"):
            yield Static(self._label("title"), id="confirm-quit-title")
            yield Static(body, id="confirm-quit-body")
            with Horizontal(id="confirm-quit-actions"):
                yield Button(self._label("cancel"), id="cancel-quit")
                yield Button(self._label("quit"), id="confirm-quit", variant="warning")
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

    def _label(self, key: str) -> str:
        labels = CONFIRM_QUIT_LABELS.get(self.lang, CONFIRM_QUIT_LABELS["en"])
        return labels.get(key, CONFIRM_QUIT_LABELS["en"][key])
