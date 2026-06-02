"""Tests for trinity.tmux — TmuxPane and TmuxSessionManager."""

import pytest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from trinity.models import AgentSpec, Provider
from trinity.tmux.pane import TmuxPane
from trinity.tmux.session import TmuxSessionManager


@dataclass
class _LaunchContext:
    cwd: Path


class TestTmuxPane:
    """Test TmuxPane low-level operations."""

    def test_send_text(self):
        pane = TmuxPane(pane_id="%0", session_name="test")

        with patch("subprocess.run") as mock_run:
            pane.send_text("hello world")
            mock_run.assert_called_once_with(
                ["tmux", "send-keys", "-t", "%0", "hello world", "Enter"],
                check=True,
                capture_output=True,
                timeout=10,
            )

    def test_send_keys(self):
        pane = TmuxPane(pane_id="%1", session_name="test")

        with patch("subprocess.run") as mock_run:
            pane.send_keys("C-c")
            mock_run.assert_called_once_with(
                ["tmux", "send-keys", "-t", "%1", "C-c"],
                check=True,
                capture_output=True,
                timeout=10,
            )

    def test_capture_returns_lines(self):
        pane = TmuxPane(pane_id="%0", session_name="test")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="line1\nline2\nline3")
            lines = pane.capture(lines=-100)
            assert lines == ["line1", "line2", "line3"]
            mock_run.assert_called_once_with(
                ["tmux", "capture-pane", "-t", "%0", "-p", "-S", "-100"],
                capture_output=True,
                text=True,
                timeout=10,
            )

    def test_capture_text_returns_string(self):
        pane = TmuxPane(pane_id="%0", session_name="test")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="output text")
            text = pane.capture_text(lines=-50)
            assert text == "output text"

    def test_is_alive_returns_true(self):
        pane = TmuxPane(pane_id="%0", session_name="test")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert pane.is_alive() is True

    def test_is_alive_returns_false(self):
        pane = TmuxPane(pane_id="%0", session_name="test")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert pane.is_alive() is False

    def test_kill(self):
        pane = TmuxPane(pane_id="%0", session_name="test")

        with patch("subprocess.run") as mock_run:
            pane.kill()
            mock_run.assert_called_once_with(
                ["tmux", "kill-pane", "-t", "%0"],
                capture_output=True,
                timeout=5,
            )

    def test_send_signal(self):
        pane = TmuxPane(pane_id="%0", session_name="test")

        with patch("subprocess.run") as mock_run:
            pane.send_signal("C-c")
            mock_run.assert_called_once_with(
                ["tmux", "send-keys", "-t", "%0", "C-c"],
                capture_output=True,
                timeout=5,
            )

    def test_repr(self):
        pane = TmuxPane(pane_id="%0", session_name="trinity")
        assert repr(pane) == "TmuxPane('%0', session='trinity')"


class TestTmuxSessionManager:
    """Test TmuxSessionManager session lifecycle."""

    def _make_agent_spec(self, name: str) -> AgentSpec:
        return AgentSpec(
            name=name,
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
        )

    def test_session_exists_true(self):
        mgr = TmuxSessionManager(session_name="trinity")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert mgr.session_exists() is True
            mock_run.assert_called_once_with(
                ["tmux", "has-session", "-t", "trinity"],
                capture_output=True,
                timeout=5,
            )

    def test_session_exists_false(self):
        mgr = TmuxSessionManager(session_name="trinity")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert mgr.session_exists() is False

    def test_create_session(self):
        mgr = TmuxSessionManager(session_name="trinity")
        specs = [self._make_agent_spec("claude"), self._make_agent_spec("codex")]

        with patch("subprocess.run") as mock_run:
            # Mock session_exists → False
            # Mock new-session
            # Mock list-panes → returns pane IDs
            mock_run.side_effect = [
                MagicMock(returncode=1),  # session_exists
                MagicMock(returncode=0),  # new-session
                MagicMock(returncode=0),  # set-option history-limit
                MagicMock(stdout="%0\n", returncode=0),  # list-panes (cmd)
                MagicMock(returncode=0),  # split-window (claude)
                MagicMock(stdout="%0\n%1\n", returncode=0),  # list-panes
                MagicMock(returncode=0),  # split-window (codex)
                MagicMock(stdout="%0\n%1\n%2\n", returncode=0),  # list-panes
                MagicMock(returncode=0),  # select-layout
                MagicMock(returncode=0),  # select-pane cmd
                MagicMock(returncode=0),  # select-pane claude
                MagicMock(returncode=0),  # select-pane codex
            ]

            mgr.create_session(specs)

            assert "cmd" in mgr.pane_map
            assert "claude" in mgr.pane_map
            assert "codex" in mgr.pane_map

    def test_create_session_uses_agent_launch_cwd(self, tmp_path):
        mgr = TmuxSessionManager(session_name="trinity")
        specs = [self._make_agent_spec("claude")]
        cwd = tmp_path / "claude-worktree"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1),  # session_exists
                MagicMock(returncode=0),  # new-session
                MagicMock(returncode=0),  # set-option history-limit
                MagicMock(stdout="%0\n", returncode=0),  # list-panes (cmd)
                MagicMock(returncode=0),  # split-window
                MagicMock(stdout="%0\n%1\n", returncode=0),  # list-panes
                MagicMock(returncode=0),  # select-layout
                MagicMock(returncode=0),  # select-pane cmd
                MagicMock(returncode=0),  # select-pane claude
            ]

            mgr.create_session(
                specs,
                launch_contexts={"claude": _LaunchContext(cwd=cwd)},
            )

        split_call = next(
            c for c in mock_run.call_args_list if "split-window" in c.args[0]
        )
        assert "-c" in split_call.args[0]
        assert str(cwd) in split_call.args[0]

    def test_destroy_session(self):
        mgr = TmuxSessionManager(session_name="trinity")
        mgr.pane_map = {"cmd": TmuxPane(pane_id="%0", session_name="trinity")}

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)  # session_exists
            mgr.destroy()
            mock_run.assert_called()
            assert len(mgr.pane_map) == 0

    def test_destroy_nonexistent_session(self):
        mgr = TmuxSessionManager(session_name="trinity")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)  # session doesn't exist
            mgr.destroy()
            # Should not call kill-session
            calls = mock_run.call_args_list
            assert all("kill-session" not in str(c) for c in calls)

    def test_get_pane(self):
        mgr = TmuxSessionManager(session_name="trinity")
        pane = TmuxPane(pane_id="%0", session_name="trinity")
        mgr.pane_map["claude"] = pane

        assert mgr.get_pane("claude") is pane
        assert mgr.get_pane("nonexistent") is None

    def test_get_all_pane_ids(self):
        mgr = TmuxSessionManager(session_name="trinity")
        mgr.pane_map = {
            "cmd": TmuxPane(pane_id="%0", session_name="trinity"),
            "claude": TmuxPane(pane_id="%1", session_name="trinity"),
        }

        ids = mgr.get_all_pane_ids()
        assert ids == ["%0", "%1"]
