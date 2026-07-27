"""Shared test fixtures for Trinity."""

import os
import sys

import pytest
from pathlib import Path
from textual.pilot import Pilot

from trinity.models import AgentSpec, Provider
from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine


@pytest.fixture(autouse=True)
def stabilize_textual_ci_pause(monkeypatch):
    if not os.environ.get("CI"):
        return
    original_pause = Pilot.pause

    async def pause(pilot, delay=None):
        await original_pause(pilot, delay)
        if delay is None:
            await original_pause(pilot, 0.1 if sys.platform == "win32" else 0.05)

    monkeypatch.setattr(Pilot, "pause", pause)


@pytest.fixture
def tmp_trinity_dir(tmp_path):
    """Create a temporary .trinity/ directory structure."""
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "agents" / "claude").mkdir(parents=True)
    (state / "agents" / "codex").mkdir(parents=True)
    (state / "agents" / "antigravity").mkdir(parents=True)
    (state / "history").mkdir()
    (state / "logs").mkdir()
    (state / "workspace").mkdir()
    return state


@pytest.fixture
def sample_config(tmp_trinity_dir):
    """Minimal valid config with one Claude agent."""
    return TrinityConfig(
        project_dir=tmp_trinity_dir.parent,
        state_dir=tmp_trinity_dir,
        agents={
            "claude": AgentSpec(
                name="claude",
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
                role_prompt="You are the Architect.",
                enabled=True,
            ),
        },
    )


@pytest.fixture
def shared_engine(tmp_trinity_dir):
    """SharedContextEngine pointed at tmp_trinity_dir/shared.md."""
    return SharedContextEngine(
        path=tmp_trinity_dir / "shared.md",
        keep_sections=["## Current Goal", "## Agreed Conclusion"],
    )


@pytest.fixture
def sample_agent_spec():
    """A basic Claude agent spec for testing."""
    return AgentSpec(
        name="claude",
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        role_prompt="You are the Architect.",
    )
