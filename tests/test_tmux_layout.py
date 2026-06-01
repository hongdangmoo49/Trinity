"""Tests for trinity.tmux.layout — TUI tmux layout management."""

from unittest.mock import MagicMock, call, patch

import pytest

from trinity.models import AgentSpec, Provider
from trinity.tmux.layout import TUILayout


@pytest.fixture
def agent_specs():
    return [
        AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            enabled=True,
        ),
        AgentSpec(
            name="codex",
            provider=Provider.CODEX,
            cli_command="codex",
            enabled=True,
        ),
    ]


@pytest.fixture
def single_agent_spec():
    return [
        AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            enabled=True,
        ),
    ]


class TestTUILayout:
    def test_init(self):
        layout = TUILayout(session_name="test-session")
        assert layout.session_name == "test-session"
        assert layout.pane_map == {}
        assert layout.tui_pane is None

    def test_get_agent_pane(self):
        layout = TUILayout()
        mock_pane = MagicMock()
        layout.pane_map["claude"] = mock_pane
        assert layout.get_agent_pane("claude") is mock_pane
        assert layout.get_agent_pane("nonexistent") is None

    def test_get_tui_pane(self):
        layout = TUILayout()
        assert layout.get_tui_pane() is None
        mock_pane = MagicMock()
        layout.tui_pane = mock_pane
        assert layout.get_tui_pane() is mock_pane

    @patch("trinity.tmux.layout.subprocess.run")
    def test_set_pane_title(self, mock_run, agent_specs):
        layout = TUILayout()
        mock_pane = MagicMock()
        mock_pane.pane_id = "%1"
        layout.pane_map["claude"] = mock_pane

        layout.set_pane_title("claude", "Claude — R1 🔄")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "select-pane" in args
        assert "%1" in args
        assert "Claude — R1 🔄" in args

    def test_set_pane_title_nonexistent(self):
        layout = TUILayout()
        # Should not raise
        layout.set_pane_title("nonexistent", "title")

    @patch("trinity.tmux.layout.subprocess.run")
    def test_update_round_display(self, mock_run, agent_specs):
        layout = TUILayout()
        for spec in agent_specs:
            mock_pane = MagicMock()
            mock_pane.pane_id = f"%{len(layout.pane_map)}"
            layout.pane_map[spec.name] = mock_pane

        layout.update_round_display(1, {
            "claude": "responding",
            "codex": "done",
        })

        # Should have called set_pane_title for each agent
        assert mock_run.call_count == 2

    @patch("trinity.tmux.layout.subprocess.run")
    def test_destroy(self, mock_run):
        layout = TUILayout(session_name="test-layout")
        layout.pane_map["claude"] = MagicMock()

        with patch.object(layout, "exists", return_value=True):
            layout.destroy()

        assert layout.pane_map == {}
        assert layout.tui_pane is None

    @patch("trinity.tmux.layout.subprocess.run")
    def test_exists_checks_session(self, mock_run):
        layout = TUILayout(session_name="test-layout")

        # Session exists
        mock_run.return_value = MagicMock(returncode=0)
        assert layout.exists() is True

        # Session doesn't exist
        mock_run.return_value = MagicMock(returncode=1)
        assert layout.exists() is False

    @patch("trinity.tmux.layout.subprocess.run")
    def test_create_layout_single_agent(self, mock_run, single_agent_spec):
        """Test layout creation with a single agent."""
        # Mock pane list responses
        mock_run.return_value = MagicMock(
            stdout="%0\n", returncode=0, stderr=""
        )

        layout = TUILayout(session_name="test-single")

        # Need to handle multiple calls with different pane counts
        call_count = [0]

        def mock_subprocess_run(*args, **kwargs):
            call_count[0] += 1
            if "list-panes" in str(args[0]):
                if call_count[0] <= 2:
                    return MagicMock(stdout="%0\n", returncode=0, stderr="")
                else:
                    return MagicMock(stdout="%0\n%1\n", returncode=0, stderr="")
            return MagicMock(stdout="", returncode=0, stderr="")

        mock_run.side_effect = mock_subprocess_run

        layout.create_layout(single_agent_spec)

        assert layout.tui_pane is not None
        assert "claude" in layout.pane_map

    @patch("trinity.tmux.layout.subprocess.run")
    def test_create_layout_with_tui_command(self, mock_run, single_agent_spec):
        """Test layout creation with auto-start TUI command."""
        mock_run.return_value = MagicMock(stdout="%0\n", returncode=0, stderr="")

        layout = TUILayout(session_name="test-tui-cmd")

        def mock_subprocess_run(*args, **kwargs):
            if "list-panes" in str(args[0]):
                return MagicMock(stdout="%0\n%1\n", returncode=0, stderr="")
            return MagicMock(stdout="", returncode=0, stderr="")

        mock_run.side_effect = mock_subprocess_run

        layout.create_layout(single_agent_spec, tui_command="trinity")

        # Should have created the layout
        assert layout.tui_pane is not None
