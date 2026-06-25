"""Prompt composer widgets."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static, TextArea

from trinity.tui.prompt import TRINITY_COMMANDS
from trinity.textual_app.i18n import (
    command_description,
    command_palette_text,
    localize_bindings,
)


COMMAND_LIMIT = 6
PASTE_SUMMARY_THRESHOLD = 1_000

_PASTE_PLACEHOLDERS = {
    "en": "[Pasted Content {count} chars]",
    "ko": "[붙여넣은 콘텐츠 {count}자]",
}


class ComposerTextArea(TextArea):
    """TextArea tuned for Trinity prompt submission."""

    BINDINGS = [
        Binding(
            "enter,ctrl+enter,super+enter",
            "submit_or_accept",
            "Send",
            priority=True,
        ),
        Binding("up", "command_palette_up", "Previous command", show=False, priority=True),
        Binding("down", "command_palette_down", "Next command", show=False, priority=True),
        Binding("tab", "accept_command", "Complete command", show=False, priority=True),
        Binding("shift+enter,alt+enter,ctrl+j", "insert_newline", "New line", show=False),
    ]

    LOCALIZED_BINDINGS = {
        ("enter", "submit_or_accept"): ("binding_send", None),
        ("ctrl+enter", "submit_or_accept"): ("binding_send", None),
        ("super+enter", "submit_or_accept"): ("binding_send", None),
        ("up", "command_palette_up"): ("binding_previous_command", None),
        ("down", "command_palette_down"): ("binding_next_command", None),
        ("shift+enter", "insert_newline"): ("binding_new_line", None),
        ("alt+enter", "insert_newline"): ("binding_new_line", None),
        ("ctrl+j", "insert_newline"): ("binding_new_line", None),
    }

    def __init__(self, *args, lang: str = "en", **kwargs) -> None:
        self._configured_placeholder = str(kwargs.get("placeholder", ""))
        super().__init__(*args, **kwargs)
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)
        self._sync_placeholder_visibility()

    def _sync_placeholder_visibility(self) -> None:
        placeholder = (
            self._configured_placeholder
            if not self.has_focus and not self.text
            else ""
        )
        if self.placeholder != placeholder:
            self.placeholder = placeholder

    def on_focus(self, event: events.Focus) -> None:
        self._sync_placeholder_visibility()

    def on_blur(self, event: events.Blur) -> None:
        self._sync_placeholder_visibility()

    def watch_has_focus(self, has_focus: bool) -> None:
        super().watch_has_focus(has_focus)
        self._sync_placeholder_visibility()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area is self:
            self._sync_placeholder_visibility()

    async def _on_key(self, event: events.Key) -> None:
        self._sync_placeholder_visibility()
        await super()._on_key(event)
        self._sync_placeholder_visibility()

    def action_submit_or_accept(self) -> None:
        parent = self.parent
        if isinstance(parent, PromptComposer):
            if parent.accept_selected_command():
                parent.ignore_next_submit()
                return
            parent.action_submit()

    def action_command_palette_up(self) -> None:
        parent = self.parent
        if isinstance(parent, PromptComposer) and parent.move_command_selection(-1):
            return
        self.action_cursor_up()

    def action_command_palette_down(self) -> None:
        parent = self.parent
        if isinstance(parent, PromptComposer) and parent.move_command_selection(1):
            return
        self.action_cursor_down()

    def action_accept_command(self) -> None:
        parent = self.parent
        if isinstance(parent, PromptComposer):
            parent.accept_selected_command(allow_exact=True)

    action_submit = action_submit_or_accept

    def action_insert_newline(self) -> None:
        if self.read_only:
            return
        start, end = self.selection
        if result := self._replace_via_keyboard("\n", start, end):
            self.move_cursor(result.end_location)

    async def _on_paste(self, event: events.Paste) -> None:
        parent = self.parent
        if isinstance(parent, PromptComposer) and parent.should_summarize_paste(event.text):
            event.stop()
            placeholder = parent.register_pasted_content(event.text)
            start, end = self.selection
            if result := self._replace_via_keyboard(placeholder, start, end):
                self.move_cursor(result.end_location)
                self.focus()
            parent._refresh_command_palette()
            self._sync_placeholder_visibility()
            return
        await super()._on_paste(event)
        self._sync_placeholder_visibility()


class PromptComposer(Vertical):
    """Multi-line prompt composer."""

    class Submitted(Message):
        """Posted when the composer should be sent."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    BINDINGS = [
        Binding("enter,ctrl+enter,super+enter", "submit", "Send", priority=True),
        Binding("shift+enter,alt+enter,ctrl+j", "insert_newline", "New line", show=False),
    ]

    LOCALIZED_BINDINGS = {
        ("enter", "submit"): ("binding_send", None),
        ("ctrl+enter", "submit"): ("binding_send", None),
        ("super+enter", "submit"): ("binding_send", None),
        ("shift+enter", "insert_newline"): ("binding_new_line", None),
        ("alt+enter", "insert_newline"): ("binding_new_line", None),
        ("ctrl+j", "insert_newline"): ("binding_new_line", None),
    }

    def __init__(
        self,
        *,
        placeholder: str = "",
        id: str | None = None,
        lang: str = "en",
    ) -> None:
        super().__init__(id=id)
        self.placeholder = placeholder
        self._command_matches: list[str] = []
        self._command_selection = 0
        self._command_window_start = 0
        self._last_slash_query: str | None = None
        self._ignore_next_submit = False
        self._pasted_content: list[tuple[str, str]] = []
        self._command_options_key: tuple[object, ...] | None = None
        self._command_palette_visible_key: bool | None = None
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        yield ComposerTextArea(
            "",
            placeholder=self.placeholder,
            soft_wrap=True,
            lang=self.lang,
            show_line_numbers=False,
            id="prompt-textarea",
        )
        with Vertical(id="prompt-command-palette", classes="composer-command-palette"):
            for index in range(COMMAND_LIMIT):
                yield Static("", id=f"command-option-{index}", classes="command-option")
            yield Static(
                "",
                id="command-option-more",
                classes="command-option command-option-more",
            )

    def on_mount(self) -> None:
        self._refresh_command_palette()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area is self.query_one(ComposerTextArea):
            self._refresh_command_palette()

    @property
    def text(self) -> str:
        return self.query_one(ComposerTextArea).text

    def set_text(self, text: str, *, clear_pastes: bool = True) -> None:
        if clear_pastes:
            self._pasted_content.clear()
        text_area = self.query_one(ComposerTextArea)
        text_area.load_text(text)
        lines = text.split("\n")
        text_area.move_cursor((len(lines) - 1, len(lines[-1])))
        self._refresh_command_palette()

    @property
    def submission_text(self) -> str:
        text = self.text
        for placeholder, content in self._pasted_content:
            text = text.replace(placeholder, content, 1)
        return text

    def clear(self) -> None:
        self.set_text("")

    def focus_text_area(self) -> None:
        self.query_one(ComposerTextArea).focus()

    def action_submit(self) -> None:
        if self._ignore_next_submit:
            self._ignore_next_submit = False
            return
        if self._is_exact_command_input():
            self._set_command_palette_visible(False)
            self.post_message(self.Submitted(self.submission_text))
            return
        if self.accept_selected_command():
            return
        self._set_command_palette_visible(False)
        self.post_message(self.Submitted(self.submission_text))

    def action_insert_newline(self) -> None:
        self.query_one(ComposerTextArea).action_insert_newline()

    def _refresh_command_palette(self) -> None:
        if not self.is_mounted:
            return

        query = self._slash_query()
        if query is None:
            self._command_matches = []
            self._command_selection = 0
            self._command_window_start = 0
            self._last_slash_query = None
            self._render_command_options()
            self._set_command_palette_visible(False)
            return

        if query != self._last_slash_query:
            self._command_selection = 0
            self._command_window_start = 0
            self._last_slash_query = query

        self._command_matches = self._matching_commands(query)
        if self._command_matches:
            self._command_selection = min(
                self._command_selection,
                len(self._command_matches) - 1,
            )
            self._ensure_command_selection_visible()
        else:
            self._command_selection = 0
            self._command_window_start = 0
        self._render_command_options()
        self._set_command_palette_visible(True)

    def _render_command_options(self) -> None:
        if not self.is_mounted:
            return

        visible_matches = self._visible_command_matches()
        slash_active = self._slash_query() is not None
        option_states: list[tuple[str, bool, bool, bool]] = []
        if not visible_matches and slash_active:
            option_states.append(
                (
                    command_palette_text("command_no_matches", self.lang),
                    True,
                    False,
                    True,
                )
            )
            option_states.extend(("", False, False, False) for _ in range(1, COMMAND_LIMIT))
        else:
            for index in range(COMMAND_LIMIT):
                if index >= len(visible_matches):
                    option_states.append(("", False, False, False))
                    continue
                command_index = self._command_window_start + index
                command = visible_matches[index]
                description = command_description(command, self.lang)
                label = f"{command:<12} {description}" if description else command
                option_states.append(
                    (
                        label,
                        True,
                        command_index == self._command_selection,
                        False,
                    )
                )

        hidden_above = self._command_window_start
        visible_end = self._command_window_start + len(visible_matches)
        hidden_below = max(0, len(self._command_matches) - visible_end)
        more_text = ""
        more_display = False
        if hidden_above or hidden_below:
            parts: list[str] = []
            if hidden_above:
                parts.append(f"↑ {hidden_above}")
            if hidden_below:
                parts.append(f"↓ {hidden_below}")
            suffix = command_palette_text("command_more", self.lang)
            more_text = " / ".join(parts) + f" {suffix}"
            more_display = True

        render_key = (tuple(option_states), more_text, more_display)
        if render_key == self._command_options_key:
            return
        self._command_options_key = render_key

        if not visible_matches and slash_active:
            first = self.query_one("#command-option-0", Static)
            first.update(option_states[0][0])
            first.display = True
            first.set_class(True, "command-option-empty")
            first.set_class(False, "command-option-selected")
            for index in range(1, COMMAND_LIMIT):
                option = self.query_one(f"#command-option-{index}", Static)
                option.update("")
                option.display = False
                option.set_class(False, "command-option-selected")
                option.set_class(False, "command-option-empty")
            self.query_one("#command-option-more", Static).display = False
            return

        for index, (label, display, selected, empty) in enumerate(option_states):
            option = self.query_one(f"#command-option-{index}", Static)
            option.update(label)
            option.display = display
            option.set_class(selected, "command-option-selected")
            option.set_class(empty, "command-option-empty")

        more = self.query_one("#command-option-more", Static)
        more.update(more_text)
        more.display = more_display

    def _set_command_palette_visible(self, visible: bool) -> None:
        if not self.is_mounted:
            return
        if visible == self._command_palette_visible_key:
            return
        palette = self.query_one("#prompt-command-palette", Vertical)
        palette.display = visible
        self.set_class(visible, "-commands-open")
        self._command_palette_visible_key = visible

    def move_command_selection(self, delta: int) -> bool:
        if not self.command_palette_open or not self._command_matches:
            return False
        self._command_selection = (
            self._command_selection + delta
        ) % len(self._command_matches)
        self._ensure_command_selection_visible()
        self._render_command_options()
        return True

    def accept_selected_command(self, *, allow_exact: bool = False) -> bool:
        if not self.command_palette_open or not self._command_matches:
            return False
        if not allow_exact and self._is_exact_command_input():
            return False
        command = self._command_matches[self._command_selection]
        self.set_text(f"{command} ")
        self.focus_text_area()
        return True

    def ignore_next_submit(self) -> None:
        self._ignore_next_submit = True

    @staticmethod
    def should_summarize_paste(text: str) -> bool:
        return bool(text) and (len(text) >= PASTE_SUMMARY_THRESHOLD or "\n" in text)

    def register_pasted_content(self, text: str) -> str:
        placeholder = self._pasted_content_placeholder(len(text))
        self._pasted_content.append((placeholder, text))
        return placeholder

    def _pasted_content_placeholder(self, count: int) -> str:
        template = _PASTE_PLACEHOLDERS.get(self.lang, _PASTE_PLACEHOLDERS["en"])
        return template.format(count=count)

    def _visible_command_matches(self) -> list[str]:
        return self._command_matches[
            self._command_window_start : self._command_window_start + COMMAND_LIMIT
        ]

    def _ensure_command_selection_visible(self) -> None:
        if not self._command_matches:
            self._command_window_start = 0
            return

        max_start = max(0, len(self._command_matches) - COMMAND_LIMIT)
        if self._command_selection < self._command_window_start:
            self._command_window_start = self._command_selection
        elif self._command_selection >= self._command_window_start + COMMAND_LIMIT:
            self._command_window_start = self._command_selection - COMMAND_LIMIT + 1
        self._command_window_start = min(max(self._command_window_start, 0), max_start)

    @property
    def command_palette_open(self) -> bool:
        if not self.is_mounted:
            return False
        return bool(self.query_one("#prompt-command-palette", Vertical).display)

    def _slash_query(self) -> str | None:
        text = self.text
        if not text.startswith("/") or any(char.isspace() for char in text):
            return None
        return text.lower()

    @staticmethod
    def _matching_commands(query: str) -> list[str]:
        return [
            command
            for command in TRINITY_COMMANDS
            if command.lower().startswith(query)
        ]

    def _is_exact_command_input(self) -> bool:
        query = self._slash_query()
        if query is None:
            return False
        return any(command.lower() == query for command in TRINITY_COMMANDS)
