"""Tests for TrinityPromptSession — prompt_toolkit-backed input."""

from unittest.mock import patch

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from trinity.tui.prompt import (
    CUSTOM_OPTION_VALUE,
    TRINITY_COMMANDS,
    TrinityPromptSession,
)


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
        # File may not exist yet (prompt_toolkit creates on first write)
        # But the directory must exist
        assert (state_dir / "history").is_dir()


class TestCommandCompletion:
    """Tab-completion includes all /commands."""

    def test_all_commands_present(self):
        expected = {
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
        }
        assert expected.issubset(set(TRINITY_COMMANDS))

    def test_completer_configured(self, tmp_path):
        """The prompt session has a WordCompleter configured."""
        session = TrinityPromptSession(tmp_path)
        assert session.session.completer is not None

    def test_completion_only_appears_for_slash_prefix(self, tmp_path):
        session = TrinityPromptSession(tmp_path)
        completer = session.session.completer

        assert completer is not None
        slash_matches = list(
            completer.get_completions(Document("/sta"), CompleteEvent())
        )
        space_matches = list(
            completer.get_completions(Document(" "), CompleteEvent())
        )
        text_matches = list(
            completer.get_completions(Document("hello /sta"), CompleteEvent())
        )

        assert any(match.text == "/status" for match in slash_matches)
        assert space_matches == []
        assert text_matches == []


class TestGetInput:
    """get_input delegates to prompt_toolkit."""

    def test_returns_user_input(self, tmp_path):
        """get_input returns the string from prompt_toolkit."""
        session = TrinityPromptSession(tmp_path)
        with patch.object(session.session, "prompt", return_value="hello world"):
            result = session.get_input()
        assert result == "hello world"

    def test_returns_question_answer_input(self, tmp_path):
        """get_answer_input uses the workflow question prompt."""
        session = TrinityPromptSession(tmp_path)
        with patch.object(session.session, "prompt", return_value="LI.FI") as prompt:
            result = session.get_answer_input(question_id="q-001")

        assert result == "LI.FI"
        prompt.assert_called_once()

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

    def test_select_option_runs_inline_selector(self, tmp_path):
        """select_option delegates to the inline terminal selector."""
        session = TrinityPromptSession(tmp_path)
        with patch.object(
            session,
            "_run_inline_option_selector",
            return_value="2",
        ) as selector:
            result = session.select_option(
                title="q-001",
                question="Which API?",
                options=["LI.FI", "Socket"],
                recommended_option="Socket",
            )

        assert result == "2"
        selector.assert_called_once_with(
            title="q-001",
            question="Which API?",
            values=[("1", "1. LI.FI"), ("2", "2. Socket (recommended)")],
        )

    def test_select_option_can_add_custom_answer_choice(self, tmp_path):
        """select_option can expose a custom-answer inline choice."""
        session = TrinityPromptSession(tmp_path)
        with patch.object(
            session,
            "_run_inline_option_selector",
            return_value=CUSTOM_OPTION_VALUE,
        ) as selector:
            result = session.select_option(
                title="q-001",
                question="Which API?",
                options=["LI.FI", "Socket"],
                allow_custom=True,
            )

        assert result == CUSTOM_OPTION_VALUE
        values = selector.call_args.kwargs["values"]
        assert values[-1] == (CUSTOM_OPTION_VALUE, "3. Custom answer...")
