"""Legacy tmux session manager for interactive/debug transport."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from trinity.legacy.tmux.pane import TmuxPane
from trinity.models import AgentSpec

logger = logging.getLogger(__name__)

TMUX_CONFIG_FLAGS = ["-f", "/dev/null"]


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

    def create_session(
        self,
        agent_specs: list[AgentSpec],
        launch_contexts: Mapping[str, object] | None = None,
    ) -> None:
        """Create a new tmux session with a shell pane plus agent panes."""
        if self.session_exists():
            self.destroy()

        all_names = ["cmd"] + [spec.name for spec in agent_specs]
        total_panes = len(all_names)

        logger.info(
            "Creating tmux session '%s' with %d panes",
            self.session_name,
            total_panes,
        )

        subprocess.run(
            ["tmux", *TMUX_CONFIG_FLAGS, "new-session", "-d", "-s", self.session_name],
            check=True,
            capture_output=True,
            timeout=10,
        )

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

        result = subprocess.run(
            ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        pane_ids = result.stdout.strip().splitlines()
        self.pane_map["cmd"] = TmuxPane(
            pane_id=pane_ids[0],
            session_name=self.session_name,
        )

        for name in all_names[1:]:
            split_cmd = ["tmux", *TMUX_CONFIG_FLAGS, "split-window", "-h"]
            cwd = self._launch_cwd(launch_contexts, name)
            if cwd:
                split_cmd.extend(["-c", str(cwd)])
            split_cmd.extend(["-t", self.session_name])

            subprocess.run(
                split_cmd,
                check=True,
                capture_output=True,
                timeout=10,
            )

            result = subprocess.run(
                ["tmux", "list-panes", "-t", self.session_name, "-F", "#{pane_id}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pane_ids = result.stdout.strip().splitlines()
            self.pane_map[name] = TmuxPane(
                pane_id=pane_ids[-1],
                session_name=self.session_name,
            )

        subprocess.run(
            ["tmux", "select-layout", "-t", self.session_name, "even-horizontal"],
            capture_output=True,
            timeout=5,
        )

        for name, pane in self.pane_map.items():
            subprocess.run(
                ["tmux", "select-pane", "-t", pane.pane_id, "-T", name],
                capture_output=True,
                timeout=5,
            )

        logger.info("Created panes: %s", list(self.pane_map.keys()))

    def get_pane(self, agent_name: str) -> TmuxPane | None:
        """Get pane for an agent by name."""
        return self.pane_map.get(agent_name)

    @staticmethod
    def _launch_cwd(
        launch_contexts: Mapping[str, object] | None,
        agent_name: str,
    ) -> Path | None:
        """Extract an agent cwd from launch context metadata."""
        if not launch_contexts:
            return None
        context = launch_contexts.get(agent_name)
        cwd = getattr(context, "cwd", None)
        return cwd if isinstance(cwd, Path) else None

    def attach(self) -> None:
        """Attach to the tmux session."""
        subprocess.run(["tmux", "attach", "-t", self.session_name], timeout=None)

    def destroy(self) -> None:
        """Kill the entire tmux session."""
        if self.session_exists():
            subprocess.run(
                ["tmux", "kill-session", "-t", self.session_name],
                capture_output=True,
                timeout=10,
            )
            logger.info("Destroyed tmux session '%s'", self.session_name)
        self.pane_map.clear()

    def get_all_pane_ids(self) -> list[str]:
        """Return all pane IDs in order."""
        return [pane.pane_id for pane in self.pane_map.values()]

