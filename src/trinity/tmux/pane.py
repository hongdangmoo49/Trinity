"""Tmux pane — low-level I/O operations for a single tmux pane."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TmuxPane:
    """Represents a single tmux pane. All methods shell out to tmux CLI."""

    pane_id: str  # e.g. "%0"
    session_name: str

    def send_text(self, text: str) -> None:
        """Send text to the pane via tmux send-keys."""
        subprocess.run(
            ["tmux", "send-keys", "-t", self.pane_id, text, "Enter"],
            check=True,
            capture_output=True,
            timeout=10,
        )

    def send_text_heredoc(self, text: str, marker: str = "TRINITY_EOF") -> None:
        """Inject multi-line text safely via heredoc pattern.

        Uses a temp file approach instead of literal heredoc to avoid
        send-keys escaping issues with special characters.
        """
        # Write content to a temp file inside the pane's shell
        # This avoids all escaping problems with send-keys
        import tempfile
        import os

        # Use a unique temp file
        tmp_path = f"/tmp/trinity_heredoc_{id(self)}_{os.getpid()}"

        # Write content to temp file from the Python side
        with open(tmp_path, "w") as f:
            f.write(text)

        # Use tmux load-buffer + paste approach
        try:
            subprocess.run(
                ["tmux", "load-buffer", "-t", self.pane_id, tmp_path],
                check=True,
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["tmux", "paste-buffer", "-t", self.pane_id],
                check=True,
                capture_output=True,
                timeout=10,
            )
            # Send Enter to submit
            subprocess.run(
                ["tmux", "send-keys", "-t", self.pane_id, "Enter"],
                check=True,
                capture_output=True,
                timeout=10,
            )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def send_keys(self, keys: str) -> None:
        """Send raw keys (no automatic Enter)."""
        subprocess.run(
            ["tmux", "send-keys", "-t", self.pane_id, keys],
            check=True,
            capture_output=True,
            timeout=10,
        )

    def capture(self, lines: int = -100) -> list[str]:
        """Capture pane output as list of lines.

        Args:
            lines: Negative number means "last N lines" (-100 = last 100).
                   Positive means "from line N".
        """
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", self.pane_id, "-p", "-S", str(lines)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.splitlines()

    def capture_text(self, lines: int = -100) -> str:
        """Capture pane output as single string."""
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", self.pane_id, "-p", "-S", str(lines)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout

    def is_alive(self) -> bool:
        """Check if the pane still exists."""
        result = subprocess.run(
            ["tmux", "display-panes", "-t", self.pane_id],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0

    def kill(self) -> None:
        """Kill the pane."""
        subprocess.run(
            ["tmux", "kill-pane", "-t", self.pane_id],
            capture_output=True,
            timeout=5,
        )

    def send_signal(self, signal: str = "C-c") -> None:
        """Send a signal (e.g., C-c for interrupt)."""
        subprocess.run(
            ["tmux", "send-keys", "-t", self.pane_id, signal],
            capture_output=True,
            timeout=5,
        )

    def __repr__(self) -> str:
        return f"TmuxPane({self.pane_id!r}, session={self.session_name!r})"
