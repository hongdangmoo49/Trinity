"""Tests for trinity.config."""

from pathlib import Path

from trinity.config import TrinityConfig
from trinity.models import Provider


class TestTrinityConfig:
    def test_default_config_has_three_agents(self):
        config = TrinityConfig.default_config()
        assert len(config.agents) == 3
        assert "claude" in config.agents
        assert "codex" in config.agents
        assert "antigravity" in config.agents

    def test_default_claude_enabled(self):
        config = TrinityConfig.default_config()
        assert config.agents["claude"].enabled

    def test_default_codex_antigravity_disabled(self):
        config = TrinityConfig.default_config()
        assert not config.agents["codex"].enabled
        assert not config.agents["antigravity"].enabled
        assert config.agents["antigravity"].provider == Provider.ANTIGRAVITY_CLI
        assert config.agents["antigravity"].cli_command == "agy"

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
model = "opus[1m]"
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
        assert config.agents["claude"].model == "opus[1m]"
        assert config.agents["claude"].role_prompt == "You are a tester."
        assert config.agents["codex"].enabled

    def test_load_detects_lang_from_korean_role_prompt(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[general]
session_name = "test-session"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
role_prompt = "당신은 아키텍트입니다."
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)
        assert config.lang == "ko"

    def test_load_migrates_legacy_gemini_agent_to_antigravity(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[agents.gemini]
provider = "gemini-cli"
cli_command = "gemini"
enabled = true
workspace_mode = "inplace"
context_budget = 1000000
role_prompt = "You are the Reviewer. You explore alternatives, identify potential issues, and ensure quality. Think critically about trade-offs and propose tests."
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)

        assert "gemini" not in config.agents
        antigravity = config.agents["antigravity"]
        assert antigravity.name == "antigravity"
        assert antigravity.provider == Provider.ANTIGRAVITY_CLI
        assert antigravity.cli_command == "agy"
        assert antigravity.enabled is True
        assert antigravity.context_budget == 1_000_000

    def test_save_after_legacy_gemini_migration_is_canonical(self, tmp_trinity_dir, tmp_path):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[agents.gemini]
