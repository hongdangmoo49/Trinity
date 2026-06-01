"""Tmux session manager — create and manage multi-pane tmux sessions."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field

from trinity.models import AgentSpec
from trinity.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)

TMUX_CONFIG_FLAGS = ["-f", "/dev/null"]  # Ignore user tmux config (CCB lesson)


@dataclass
class TmuxSessionManager:
    """Creates and manages a tmux session with agent panes."""

    session_name: str = "trinity"
    pane_map: dict[str, TmuxPane] = field(default_factory=dict, repr=False)

    def session_exists(self) -> bool:
        """Check if the tmux session already exists."""
        result = subprocess.run(
            ["tmux", "has-session", "-t", self.session_name],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0

    def create_session(self, agent_specs: list[AgentSpec]) -> None:
        """Create a new tmux session with panes for each agent.

        Layout: horizontal split, one pane per agent.
        Also adds a 'cmd' shell pane as the first pane.
        """
        if self.session_exists():
            self.destroy()

        all_names = ["cmd"] + [spec.name for spec in agent_specs]
        total_panes = len(all_names)

        logger.info(f"Creating tmux session '{self.session_name}' with {total_panes} panes")

        # Create session with first pane (cmd)
        subprocess.run(
            ["tmux", *TMUX_CONFIG_FLAGS, "new-session", "-d", "-s", self.session_name],
            check=True,
            capture_output=True,
            timeout=10,
        )

        # Set history limit
        subprocess.run(
            [
                "tmux",
                "set-option",
                "-t",
                self.session_name,
                "history-limit",
                "10000",
            ],
            capture_output=True,
            timeout=5,
        )

        # Get the first pane ID (cmd)
        result = subprocess.run(
            ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        pane_ids = result.stdout.strip().splitlines()

        self.pane_map["cmd"] = TmuxPane(pane_id=pane_ids[0], session_name=self.session_name)

        # Create additional panes via split-window
        for i, name in enumerate(all_names[1:], start=1):
            subprocess.run(
                [
                    "tmux",
                    *TMUX_CONFIG_FLAGS,
                    "split-window",
                    "-h",
                    "-t",
                    self.session_name,
                ],
                check=True,
                capture_output=True,
                timeout=10,
            )

            # Get updated pane list
            result = subprocess.run(
                ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_id}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pane_ids = result.stdout.strip().splitlines()

            # The new pane is the last one
            self.pane_map[name] = TmuxPane(
                pane_id=pane_ids[-1], session_name=self.session_name
            )

        # Apply even layout
        subprocess.run(
            ["tmux", "select-layout", "-t", self.session_name, "even-horizontal"],
            capture_output=True,
            timeout=5,
        )

        # Set pane titles
        for name, pane in self.pane_map.items():
            subprocess.run(
                [
                    "tmux",
                    "select-pane",
                    "-t",
                    pane.pane_id,
                    "-T",
                    name,
                ],
                capture_output=True,
                timeout=5,
            )

        logger.info(f"Created panes: {list(self.pane_map.keys())}")

    def get_pane(self, agent_name: str) -> TmuxPane | None:
        """Get pane for an agent by name."""
        return self.pane_map.get(agent_name)

    def attach(self) -> None:
        """Attach to the tmux session (interactive)."""
        subprocess.run(
            ["tmux", "attach", "-t", self.session_name],
            timeout=None,
        )

    def destroy(self) -> None:
        """Kill the entire tmux session."""
        if self.session_exists():
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session_name],
                capture_output=True,
                timeout=10,
            )
            logger.info(f"Destroyed tmux session '{self.session_name}'")
        self.pane_map.clear()

    def get_all_pane_ids(self) -> list[str]:
        """Return all pane IDs in order."""
        return [pane.pane_id for pane in self.pane_map.values()]
