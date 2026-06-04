"""Shared test fixtures for Trinity."""

import pytest
from pathlib import Path

from trinity.models import AgentSpec, Provider
from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine


@pytest.fixture
def tmp_trinity_dir(tmp_path):
    """Create a temporary .trinity/ directory structure."""
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "agents" / "claude").mkdir(parents=True)
    (state / "agents" / "codex").mkdir(parents=True)
    (state / "agents" / "antigravity").mkdir(parents=True)
    (state / "agents" / "gemini").mkdir(parents=True)
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
