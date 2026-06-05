"""Prompt composer widgets."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static, TextArea

from trinity.tui.prompt import TRINITY_COMMANDS


COMMAND_LIMIT = 8
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
        Binding("enter,ctrl+enter", "submit_or_accept", "Send", priority=True),
        Binding("up", "command_palette_up", "Previous command", show=False, priority=True),
        Binding("down", "command_palette_down", "Next command", show=False, priority=True),
        Binding("alt+enter", "insert_newline", "New line", show=False),
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
        self._replace_via_keyboard("\n", start, end)


class PromptComposer(Vertical):
    """Multi-line prompt composer."""

    class Submitted(Message):
        """Posted when the composer should be sent."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    BINDINGS = [
        Binding("enter", "submit", "Send", priority=True),
        Binding("ctrl+enter", "submit", "Send", show=False, priority=True),
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
        self._ignore_next_submit = False

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
            yield Static("", id="command-option-more", classes="command-option command-option-more")

    def on_mount(self) -> None:
        self._refresh_command_palette()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area is self.query_one(ComposerTextArea):
            self._refresh_command_palette()

    @property
    def text(self) -> str:
        return self.query_one(ComposerTextArea).text

    def set_text(self, text: str) -> None:
        self.query_one(ComposerTextArea).load_text(text)
        self._refresh_command_palette()

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
        self.post_message(self.Submitted(self.text))

    def _refresh_command_palette(self) -> None:
        if not self.is_mounted:
            return

        query = self._slash_query()
        if query is None:
            self._command_matches = []
            self._command_selection = 0
            self._render_command_options()
            self._set_command_palette_visible(False)
            return

        self._command_matches = self._matching_commands(query)
        if self._command_matches:
            self._command_selection = min(
                self._command_selection,
                len(self._command_matches) - 1,
                COMMAND_LIMIT - 1,
            )
        else:
            self._command_selection = 0
        self._render_command_options()
        self._set_command_palette_visible(True)

    def _render_command_options(self) -> None:
        if not self.is_mounted:
            return

        visible_matches = self._command_matches[:COMMAND_LIMIT]
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

            command = visible_matches[index]
            description = COMMAND_DESCRIPTIONS.get(command, "")
            label = f"{command:<12} {description}" if description else command
            option.update(label)
            option.display = True
            option.set_class(index == self._command_selection, "command-option-selected")
            option.set_class(False, "command-option-empty")

        hidden_count = len(self._command_matches) - COMMAND_LIMIT
        more = self.query_one("#command-option-more", Static)
        if hidden_count > 0:
            more.update(f"+ {hidden_count} more commands")
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
        visible_count = min(len(self._command_matches), COMMAND_LIMIT)
        self._command_selection = (self._command_selection + delta) % visible_count
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
