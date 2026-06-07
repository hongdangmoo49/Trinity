"""Workflow resume selector modal."""

from __future__ import annotations

import datetime as dt

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.workflow_controller import TextualWorkflowArchiveOption


class ResumeWorkflowPicker(ModalScreen[str | None]):
    """Select an archived workflow to restore."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "cancel"): ("binding_cancel", None),
    }

    def __init__(
        self,
        archives: list[TextualWorkflowArchiveOption],
        *,
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.archives = archives
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="resume-picker"):
            yield Static("Resume Workflow", id="resume-picker-title")
            if not self.archives:
                yield Static("No saved workflow sessions.", id="resume-picker-empty")
            else:
                for archive in self.archives:
                    yield Button(
                        self._archive_label(archive),
                        id=f"resume-archive-{archive.selector}",
                        classes="resume-archive-option",
                    )
            yield Button("Cancel", id="cancel-resume-picker")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "cancel-resume-picker":
            event.stop()
            self.dismiss(None)
            return
        prefix = "resume-archive-"
        if button_id.startswith(prefix):
            event.stop()
            self.dismiss(button_id.removeprefix(prefix))

    def action_cancel(self) -> None:
        self.dismiss(None)

    @staticmethod
    def _archive_label(archive: TextualWorkflowArchiveOption) -> str:
        goal = archive.goal.strip() or "(no goal)"
        if len(goal) > 64:
            goal = f"{goal[:61]}..."
        updated = dt.datetime.fromtimestamp(
            archive.updated_at,
            tz=dt.UTC,
        ).strftime("%Y-%m-%d %H:%M UTC")
        return (
            f"{archive.selector}. {archive.session_id} "
            f"[{archive.state}] {goal} - {updated}"
        )
