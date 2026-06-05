"""Prompt composer widgets."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static, TextArea

from trinity.tui.prompt import TRINITY_COMMANDS


COMMAND_LIMIT = 6
PASTE_SUMMARY_THRESHOLD = 1_000
COMMAND_DESCRIPTIONS = {
    "/status": "show provider and workflow status",
    "/context": "show shared context summary",
    "/rounds": "show deliberation rounds",
    "/agent": "inspect or focus an agent",
    "/history": "show recent session history",
    "/save": "save current workflow state",
    "/caveman": "toggle concise reasoning mode",
    "/workflow": "show workflow ledger",
    "/questions": "show pending questions",
    "/answer": "answer a pending question",
    "/decisions": "show agreed decisions",
    "/packages": "show work packages",
    "/subtasks": "show decomposed subtasks",
    "/resume": "resume a saved workflow",
    "/execute": "open execution preflight",
    "/target": "set target workspace candidate",
    "/help": "show available commands",
    "/quit": "exit Trinity",
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
        Binding("shift+enter,alt+enter,ctrl+j", "insert_newline", "New line", show=False),
    ]

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
            return
        await super()._on_paste(event)


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

    def __init__(
        self,
        *,
        placeholder: str = "",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.placeholder = placeholder
        self._command_matches: list[str] = []
        self._command_selection = 0
        self._command_window_start = 0
        self._last_slash_query: str | None = None
        self._ignore_next_submit = False
        self._pasted_content: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        yield ComposerTextArea(
            "",
            placeholder=self.placeholder,
            soft_wrap=True,
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
        if not visible_matches and self._slash_query() is not None:
            first = self.query_one("#command-option-0", Static)
            first.update("No matching commands")
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

        for index in range(COMMAND_LIMIT):
            option = self.query_one(f"#command-option-{index}", Static)
            if index >= len(visible_matches):
                option.update("")
                option.display = False
                option.set_class(False, "command-option-selected")
                option.set_class(False, "command-option-empty")
                continue

            command_index = self._command_window_start + index
            command = visible_matches[index]
            description = COMMAND_DESCRIPTIONS.get(command, "")
            label = f"{command:<12} {description}" if description else command
            option.update(label)
            option.display = True
            option.set_class(
                command_index == self._command_selection,
                "command-option-selected",
            )
            option.set_class(False, "command-option-empty")

        hidden_above = self._command_window_start
        visible_end = self._command_window_start + len(visible_matches)
        hidden_below = max(0, len(self._command_matches) - visible_end)
        more = self.query_one("#command-option-more", Static)
        if hidden_above or hidden_below:
            parts: list[str] = []
            if hidden_above:
                parts.append(f"↑ {hidden_above}")
            if hidden_below:
                parts.append(f"↓ {hidden_below}")
            more.update(" / ".join(parts) + " more commands")
            more.display = True
        else:
            more.update("")
            more.display = False

    def _set_command_palette_visible(self, visible: bool) -> None:
        if not self.is_mounted:
            return
        palette = self.query_one("#prompt-command-palette", Vertical)
        palette.display = visible
        self.set_class(visible, "-commands-open")

    def move_command_selection(self, delta: int) -> bool:
        if not self.command_palette_open or not self._command_matches:
            return False
        self._command_selection = (
            self._command_selection + delta
        ) % len(self._command_matches)
        self._ensure_command_selection_visible()
        self._render_command_options()
        return True

    def accept_selected_command(self) -> bool:
        if not self.command_palette_open or not self._command_matches:
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
        placeholder = f"[Pasted Content {len(text)} chars]"
        self._pasted_content.append((placeholder, text))
        return placeholder

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