provider = "gemini-cli"
cli_command = "gemini"
enabled = true
role_prompt = "custom reviewer prompt"
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)
        save_path = tmp_path / "trinity.config"
        config.save(save_path)
        saved = save_path.read_text(encoding="utf-8")

        assert "[agents.antigravity]" in saved
        assert "gemini-cli" not in saved
        assert 'cli_command = "agy"' in saved
        assert "custom reviewer prompt" in saved

    def test_load_prefers_existing_antigravity_over_legacy_gemini(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[agents.antigravity]
provider = "antigravity-cli"
cli_command = "agy"
enabled = true
role_prompt = "antigravity reviewer"

[agents.gemini]
provider = "gemini-cli"
cli_command = "gemini"
enabled = true
role_prompt = "old gemini reviewer"
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)

        assert list(config.agents) == ["antigravity"]
        assert config.agents["antigravity"].role_prompt == "antigravity reviewer"

    def test_load_migrates_custom_gemini_cli_provider_key(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[agents.reviewer]
provider = "gemini-cli"
cli_command = "gemini"
enabled = true
role_prompt = "custom reviewer"
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)

        reviewer = config.agents["reviewer"]
        assert reviewer.provider == Provider.ANTIGRAVITY_CLI
        assert reviewer.cli_command == "agy"
        assert reviewer.role_prompt == "custom reviewer"

    def test_korean_role_prompt_overrides_legacy_explicit_english_lang(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[general]
lang = "en"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
role_prompt = "당신은 아키텍트입니다."
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)
        assert config.lang == "ko"

    def test_config_compression_defaults(self):
        """TrinityConfig should have prompt compression defaults."""
        config = TrinityConfig.default_config()
        assert config.prompt_compression_enabled is True
        assert config.prompt_compression_round_threshold == 2
        assert config.prompt_compression_max_summary_tokens == 200

    def test_provider_readiness_defaults(self):
        config = TrinityConfig.default_config()
        assert config.provider_readiness_mode == "strict"
        assert config.provider_readiness_timeout_seconds == 20.0

    def test_default_provider_timeouts(self):
        config = TrinityConfig.default_config()
        assert config.round_timeout_seconds == 300.0
        assert config.execution_timeout_seconds == 1800.0
        assert config.synthesis_timeout_seconds == 300.0

    def test_provider_state_mode_defaults_to_user_home(self):
        config = TrinityConfig.default_config()
        assert config.provider_state_mode == "user-home"

    def test_transport_mode_defaults_to_one_shot(self):
        config = TrinityConfig.default_config()
        assert config.transport_mode == "one-shot"

    def test_load_provider_state_mode(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[general]
provider_state_mode = "isolated"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)

        assert config.provider_state_mode == "isolated"

    def test_load_transport_mode(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[general]
transport_mode = "tmux"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)

        assert config.transport_mode == "tmux"

    def test_load_rejects_invalid_provider_state_mode(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[general]
provider_state_mode = "sandboxed"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
""",
            encoding="utf-8",
        )

        import pytest

        with pytest.raises(ValueError, match="provider_state_mode"):
            TrinityConfig.load(config_path)

    def test_load_rejects_invalid_transport_mode(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[general]
transport_mode = "interactive"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
""",
            encoding="utf-8",
        )

        import pytest

        with pytest.raises(ValueError, match="transport_mode"):
            TrinityConfig.load(config_path)

    def test_load_provider_readiness_config(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[deliberation]
provider_readiness_mode = "degraded"
provider_readiness_timeout_seconds = 1.5

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)

        assert config.provider_readiness_mode == "degraded"
        assert config.provider_readiness_timeout_seconds == 1.5

    def test_save_and_reload(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        config.provider_readiness_mode = "degraded"
        config.provider_readiness_timeout_seconds = 2.0
        config.round_timeout_seconds = 300.0
        config.execution_timeout_seconds = 1200.0
        config.synthesis_mode = "model"
        config.synthesis_agent = "claude"
        config.synthesis_model = "sonnet"
        config.synthesis_timeout_seconds = 9.0
        config.synthesis_max_input_chars = 12_345
        save_path = tmp_path / "test_config.toml"
        config.save(save_path)

        # Reload
        loaded = TrinityConfig.load(save_path)
        assert loaded.session_name == config.session_name
        assert len(loaded.agents) == len(config.agents)
        assert loaded.agents["claude"].provider == Provider.CLAUDE_CODE
        assert loaded.agents["claude"].model == config.agents["claude"].model
        assert loaded.provider_state_mode == "user-home"
        assert loaded.transport_mode == "one-shot"
        assert loaded.provider_readiness_mode == "degraded"
        assert loaded.provider_readiness_timeout_seconds == 2.0
        assert loaded.round_timeout_seconds == 300.0
        assert loaded.execution_timeout_seconds == 1200.0
        assert loaded.synthesis_mode == "model"
        assert loaded.synthesis_agent == "claude"
        assert loaded.synthesis_model == "sonnet"
        assert loaded.synthesis_timeout_seconds == 9.0
        assert loaded.synthesis_max_input_chars == 12_345

    def test_save_includes_model_field(self, tmp_path):
        config = TrinityConfig.default_config(project_dir=tmp_path)
        config.agents["claude"].model = "opus[1m]"
        config.agents["claude"].context_budget = 1_000_000
        save_path = tmp_path / "test_config.toml"

        config.save(save_path)

        text = save_path.read_text(encoding="utf-8")
        assert 'model = "opus[1m]"' in text

    def test_save_load_roundtrip_with_special_chars(self, tmp_path):
        """Verify special characters in role_prompt survive save/load."""
        config = TrinityConfig.default_config()
        config.agents["claude"].role_prompt = 'He said "hello"\nwith\nnewlines\tand\ttabs'

        config_path = tmp_path / "trinity.config"
        config.save(config_path)
        loaded = TrinityConfig.load(config_path)

        assert loaded.agents["claude"].role_prompt == config.agents["claude"].role_prompt

    def test_synthesis_config_defaults(self):
        config = TrinityConfig.default_config()
        assert config.synthesis_mode == "auto"
        assert config.synthesis_agent == ""
        assert config.synthesis_model == "fast"
        assert config.synthesis_timeout_seconds == 300.0
        assert config.synthesis_max_input_chars == 60_000

    def test_load_synthesis_config(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[deliberation]
synthesis_mode = "model"
synthesis_agent = "codex"
synthesis_model = "gpt-5.4-mini"
synthesis_timeout_seconds = 5.5
synthesis_max_input_chars = 12000

[agents.codex]
provider = "codex"
cli_command = "codex"
enabled = true
""",
            encoding="utf-8",
        )

        config = TrinityConfig.load(config_path)

        assert config.synthesis_mode == "model"
        assert config.synthesis_agent == "codex"
        assert config.synthesis_model == "gpt-5.4-mini"
        assert config.synthesis_timeout_seconds == 5.5
        assert config.synthesis_max_input_chars == 12_000

    def test_load_rejects_invalid_synthesis_mode(self, tmp_trinity_dir):
        config_path = tmp_trinity_dir / "trinity.config"
        config_path.write_text(
            """
[deliberation]
synthesis_mode = "always"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
""",
            encoding="utf-8",
        )

        import pytest

        with pytest.raises(ValueError, match="synthesis_mode"):
            TrinityConfig.load(config_path)
