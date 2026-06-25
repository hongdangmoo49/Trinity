"""Workflow resume selector modal."""

from __future__ import annotations

import datetime as dt

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.widgets.status_label import display_status_value
from trinity.textual_app.workflow_controller import TextualWorkflowArchiveOption


RESUME_PICKER_LABELS = {
    "en": {
        "cancel": "Cancel",
        "empty": "No saved workflow sessions.",
        "no_goal": "(no goal)",
        "title": "Resume Workflow",
    },
    "ko": {
        "cancel": "취소",
        "empty": "저장된 워크플로우 세션이 없습니다.",
        "no_goal": "(목표 없음)",
        "title": "워크플로우 재개",
    },
}


class ResumeWorkflowPicker(ModalScreen[str | None]):
    """Select an archived workflow to restore."""

    DEFAULT_CSS = """
    ResumeWorkflowPicker {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("up", "cursor_up", "Previous", priority=True),
        Binding("down", "cursor_down", "Next", priority=True),
        Binding("enter", "confirm", "Resume", priority=True),
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
        self.selected_index = 0
        self._archive_buttons: list[Button] = []
        self._archive_list_widget: VerticalScroll | None = None
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        self._archive_buttons = []
        self._archive_list_widget = None
        with Vertical(id="resume-picker"):
            yield Static(self._label("title"), id="resume-picker-title")
            if not self.archives:
                yield Static(self._label("empty"), id="resume-picker-empty")
            else:
                archive_list = VerticalScroll(id="resume-archive-list")
                self._archive_list_widget = archive_list
                with archive_list:
                    for archive in self.archives:
                        classes = "resume-archive-option"
                        if archive.selector == self.archives[self.selected_index].selector:
                            classes += " resume-archive-option-selected"
                        button = Button(
                            self._archive_label(archive),
                            id=f"resume-archive-{archive.selector}",
                            classes=classes,
                        )
                        self._archive_buttons.append(button)
                        yield button
            yield Button(self._label("cancel"), id="cancel-resume-picker")
        yield Footer()

    def on_mount(self) -> None:
        self._focus_selected_archive()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "cancel-resume-picker":
            event.stop()
            self.dismiss(None)
            return
        prefix = "resume-archive-"
        if button_id.startswith(prefix):
            event.stop()
            selector = button_id.removeprefix(prefix)
            self._select_archive(selector)
            self.dismiss(selector)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_cursor_up(self) -> None:
        if not self.archives:
            return
        self.selected_index = (self.selected_index - 1) % len(self.archives)
        self._focus_selected_archive()

    def action_cursor_down(self) -> None:
        if not self.archives:
            return
        self.selected_index = (self.selected_index + 1) % len(self.archives)
        self._focus_selected_archive()

    def action_confirm(self) -> None:
        if not self.archives:
            self.dismiss(None)
            return
        self.dismiss(self.archives[self.selected_index].selector)

    def _select_archive(self, selector: str) -> None:
        for index, archive in enumerate(self.archives):
            if archive.selector == selector:
                self.selected_index = index
                self._focus_selected_archive()
                return

    def _focus_selected_archive(self) -> None:
        buttons = self._archive_buttons_for_focus()
        if not buttons:
            return
        self.selected_index = max(0, min(self.selected_index, len(buttons) - 1))
        for index, button in enumerate(buttons):
            if index == self.selected_index:
                button.add_class("resume-archive-option-selected")
            else:
                button.remove_class("resume-archive-option-selected")
        selected = buttons[self.selected_index]
        selected.focus()
        archive_list = self._archive_list()
        if archive_list is not None:
            archive_list.scroll_to_widget(
                selected,
                animate=False,
                immediate=True,
            )

    def _archive_buttons_for_focus(self) -> list[Button]:
        if self._archive_buttons:
            return self._archive_buttons
        self._archive_buttons = [
            button
            for button in self.query(".resume-archive-option")
            if isinstance(button, Button)
        ]
        return self._archive_buttons

    def _archive_list(self) -> VerticalScroll | None:
        if self._archive_list_widget is not None:
            return self._archive_list_widget
        if not self.archives:
            return None
        self._archive_list_widget = self.query_one(
            "#resume-archive-list",
            VerticalScroll,
        )
        return self._archive_list_widget

    def _archive_label(self, archive: TextualWorkflowArchiveOption) -> str:
        goal = archive.goal.strip() or self._label("no_goal")
        if len(goal) > 64:
            goal = f"{goal[:61]}..."
        updated = dt.datetime.fromtimestamp(
            archive.updated_at,
            tz=dt.UTC,
        ).strftime("%Y-%m-%d %H:%M UTC")
        state = display_status_value(archive.state, lang=self.lang)
        return (
            f"{archive.selector}. {archive.session_id} "
            f"[{state}] {goal} - {updated}"
        )

    def _label(self, key: str) -> str:
        labels = RESUME_PICKER_LABELS.get(self.lang, RESUME_PICKER_LABELS["en"])
        return labels.get(key, RESUME_PICKER_LABELS["en"][key])
