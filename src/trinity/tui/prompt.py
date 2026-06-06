"""Trinity prompt session — prompt_toolkit based interactive input.

Replaces Rich Prompt.ask() with prompt_toolkit for:
- Arrow key history (up/down)
- Cursor movement (left/right, Home/End)
- Tab auto-completion for /commands
- Emacs-style keybindings
- Persistent input history file
"""

from __future__ import annotations

import logging
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.history import FileHistory
from prompt_toolkit.input import DummyInput
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.styles import Style

try:  # Windows services/non-console test runners can lack a screen buffer.
    from prompt_toolkit.output.win32 import NoConsoleScreenBufferError
except Exception:  # pragma: no cover - platform-specific import guard
    NoConsoleScreenBufferError = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Trinity /commands for tab-completion
TRINITY_COMMANDS = [
    "/status",
    "/context",
    "/rounds",
    "/agent",
    "/history",
    "/save",
    "/caveman",
    "/workflow",
    "/questions",
    "/answer",
    "/decisions",
    "/packages",
    "/subtasks",
    "/report",
    "/resume",
    "/execute",
    "/target",
    "/help",
    "/quit",
    "/exit",
    "/q",
]

# prompt_toolkit style mapping
TRINITY_STYLE = Style.from_dict({
    "prompt": "bold green",
    "selector-title": "bold cyan",
    "selector-help": "ansigray",
    "selector-selected": "reverse",
    "selector-recommended": "green",
    "": "",  # default
})

CUSTOM_OPTION_VALUE = "__custom__"


class SlashCommandCompleter(Completer):
    """Complete Trinity commands only when the input begins with slash."""

    def __init__(self, commands: list[str]):
        self.commands = commands

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ):
        text = document.text_before_cursor
        if not text.startswith("/") or any(char.isspace() for char in text):
            return

        normalized = text.lower()
        for command in self.commands:
            if command.lower().startswith(normalized):
                yield Completion(command, start_position=-len(text))


class TrinityPromptSession:
    """prompt_toolkit-backed input session with history and completion.

    Usage:
        session = TrinityPromptSession(state_dir)
        user_input = session.get_input()  # Blocks until Enter
    """

    def __init__(self, state_dir: Path | None = None):
        history_path: str | None = None
        if state_dir:
            history_dir = state_dir / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            history_path = str(history_dir / "input_history")

        self.session: PromptSession[str] = self._create_session(history_path)

    def _create_session(self, history_path: str | None) -> PromptSession[str]:
        """Create a prompt_toolkit session, falling back in non-console runs."""
        kwargs = dict(
            history=FileHistory(history_path) if history_path else None,
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
            completer=SlashCommandCompleter(TRINITY_COMMANDS),
            style=TRINITY_STYLE,
        )
        try:
            return PromptSession(**kwargs)
        except Exception as exc:
            if NoConsoleScreenBufferError is None or not isinstance(
                exc, NoConsoleScreenBufferError
            ):
                raise

            logger.debug(
                "PromptSession could not attach to a Windows console; "
                "falling back to dummy prompt_toolkit I/O."
            )
            return PromptSession(
                input=DummyInput(),
                output=DummyOutput(),
                **kwargs,
            )

    def get_input(self) -> str:
        """Read user input with arrow keys, history, and tab completion.

        Returns:
            The user's input string (stripped).

        Raises:
            KeyboardInterrupt: On Ctrl+C.
            EOFError: On Ctrl+D.
        """
        return self.session.prompt(
            [("class:prompt", "💬 trinity> ")],
        )

    def get_answer_input(self, *, question_id: str) -> str:
        """Read a free-form workflow question answer."""
        return self.session.prompt(
            [("class:prompt", f"❓ {question_id}> ")],
        )

    def get_path_input(self, *, label: str, default: str = "") -> str:
        """Read a filesystem path with an optional default hint."""
        prompt = f"📁 {label}"
        if default:
            prompt += f" [{default}]"
        prompt += "> "
        return self.session.prompt([("class:prompt", prompt)])

    def select_option(
        self,
        *,
        title: str,
        question: str,
        options: list[str],
        recommended_option: str | None = None,
        allow_custom: bool = False,
    ) -> str | None:
        """Select a question option inline using arrow keys."""
        values = self._build_option_values(
            options=options,
            recommended_option=recommended_option,
            allow_custom=allow_custom,
        )
        return self._run_inline_option_selector(
            title=title,
            question=question,
            values=values,
        )

    @staticmethod
    def _build_option_values(
        *,
        options: list[str],
        recommended_option: str | None = None,
        allow_custom: bool = False,
    ) -> list[tuple[str, str]]:
        """Build selectable values for inline option selection."""
        values = []
        for index, option in enumerate(options, 1):
            label = f"{index}. {option}"
            if option == recommended_option:
                label += " (recommended)"
            values.append((str(index), label))
        if allow_custom:
            values.append(
                (CUSTOM_OPTION_VALUE, f"{len(options) + 1}. Custom answer...")
            )
        return values

    def _run_inline_option_selector(
        self,
        *,
        title: str,
        question: str,
        values: list[tuple[str, str]],
    ) -> str | None:
        """Render an inline terminal selector instead of a full-screen dialog."""
        if not values:
            return None

        selected_index = 0
        bindings = KeyBindings()

        def fragments() -> StyleAndTextTuples:
            lines: StyleAndTextTuples = [
                ("class:selector-title", f"{title}\n"),
                ("", f"{question}\n"),
                (
                    "class:selector-help",
                    "Use Up/Down or j/k, Enter to select, Esc to cancel.\n\n",
                ),
            ]
            for index, (_value, label) in enumerate(values):
                selected = index == selected_index
                marker = ">" if selected else " "
                style = "class:selector-selected" if selected else ""
                if "(recommended)" in label and not selected:
                    style = "class:selector-recommended"
                lines.append((style, f"{marker} {label}\n"))
            return lines

        control = FormattedTextControl(fragments)

        @bindings.add("up")
        @bindings.add("k")
        def _move_up(event) -> None:
            nonlocal selected_index
            selected_index = (selected_index - 1) % len(values)
            event.app.invalidate()

        @bindings.add("down")
        @bindings.add("j")
        def _move_down(event) -> None:
            nonlocal selected_index
            selected_index = (selected_index + 1) % len(values)
            event.app.invalidate()

        @bindings.add("enter")
        def _confirm(event) -> None:
            event.app.exit(result=values[selected_index][0])

        @bindings.add("escape")
        @bindings.add("c-c")
        def _cancel(event) -> None:
            event.app.exit(result=None)

        app = Application(
            layout=Layout(HSplit([Window(control, dont_extend_height=True)])),
            key_bindings=bindings,
            style=TRINITY_STYLE,
            full_screen=False,
            erase_when_done=False,
        )
        return app.run()
