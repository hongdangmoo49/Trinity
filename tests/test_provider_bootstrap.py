"""Tests for isolated provider bootstrap helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trinity.config import TrinityConfig
from trinity.models import AgentSpec, Provider
from trinity.providers.bootstrap import (
    ProviderBootstrapError,
    ProviderBootstrapper,
    build_provider_argv,
    build_provider_command,
)


def _config(tmp_path: Path) -> TrinityConfig:
    return TrinityConfig(
        project_dir=tmp_path,
        state_dir=tmp_path / ".trinity",
        session_name="test",
        agents={
            "claude": AgentSpec(
                name="claude",
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
                enabled=True,
                extra_args=["--dangerously-skip-permissions"],
            ),
            "codex": AgentSpec(
                name="codex",
                provider=Provider.CODEX,
                cli_command="codex",
                enabled=False,
            ),
        },
    )


def test_prepare_targets_uses_active_agents_by_default(tmp_path):
    bootstrapper = ProviderBootstrapper()

    targets = bootstrapper.prepare_targets(_config(tmp_path))

    assert [target.agent_name for target in targets] == ["claude"]
    target = targets[0]
    assert target.managed_home == tmp_path / ".trinity" / "agents" / "claude" / "provider-state"
    assert target.env_overrides["HOME"] == str(target.managed_home)
    assert (target.managed_home / ".claude").exists()


def test_prepare_targets_allows_explicit_disabled_agent(tmp_path):
    bootstrapper = ProviderBootstrapper()

    targets = bootstrapper.prepare_targets(_config(tmp_path), agent_names=["codex"])

    assert [target.agent_name for target in targets] == ["codex"]
    assert (targets[0].managed_home / ".codex").exists()


def test_select_agent_specs_rejects_unknown_agent(tmp_path):
    bootstrapper = ProviderBootstrapper()

    with pytest.raises(ProviderBootstrapError, match="Unknown agent"):
        bootstrapper.select_agent_specs(_config(tmp_path), agent_names=["ghost"])


def test_build_provider_command_includes_isolated_env_and_args():
    spec = AgentSpec(
        name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        model="gpt-5.4-mini",
        extra_args=["--flag"],
    )

    command = build_provider_command(
        spec,
        {
            "HOME": "/tmp/home",
            "XDG_CONFIG_HOME": "/tmp/home/.config",
        },
    )

    assert command.startswith("env HOME=/tmp/home XDG_CONFIG_HOME=/tmp/home/.config ")
    assert "codex --model gpt-5.4-mini --flag" in command


def test_build_provider_argv_uses_argv_not_shell_string():
    spec = AgentSpec(
        name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        model="gpt-5.4-mini",
        extra_args=["--flag", "value with spaces"],
    )

    argv = build_provider_argv(spec)

    assert argv == (
        "codex",
        "--model",
        "gpt-5.4-mini",
        "--flag",
        "value with spaces",
    )


def test_run_sequential_streams_commands_without_tmux(tmp_path):
    config = _config(tmp_path)
    runner = MagicMock()
    runner.stream_interactive.return_value = 0

    with patch("trinity.providers.bootstrap.shutil.which", return_value="/bin/claude"):
        result = ProviderBootstrapper(runner=runner).run_sequential(
            config,
            agent_names=["claude"],
        )

    runner.stream_interactive.assert_called_once()
    command = runner.stream_interactive.call_args.args[0]
    assert command.argv == ("claude", "--dangerously-skip-permissions")
    assert command.cwd == tmp_path
    assert command.env["HOME"] == str(
        tmp_path / ".trinity" / "agents" / "claude" / "provider-state"
    )
    assert result.exit_codes == {"claude": 0}
    assert result.failed_agents == ()


def test_run_sequential_check_only_does_not_launch(tmp_path):
    runner = MagicMock()

    with patch("trinity.providers.bootstrap.shutil.which", return_value=None):
        result = ProviderBootstrapper(runner=runner).run_sequential(
            _config(tmp_path),
            agent_names=["claude"],
            check_only=True,
        )

    runner.stream_interactive.assert_not_called()
    assert result.check_only is True
    assert result.checks["claude"].installed is False
    assert result.exit_codes == {}


def test_run_sequential_rejects_missing_cli_without_skip_ready(tmp_path):
    runner = MagicMock()

    with patch("trinity.providers.bootstrap.shutil.which", return_value=None):
        with pytest.raises(ProviderBootstrapError, match="not found"):
            ProviderBootstrapper(runner=runner).run_sequential(
                _config(tmp_path),
                agent_names=["claude"],
            )

    runner.stream_interactive.assert_not_called()


def test_run_sequential_skip_ready_runs_even_when_cli_missing(tmp_path):
    runner = MagicMock()
    runner.stream_interactive.return_value = 0

    with patch("trinity.providers.bootstrap.shutil.which", return_value=None):
        result = ProviderBootstrapper(runner=runner).run_sequential(
            _config(tmp_path),
            agent_names=["claude"],
            skip_ready=True,
        )

    runner.stream_interactive.assert_called_once()
    assert result.checks["claude"].installed is False
    assert result.exit_codes == {"claude": 0}


def test_run_sequential_stops_on_first_failure_by_default(tmp_path):
    runner = MagicMock()
    runner.stream_interactive.return_value = 2

    with patch("trinity.providers.bootstrap.shutil.which", return_value="/bin/claude"):
        with pytest.raises(ProviderBootstrapError, match="exited with code 2"):
            ProviderBootstrapper(runner=runner).run_sequential(
                _config(tmp_path),
                agent_names=["claude"],
            )


def test_run_sequential_continue_on_error_records_failure(tmp_path):
    runner = MagicMock()
    runner.stream_interactive.return_value = 2

    with patch("trinity.providers.bootstrap.shutil.which", return_value="/bin/claude"):
        result = ProviderBootstrapper(runner=runner).run_sequential(
            _config(tmp_path),
            agent_names=["claude"],
            continue_on_error=True,
        )

    assert result.exit_codes == {"claude": 2}
    assert result.failed_agents == ("claude",)


def test_launch_session_sends_commands_to_tmux_panes(tmp_path):
    config = _config(tmp_path)
    pane = MagicMock()
    manager = MagicMock()
    manager.session_exists.return_value = False
    manager.get_pane.return_value = pane

    with patch("trinity.providers.bootstrap.TmuxSessionManager", return_value=manager):
        result = ProviderBootstrapper().launch_session(
            config,
            agent_names=["claude"],
            session_name="bootstrap-test",
        )

    manager.create_session.assert_called_once()
    pane.send_text.assert_called_once()
    sent_command = pane.send_text.call_args.args[0]
    assert "HOME=" in sent_command
    assert "claude --dangerously-skip-permissions" in sent_command
    assert result.session_name == "bootstrap-test"
    assert result.commands["claude"] == sent_command


def test_launch_session_refuses_existing_session_without_force(tmp_path):
    manager = MagicMock()
    manager.session_exists.return_value = True

    with patch("trinity.providers.bootstrap.TmuxSessionManager", return_value=manager):
        with pytest.raises(ProviderBootstrapError, match="already exists"):
            ProviderBootstrapper().launch_session(_config(tmp_path))

    manager.create_session.assert_not_called()
