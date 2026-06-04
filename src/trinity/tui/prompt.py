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
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from prompt_toolkit.input import DummyInput
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.shortcuts import radiolist_dialog
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
    "/resume",
    "/execute",
    "/help",
    "/quit",
]

# prompt_toolkit style mapping
TRINITY_STYLE = Style.from_dict({
    "prompt": "bold green",
    "": "",  # default
})


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

    def select_option(
        self,
        *,
        title: str,
        question: str,
        options: list[str],
        recommended_option: str | None = None,
    ) -> str | None:
        """Select a numbered question option using arrow keys."""
        values = []
        for index, option in enumerate(options, 1):
            label = f"{index}. {option}"
            if option == recommended_option:
                label += " (recommended)"
            values.append((str(index), label))

        return radiolist_dialog(
            title=title,
            text=question,
            values=values,
            ok_text="Select",
            cancel_text="Cancel",
        ).run()
