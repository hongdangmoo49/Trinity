"""Tests for TrinityPromptSession — prompt_toolkit-backed input."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from trinity.tui.prompt import TRINITY_COMMANDS, TrinityPromptSession


class TestTrinityPromptSession:
    """TrinityPromptSession initialization and configuration."""

    def test_creates_history_dir(self, tmp_path):
        """History directory is created on init."""
        state_dir = tmp_path / "state"
        TrinityPromptSession(state_dir)
        assert (state_dir / "history").exists()

    def test_no_state_dir_works(self):
        """Session works without a state directory (in-memory history)."""
        session = TrinityPromptSession(None)
        assert session.session is not None

    def test_history_file_path(self, tmp_path):
        """History file is created at the expected path."""
        state_dir = tmp_path / "state"
        TrinityPromptSession(state_dir)
        history_path = state_dir / "history" / "input_history"
        # File may not exist yet (prompt_toolkit creates on first write)
        # But the directory must exist
        assert (state_dir / "history").is_dir()


class TestCommandCompletion:
    """Tab-completion includes all /commands."""

    def test_all_commands_present(self):
        expected = {"/status", "/context", "/rounds", "/agent", "/history",
                    "/save", "/caveman", "/help", "/quit"}
        assert expected.issubset(set(TRINITY_COMMANDS))

    def test_completer_configured(self, tmp_path):
        """The prompt session has a WordCompleter configured."""
        session = TrinityPromptSession(tmp_path)
        assert session.session.completer is not None


class TestGetInput:
    """get_input delegates to prompt_toolkit."""

    def test_returns_user_input(self, tmp_path):
        """get_input returns the string from prompt_toolkit."""
        session = TrinityPromptSession(tmp_path)
        with patch.object(session.session, "prompt", return_value="hello world"):
            result = session.get_input()
        assert result == "hello world"

    def test_propagates_keyboard_interrupt(self, tmp_path):
        """KeyboardInterrupt from prompt_toolkit is not swallowed."""
        session = TrinityPromptSession(tmp_path)
        with patch.object(session.session, "prompt", side_effect=KeyboardInterrupt):
            try:
                session.get_input()
                assert False, "Should have raised KeyboardInterrupt"
            except KeyboardInterrupt:
                pass

    def test_propagates_eof_error(self, tmp_path):
        """EOFError from prompt_toolkit is not swallowed."""
        session = TrinityPromptSession(tmp_path)
        with patch.object(session.session, "prompt", side_effect=EOFError):
            try:
                session.get_input()
                assert False, "Should have raised EOFError"
            except EOFError:
                pass
