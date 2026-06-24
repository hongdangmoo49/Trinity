"""Confirmation modal for unsafe target workspace selections."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.textual_app.i18n import localize_bindings


TARGET_CONFIRM_LABELS = {
    "en": {
        "body": (
            "The selected target is inside the Trinity control repository. "
            "Execution may write into Trinity itself."
        ),
        "cancel": "Cancel",
        "confirm": "Use Anyway",
        "control_repo": "Control repo",
        "target": "Target",
        "title": "Confirm Control Repo Target",
    },
    "ko": {
        "body": (
            "선택한 대상이 Trinity 제어 저장소 안에 있습니다. "
            "실행 시 Trinity 자체에 파일을 쓸 수 있습니다."
        ),
        "cancel": "취소",
        "confirm": "그래도 사용",
        "control_repo": "제어 저장소",
        "target": "대상",
        "title": "제어 저장소 대상 확인",
    },
}


class TargetWorkspaceConfirmModal(ModalScreen[bool]):
    """Ask before allowing the Trinity control repo as an implementation target."""

    DEFAULT_CSS = """
    TargetWorkspaceConfirmModal {
        align: center middle;
    }

    #target-confirm-modal {
        width: 78;
        max-width: 92%;
        height: auto;
        border: round $warning;
        padding: 1 2;
        background: $surface;
    }

    #target-confirm-title {
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }

    #target-confirm-body {
        margin-bottom: 1;
    }

    #target-confirm-paths {
        color: $text-muted;
        margin-bottom: 1;
    }

    #target-confirm-actions {
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

    def __init__(
        self,
        *,
        target_path: Path,
        control_repo: Path,
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.target_path = target_path
        self.control_repo = control_repo
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="target-confirm-modal"):
            yield Static(self._label("title"), id="target-confirm-title")
            yield Static(
                self._label("body"),
                id="target-confirm-body",
            )
            yield Static(
                f"{self._label('target')}: {self.target_path}\n"
                f"{self._label('control_repo')}: {self.control_repo}",
                id="target-confirm-paths",
            )
            with Horizontal(id="target-confirm-actions"):
                yield Button(self._label("cancel"), id="cancel-target-confirm")
                yield Button(
                    self._label("confirm"),
                    id="confirm-target",
                    variant="warning",
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-target":
            event.stop()
            self.dismiss(True)
        elif event.button.id == "cancel-target-confirm":
            event.stop()
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _label(self, key: str) -> str:
        labels = TARGET_CONFIRM_LABELS.get(self.lang, TARGET_CONFIRM_LABELS["en"])
        return labels.get(key, TARGET_CONFIRM_LABELS["en"][key])
