"""Tests for trinity.config."""

import pytest
from pathlib import Path

from trinity.config import TrinityConfig
from trinity.models import Provider


class TestTrinityConfig:
    def test_default_config_has_three_agents(self):
        config = TrinityConfig.default_config()
        assert len(config.agents) == 3
        assert "claude" in config.agents
        assert "codex" in config.agents
        assert "gemini" in config.agents

    def test_default_claude_enabled(self):
        config = TrinityConfig.default_config()
        assert config.agents["claude"].enabled

    def test_default_codex_gemini_disabled(self):
        config = TrinityConfig.default_config()
        assert not config.agents["codex"].enabled
        assert not config.agents["gemini"].enabled

    def test_active_agents_filters_disabled(self):
        config = TrinityConfig.default_config()
        active = config.active_agents
        assert len(active) == 1
        assert "claude" in active

    def test_effective_state_dir_default(self):
        config = TrinityConfig.default_config(project_dir=Path("/tmp/myproject"))
        assert config.effective_state_dir == Path("/tmp/myproject/.trinity")

    def test_effective_state_dir_explicit(self, tmp_path):
        state = tmp_path / "custom_state"
        config = TrinityConfig(state_dir=state)
        assert config.effective_state_dir == state

    def test_shared_context_path(self, tmp_path):
        config = TrinityConfig(project_dir=tmp_path)
        assert config.shared_context_path == tmp_path / ".trinity" / "shared.md"

    def test_load_from_toml(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[general]
session_name = "test-session"
max_deliberation_rounds = 3

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
role_prompt = "You are a tester."

[agents.codex]
provider = "codex"
cli_command = "codex"
enabled = true
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)
        assert config.session_name == "test-session"
        assert config.max_deliberation_rounds == 3
        assert len(config.agents) == 2
        assert config.agents["claude"].role_prompt == "You are a tester."
        assert config.agents["codex"].enabled

    def test_config_compression_defaults(self):
        """TrinityConfig should have prompt compression defaults."""
        config = TrinityConfig.default_config()
        assert config.prompt_compression_enabled is True
        assert config.prompt_compression_round_threshold == 2
        assert config.prompt_compression_max_summary_tokens == 200

    def test_save_and_reload(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        save_path = tmp_path / "test_config.toml"
        config.save(save_path)

        # Reload
        loaded = TrinityConfig.load(save_path)
        assert loaded.session_name == config.session_name
        assert len(loaded.agents) == len(config.agents)
        assert loaded.agents["claude"].provider == Provider.CLAUDE_CODE
