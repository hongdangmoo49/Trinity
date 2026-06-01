"""Tmux layout for TUI mode — split pane with TUI on top, agents below.

Creates a tmux layout like:

┌─────────────────────────────────────────────────────────┐
│                                                         │
│              Trinity TUI (상태/입력)                     │
│                                                         │
├────────────────────────┬────────────────────────────────┤
│                        │                                │
│    Claude (Architect)  │    Codex (Implementer)         │
│    [터미널 출력]        │    [터미널 출력]                │
│                        │                                │
└────────────────────────┴────────────────────────────────┘
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from trinity.models import AgentSpec
from trinity.tmux.pane import TmuxPane
from trinity.tmux.session import TmuxSessionManager, TMUX_CONFIG_FLAGS

logger = logging.getLogger(__name__)


@dataclass
class TUILayout:
    """Manages the tmux layout for TUI mode.

    Creates a two-row layout:
    - Top row: Trinity TUI pane (status dashboard + user input)
    - Bottom row: Agent panes (horizontally split, one per agent)
    """

    session_name: str = "trinity"
    pane_map: dict[str, TmuxPane] = field(default_factory=dict, repr=False)
    tui_pane: TmuxPane | None = None

    def create_layout(
        self,
        agent_specs: list[AgentSpec],
        tui_command: str | None = None,
    ) -> None:
        """Create the TUI + agent tmux layout.

        Args:
            agent_specs: List of agent specs to create panes for.
            tui_command: Optional command to run in the TUI pane
                         (e.g., 'trinity --interactive').
        """
        # Kill existing session if any
        session = TmuxSessionManager(session_name=self.session_name)
        if session.session_exists():
            session.destroy()

        agent_names = [spec.name for spec in agent_specs]
        logger.info(
            f"Creating TUI layout '{self.session_name}' "
            f"with agents: {agent_names}"
        )

        # Step 1: Create session with TUI pane (top)
        subprocess.run(
            ["tmux", *TMUX_CONFIG_FLAGS, "new-session", "-d", "-s", self.session_name],
            check=True,
            capture_output=True,
            timeout=10,
            encoding="utf-8",
        )

        # Get the first pane ID → TUI pane
        result = subprocess.run(
            ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
        )
        pane_ids = result.stdout.strip().splitlines()
        self.tui_pane = TmuxPane(pane_id=pane_ids[0], session_name=self.session_name)

        # Set TUI pane title
        subprocess.run(
            ["tmux", "select-pane", "-t", self.tui_pane.pane_id, "-T", "Trinity TUI"],
            capture_output=True,
            timeout=5,
            encoding="utf-8",
        )

        # Step 2: Split vertically for agent area (bottom)
        subprocess.run(
            [
                "tmux", *TMUX_CONFIG_FLAGS,
                "split-window", "-v", "-t", self.session_name,
            ],
            check=True,
            capture_output=True,
            timeout=10,
            encoding="utf-8",
        )

        # Get updated pane list
        result = subprocess.run(
            ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
        )
        pane_ids = result.stdout.strip().splitlines()

        # The second pane is the first agent's pane
        first_agent_pane = TmuxPane(
            pane_id=pane_ids[-1], session_name=self.session_name,
        )

        if agent_names:
            self.pane_map[agent_names[0]] = first_agent_pane
            subprocess.run(
                [
                    "tmux", "select-pane",
                    "-t", first_agent_pane.pane_id,
                    "-T", agent_names[0],
                ],
                capture_output=True,
                timeout=5,
                encoding="utf-8",
            )

        # Step 3: Split the agent area horizontally for remaining agents
        for name in agent_names[1:]:
            subprocess.run(
                [
                    "tmux", *TMUX_CONFIG_FLAGS,
                    "split-window", "-h",
                    "-t", first_agent_pane.pane_id,
                ],
                check=True,
                capture_output=True,
                timeout=10,
                encoding="utf-8",
            )

            # Get updated pane list
            result = subprocess.run(
                ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_id}"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
            )
            pane_ids = result.stdout.strip().splitlines()

            new_pane = TmuxPane(
                pane_id=pane_ids[-1], session_name=self.session_name,
            )
            self.pane_map[name] = new_pane

            subprocess.run(
                ["tmux", "select-pane", "-t", new_pane.pane_id, "-T", name],
                capture_output=True,
                timeout=5,
                encoding="utf-8",
            )

        # Step 4: Apply layout — 60% top (TUI), 40% bottom (agents)
        # Set main-pane-height for the top pane
        subprocess.run(
            [
                "tmux", "set-option", "-t", self.session_name,
                "main-pane-height", "60%",
            ],
            capture_output=True,
            timeout=5,
            encoding="utf-8",
        )

        # Apply even-horizontal layout to agent panes
        if len(agent_names) > 1:
            # The bottom pane is the parent of agent splits
            subprocess.run(
                [
                    "tmux", "select-layout",
                    "-t", first_agent_pane.pane_id,
                    "even-horizontal",
                ],
                capture_output=True,
                timeout=5,
                encoding="utf-8",
            )

        # Set history limit
        subprocess.run(
            [
                "tmux", "set-option", "-t", self.session_name,
                "history-limit", "10000",
            ],
            capture_output=True,
            timeout=5,
            encoding="utf-8",
        )

        # Step 5: Optionally start TUI in the top pane
        if tui_command and self.tui_pane:
            self.tui_pane.send_keys(tui_command)

        logger.info(
            f"TUI layout created: TUI pane={self.tui_pane.pane_id if self.tui_pane else 'N/A'}, "
            f"agent panes={list(self.pane_map.keys())}"
        )

    def get_agent_pane(self, agent_name: str) -> TmuxPane | None:
        """Get the tmux pane for a specific agent."""
        return self.pane_map.get(agent_name)

    def get_tui_pane(self) -> TmuxPane | None:
        """Get the TUI pane."""
        return self.tui_pane

    def set_pane_title(self, agent_name: str, title: str) -> None:
        """Update a pane's title.

        Args:
            agent_name: Agent name.
            title: New pane title.
        """
        pane = self.pane_map.get(agent_name)
        if not pane:
            return

        subprocess.run(
            ["tmux", "select-pane", "-t", pane.pane_id, "-T", title],
            capture_output=True,
            timeout=5,
            encoding="utf-8",
        )

    def update_round_display(self, round_num: int, agent_states: dict[str, str]) -> None:
        """Update pane titles with round progress.

        Args:
            round_num: Current round number.
            agent_states: Dict of agent_name → state string (e.g. "responding", "done").
        """
        for name, state in agent_states.items():
            icon = "🔄" if state == "responding" else "✅" if state == "done" else "⬜"
            self.set_pane_title(name, f"{name} — R{round_num} {icon}")

    def destroy(self) -> None:
        """Destroy the tmux session."""
        session = TmuxSessionManager(session_name=self.session_name)
        session.destroy()
        self.pane_map.clear()
        self.tui_pane = None

    def exists(self) -> bool:
        """Check if the tmux session exists."""
        session = TmuxSessionManager(session_name=self.session_name)
        return session.session_exists()
