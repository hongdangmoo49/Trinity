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
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

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
    "/help",
    "/quit",
]

# prompt_toolkit style mapping
TRINITY_STYLE = Style.from_dict({
    "prompt": "bold green",
    "": "",  # default
})


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

        self.session: PromptSession[str] = PromptSession(
            history=FileHistory(history_path) if history_path else None,
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
            completer=WordCompleter(TRINITY_COMMANDS, ignore_case=True),
            style=TRINITY_STYLE,
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
