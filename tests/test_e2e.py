"""Tests for E2E flow — init → ask → status → context (mock agents)."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from click.testing import CliRunner

from trinity.cli import main
from trinity.models import (
    AgentSpec, ConsensusResult, ContextUsage, DeliberationResult, Provider,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path


def _mock_orchestrator_result():
    """Create a mock DeliberationResult."""
    return DeliberationResult(
        user_prompt="test question",
        rounds_completed=2,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=3,
            total_agents=3,
            opinions={"a": "yes", "b": "yes", "c": "yes"},
            summary="Use pytest for testing.",
        ),
        total_tokens_used=5000,
        duration_seconds=3.5,
    )


# ===========================================================================
# E2E: init
# ===========================================================================

class TestE2EInit:
    def test_init_creates_directory(self, runner, project_dir):
        with patch("trinity.cli.Path.cwd", return_value=project_dir):
            result = runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert (project_dir / ".trinity").exists()
        assert (project_dir / ".trinity" / "trinity.config").exists()
        assert (project_dir / ".trinity" / "shared.md").exists()
        assert "initialized" in result.output.lower() or "✓" in result.output

    def test_init_creates_agent_dirs(self, runner, project_dir):
        with patch("trinity.cli.Path.cwd", return_value=project_dir):
            runner.invoke(main, ["init"])

        assert (project_dir / ".trinity" / "agents" / "claude").exists()
        assert (project_dir / ".trinity" / "agents" / "codex").exists()
        assert (project_dir / ".trinity" / "agents" / "gemini").exists()

    def test_init_force_overwrites(self, runner, project_dir):
        with patch("trinity.cli.Path.cwd", return_value=project_dir):
            runner.invoke(main, ["init"])
            # Modify a file
            config_path = project_dir / ".trinity" / "trinity.config"
            config_path.write_text("modified", encoding="utf-8")

            result = runner.invoke(main, ["init", "--force"])
            assert result.exit_code == 0
            assert config_path.read_text() != "modified"

    def test_init_no_force_warns(self, runner, project_dir):
        with patch("trinity.cli.Path.cwd", return_value=project_dir):
            runner.invoke(main, ["init"])
            result = runner.invoke(main, ["init"])
            assert "already exists" in result.output


# ===========================================================================
# E2E: status
# ===========================================================================

class TestE2EStatus:
    def test_status_shows_agents(self, runner, project_dir):
        with patch("trinity.cli.Path.cwd", return_value=project_dir):
            runner.invoke(main, ["init"])

        config_path = project_dir / ".trinity" / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["status"])

        assert result.exit_code == 0


# ===========================================================================
# E2E: ask (with mock)
# ===========================================================================

class TestE2EAsk:
    def test_ask_with_mock_orchestrator(self, runner, project_dir):
        mock_result = _mock_orchestrator_result()

        with patch("trinity.cli.Path.cwd", return_value=project_dir):
            runner.invoke(main, ["init"])

        config_path = project_dir / ".trinity" / "trinity.config"

        with patch("trinity.cli.find_config_path", return_value=config_path):
            with patch("trinity.cli.TrinityOrchestrator") as MockOrch:
                mock_instance = MagicMock()
                mock_instance.ask = AsyncMock(return_value=mock_result)
                MockOrch.return_value = mock_instance

                with patch("asyncio.run", return_value=mock_result):
                    result = runner.invoke(main, ["ask", "test question"])

        assert result.exit_code == 0


# ===========================================================================
# E2E: context
# ===========================================================================

class TestE2EContext:
    def test_context_shows_shared(self, runner, project_dir):
        with patch("trinity.cli.Path.cwd", return_value=project_dir):
            runner.invoke(main, ["init"])

        config_path = project_dir / ".trinity" / "trinity.config"
        with patch("trinity.cli.find_config_path", return_value=config_path):
            result = runner.invoke(main, ["context"])

        assert result.exit_code == 0


# ===========================================================================
# E2E: version
# ===========================================================================

class TestE2EVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "trinity" in result.output.lower()
