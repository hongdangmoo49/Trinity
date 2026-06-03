"""Managed Home — per-agent isolated home directories.

Each agent gets its own "home" directory for provider-specific state,
preventing config file collisions between Claude, Codex, and Gemini.

Directory layout:
    .trinity/agents/
        <agent-name>/
            provider-state/      ← isolated home (HOME env override)
                .claude/         ← Claude Code config/state
                .codex/          ← Codex config/state
                .config/         ← Gemini CLI config
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class ManagedHome:
    """Creates and manages per-agent isolated home directories.

    This prevents provider state leakage between agents. For example,
    Claude Code writes to ~/.claude/, Codex to ~/.codex/, etc.
    By overriding HOME, each agent uses its own state directory.

    Usage:
        mh = ManagedHome(state_dir=Path(".trinity"))
        home = mh.setup("claude", provider=Provider.CLAUDE_CODE)
        # home = .trinity/agents/claude/provider-state
        # Set HOME=home when spawning the agent process
    """

    def __init__(self, state_dir: Path):
        """
        Args:
            state_dir: The .trinity state directory.
        """
        self.state_dir = state_dir.resolve()
        self.agents_dir = self.state_dir / "agents"

    def _agent_home(self, agent_name: str) -> Path:
        """Return the managed home path for an agent."""
        return self.agents_dir / agent_name / "provider-state"

    def _validate_path_within_home(self, home: Path, filename: str) -> Path:
        """Resolve filename within home, raising ValueError on path traversal."""
        resolved = (home / filename).resolve()
        if not resolved.is_relative_to(home.resolve()):
            raise ValueError(f"Path traversal detected: {filename}")
        return resolved

    def setup(self, agent_name: str, provider: str | None = None) -> Path:
        """Create an isolated home directory for the agent.

        Args:
            agent_name: Unique agent identifier.
            provider: Provider name (for provider-specific init).

        Returns:
            Path to the managed home directory.
        """
        home = self._agent_home(agent_name)
        home.mkdir(parents=True, exist_ok=True)

        # Create provider-specific subdirectories
        if provider:
            self._init_provider_dirs(home, provider)

        logger.info(f"Managed home for '{agent_name}': {home}")
        return home

    def _init_provider_dirs(self, home: Path, provider: str) -> None:
        """Create provider-specific config directories inside managed home."""
        provider_dirs = {
            "claude-code": [".claude"],
            "codex": [".codex"],
            "gemini-cli": [".config", ".config/gemini"],
        }

        dirs = provider_dirs.get(provider, [])
        for d in dirs:
            (home / d).mkdir(parents=True, exist_ok=True)

    def get_home(self, agent_name: str) -> Path | None:
        """Get the managed home path if it exists."""
        home = self._agent_home(agent_name)
        return home if home.exists() else None

    def get_env_overrides(self, agent_name: str) -> dict[str, str]:
        """Return environment variable overrides for the agent.

        These should be merged into the agent process environment.

        Returns:
            Dict with HOME and any provider-specific env vars.
        """
        home = self._agent_home(agent_name)
        if not home.exists():
            return {}

        env = {"HOME": str(home)}

        # Add XDG directories for Linux compatibility
        env["XDG_CONFIG_HOME"] = str(home / ".config")
        env["XDG_DATA_HOME"] = str(home / ".local" / "share")
        env["XDG_CACHE_HOME"] = str(home / ".cache")

        return env

    def exists(self, agent_name: str) -> bool:
        """Check if a managed home exists for the agent."""
        return self._agent_home(agent_name).exists()

    def cleanup(self, agent_name: str) -> bool:
        """Remove the managed home for an agent.

        Returns:
            True if cleanup succeeded or home didn't exist.
        """
        home = self._agent_home(agent_name)
        if not home.exists():
            return True

        try:
            shutil.rmtree(home)
            logger.info(f"Cleaned up managed home for '{agent_name}'")
            return True
        except OSError as e:
            logger.error(f"Failed to clean up managed home for '{agent_name}': {e}")
            return False

    def cleanup_all(self) -> int:
        """Remove all managed homes. Returns count cleaned."""
        if not self.agents_dir.exists():
            return 0

        count = 0
        for agent_dir in self.agents_dir.iterdir():
            if agent_dir.is_dir():
                state_dir = agent_dir / "provider-state"
                if state_dir.exists():
                    try:
                        shutil.rmtree(state_dir)
                        count += 1
                    except OSError:
                        pass
        return count

    def get_disk_usage(self, agent_name: str) -> int:
        """Get total disk usage in bytes for the agent's managed home."""
        home = self._agent_home(agent_name)
        if not home.exists():
            return 0

        total = 0
        for path in home.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total

    def write_config(self, agent_name: str, filename: str, content: str) -> Path:
        """Write a config file into the agent's managed home.

        Args:
            agent_name: Agent identifier.
            filename: Relative path within the managed home (e.g., ".claude/settings.json").
            content: File content.

        Returns:
            Path to the written file.
        """
        home = self._agent_home(agent_name)
        home.mkdir(parents=True, exist_ok=True)

        file_path = self._validate_path_within_home(home, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        logger.debug(f"Wrote config for '{agent_name}': {file_path}")
        return file_path

    def read_config(self, agent_name: str, filename: str) -> str | None:
        """Read a config file from the agent's managed home.

        Returns:
            File content, or None if not found.
        """
        home = self._agent_home(agent_name)
        file_path = self._validate_path_within_home(home, filename)

        if not file_path.exists():
            return None

        return file_path.read_text(encoding="utf-8")

    def list_agents(self) -> list[str]:
        """List all agents with managed homes."""
        if not self.agents_dir.exists():
            return []

        return [
            d.name
            for d in self.agents_dir.iterdir()
            if d.is_dir() and (d / "provider-state").exists()
        ]
