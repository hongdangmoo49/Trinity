"""Tests for trinity.cli — CLI commands."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from click.testing import CliRunner

from trinity.cli import main, load_config, find_config_path
from trinity.context.analytics import RoundRecord, TokenAnalytics, analytics_history_path
from trinity.models import Provider


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def trinity_project(tmp_path):
    """Create a minimal trinity project directory."""
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "agents" / "claude").mkdir(parents=True)
    (state / "agents" / "codex").mkdir(parents=True)
    (state / "agents" / "antigravity").mkdir(parents=True)
    (state / "history").mkdir()
    (state / "logs").mkdir()
    (state / "workspace").mkdir()
    (state / "shared.md").write_text(
        "# Shared Context\n\n## Current Goal\nTest goal\n", encoding="utf-8"
    )
    (state / "trinity.config").write_text(
        '[general]\nsession_name = "test"\n\n'
        '[agents.claude]\nprovider = "claude-code"\ncli_command = "claude"\nenabled = true\n',
        encoding="utf-8",
    )
    return tmp_path


class TestVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __import__("trinity").__version__ in result.output


class TestInit:
    def test_init_creates_structure(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "--non-interactive"])
            assert result.exit_code == 0

            # Check directory structure
            assert Path(".trinity").exists()
            assert Path(".trinity/trinity.config").exists()
            assert Path(".trinity/shared.md").exists()
            assert Path(".trinity/agents/claude/role.md").exists()
            assert Path(".trinity/agents/codex/role.md").exists()
            assert Path(".trinity/agents/antigravity/role.md").exists()
            assert Path(".trinity/history").exists()
            assert Path(".trinity/logs").exists()
            assert Path(".trinity/workspace").exists()

    def test_init_shared_md_content(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "--non-interactive"])
            assert result.exit_code == 0

            shared = Path(".trinity/shared.md").read_text(encoding="utf-8")
            assert "Shared Context" in shared
            assert "Current Goal" in shared

    def test_init_adds_gitignore(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["init", "--non-interactive"])
            assert result.exit_code == 0

            gitignore = Path(".gitignore").read_text(encoding="utf-8")
            assert ".trinity/" in gitignore

    def test_init_existing_without_force(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["init", "--non-interactive"])  # First init
            result = runner.invoke(main, ["init"])  # Second init without --force
            assert "already exists" in result.output

    def test_init_with_force(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["init", "--non-interactive"])  # First init
            result = runner.invoke(main, ["init", "--force", "--non-interactive"])  # Force re-init
            assert result.exit_code == 0
            assert "initialized" in result.output.lower() or "✓" in result.output

    def test_init_gitignore_no_duplicate(self, runner, tmp_path):
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(main, ["init", "--non-interactive"])
            runner.invoke(main, ["init", "--force", "--non-interactive"])

            gitignore = Path(".gitignore").read_text(encoding="utf-8")
            assert gitignore.count(".trinity/") == 1


class TestStatus:
    def test_status_shows_agents(self, runner, trinity_project):
        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == 0
            assert "claude" in result.output
            assert "claude-code" in result.output

    def test_status_shows_shared_context_path(self, runner, trinity_project):
        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            result = runner.invoke(main, ["status"])
            assert "shared context" in result.output.lower() or "shared.md" in result.output


class TestBootstrap:
    def test_bootstrap_requires_project_config(self, runner):
        with patch("trinity.cli.find_config_path", return_value=None):
            result = runner.invoke(main, ["bootstrap", "--no-attach"])

        assert result.exit_code == 1
        assert "trinity init" in result.output

    def test_bootstrap_starts_session_without_attach(self, runner, trinity_project):
        mock_target = SimpleNamespace(
            agent_name="claude",
            spec=SimpleNamespace(provider=Provider.CLAUDE_CODE),
            managed_home=trinity_project / ".trinity" / "agents" / "claude" / "provider-state",
            cwd=trinity_project,
        )
        mock_result = SimpleNamespace(
            session_name="test-bootstrap",
            targets=(mock_target,),
            commands={"claude": "env HOME=/tmp claude"},
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.ProviderBootstrapper") as MockBootstrapper:
                with patch("trinity.cli.attach_to_bootstrap_session") as mock_attach:
                    instance = MockBootstrapper.return_value
                    instance.launch_session.return_value = mock_result

                    result = runner.invoke(
                        main,
                        [
                            "bootstrap",
                            "--agents",
                            "claude,codex",
                            "--session-name",
                            "test-bootstrap",
                            "--no-attach",
                        ],
                    )

        assert result.exit_code == 0
        instance.launch_session.assert_called_once()
        kwargs = instance.launch_session.call_args.kwargs
        assert kwargs["agent_names"] == ["claude", "codex"]
        assert kwargs["session_name"] == "test-bootstrap"
        assert "test-bootstrap" in result.output
        mock_attach.assert_not_called()


class TestContext:
    def test_context_shows_all(self, runner, trinity_project):
        """Test context command reads shared.md via TrinityConfig.shared_context_path."""
        from trinity.config import TrinityConfig

        config_path = trinity_project / ".trinity" / "trinity.config"
        config = TrinityConfig.load(config_path)

        # Ensure shared.md exists at the path config resolves to
        shared_path = config.shared_context_path
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_text(
            "# Shared Context\n\n## Current Goal\nTest goal\n", encoding="utf-8"
        )

        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["context"])
            assert result.exit_code == 0
            assert "Test goal" in result.output

    def test_context_specific_section(self, runner, trinity_project):
        """Test context --section reads a specific section."""
        from trinity.config import TrinityConfig

        config_path = trinity_project / ".trinity" / "trinity.config"
        config = TrinityConfig.load(config_path)

        shared_path = config.shared_context_path
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_text(
            "# Shared Context\n\n## Current Goal\nTest goal\n", encoding="utf-8"
        )

        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["context", "--section", "Current Goal"])
            assert result.exit_code == 0
            assert "Test goal" in result.output

    def test_context_nonexistent_section(self, runner, trinity_project):
        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            result = runner.invoke(main, ["context", "--section", "Nonexistent"])
            assert "not found" in result.output


class TestAsk:
    def test_ask_with_mock(self, runner, trinity_project):
        from trinity.models import DeliberationResult, ConsensusResult

        mock_result = DeliberationResult(
            user_prompt="test question",
            rounds_completed=2,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "I agree."},
                summary="Test consensus reached.",
            ),
            total_tokens_used=500,
            duration_seconds=1.5,
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_orch_instance = MagicMock()
                mock_orch_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_orch_instance

                result = runner.invoke(main, ["ask", "test question"])
                assert result.exit_code == 0
                assert "Consensus" in result.output or "consensus" in result.output

    def test_ask_with_max_rounds_override(self, runner, trinity_project):
        from trinity.models import DeliberationResult, ConsensusResult

        mock_result = DeliberationResult(
            user_prompt="test",
            rounds_completed=2,
            consensus=None,
        )

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_orch_instance = MagicMock()
                mock_orch_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_orch_instance

                result = runner.invoke(main, ["ask", "test", "--max-rounds", "3"])
                assert result.exit_code == 0

    def test_ask_with_agents_filter(self, runner, trinity_project):
        from trinity.models import DeliberationResult

        mock_result = DeliberationResult(user_prompt="test", rounds_completed=1, consensus=None)

        with patch("trinity.cli.find_config_path", return_value=trinity_project / ".trinity" / "trinity.config"):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_orch_instance = MagicMock()
                mock_orch_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_orch_instance

                result = runner.invoke(main, ["ask", "test", "--agents", "claude"])
                assert result.exit_code == 0


class TestAnalytics:
    def test_analytics_command_no_data(self, runner):
        """trinity analytics should handle no-data case gracefully."""
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["analytics"])
            assert result.exit_code == 0

    def test_analytics_command_reads_persisted_history(self, runner, trinity_project):
        """trinity analytics should display saved records without a live session."""
        state_dir = trinity_project / ".trinity"
        token_analytics = TokenAnalytics(history_path=analytics_history_path(state_dir))
        token_analytics.record(
            RoundRecord(1, {"claude": 100, "codex": 50}, 20, 1.0)
        )
        token_analytics.record(
            RoundRecord(2, {"claude": 150, "codex": 100}, 25, 1.5)
        )

        config_path = state_dir / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["analytics"])

        assert result.exit_code == 0
        assert "Rounds: 2" in result.output
        assert "Total tokens: 400" in result.output
        assert "Avg tokens/round: 200" in result.output
        assert "claude" in result.output
        assert "codex" in result.output


class TestFindConfigPath:
    def test_finds_config_in_current_dir(self, trinity_project):
        with patch("trinity.cli.Path.cwd", return_value=trinity_project):
            path = find_config_path()
            assert path is not None
            assert path.name == "trinity.config"

    def test_returns_none_when_no_config(self, tmp_path):
        with patch("trinity.cli.Path.cwd", return_value=tmp_path):
            path = find_config_path()
            assert path is None


class TestLoadConfig:
    def test_loads_from_path(self, trinity_project):
        config_path = trinity_project / ".trinity" / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            config = load_config()
            assert config.session_name == "test"
            assert "claude" in config.agents

    def test_returns_default_when_no_path(self, tmp_path):
        with patch("trinity.cli.find_config_path", return_value=None):
            config = load_config()
            assert config.session_name == "trinity"  # default
