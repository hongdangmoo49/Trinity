"""Tests for provider readiness classification."""

import json
import subprocess

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, Provider
from trinity.providers.readiness import (
    OneShotProviderPreflight,
    ProviderReadinessGate,
    ProviderState,
)


class FakePane:
    def __init__(self, lines: list[str], alive: bool = True):
        self.lines = lines
        self.alive = alive

    def capture(self, lines: int = -80) -> list[str]:
        return self.lines

    def is_alive(self) -> bool:
        return self.alive


class FakeAgent(AgentWrapper):
    def __init__(
        self,
        provider: Provider,
        lines: list[str],
        alive: bool = True,
        name: str = "agent",
    ):
        super().__init__(
            AgentSpec(
                name=name,
                provider=provider,
                cli_command=provider.value,
            )
        )
        self.pane = FakePane(lines, alive=alive)

    async def start(self, initial_prompt: str = "") -> None:
        pass

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        raise NotImplementedError

    async def get_context_usage(self) -> ContextUsage:
        return self.context_usage

    async def is_alive(self) -> bool:
        return True

    async def graceful_shutdown(self) -> None:
        pass


class FakePrintAgent(AgentWrapper):
    def __init__(
        self,
        provider: Provider,
        cli_command: str,
        *,
        model: str = "default",
        extra_args: list[str] | None = None,
        name: str = "agent",
    ):
        super().__init__(
            AgentSpec(
                name=name,
                provider=provider,
                cli_command=cli_command,
                model=model,
                extra_args=extra_args or [],
            )
        )

    async def start(self, initial_prompt: str = "") -> None:
        pass

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0, access=None
    ) -> DeliberationMessage:
        raise NotImplementedError

    async def get_context_usage(self) -> ContextUsage:
        return self.context_usage

    async def is_alive(self) -> bool:
        return True

    async def graceful_shutdown(self) -> None:
        pass


class FakeProcessRunner:
    def __init__(
        self,
        responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]] | None = None,
        exceptions: dict[tuple[str, ...], Exception] | None = None,
    ):
        self.responses = responses or {}
        self.exceptions = exceptions or {}
        self.calls: list[tuple[str, ...]] = []

    def run(self, command):
        argv = tuple(str(item) for item in command.argv)
        self.calls.append(argv)
        if argv in self.exceptions:
            raise self.exceptions[argv]
        return self.responses.get(
            argv,
            subprocess.CompletedProcess(
                args=list(argv),
                returncode=0,
                stdout="ok\n",
                stderr="",
            ),
        )


def _completed(
    argv: tuple[str, ...],
    *,
    stdout: str = "ok\n",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=list(argv),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_one_shot_preflight_rejects_missing_cwd(tmp_path):
    cli = tmp_path / "codex"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")
    agent = FakePrintAgent(Provider.CODEX, str(cli), name="codex")
    agent.configure_launch(cwd=tmp_path / "missing")
    runner = FakeProcessRunner()

    result = OneShotProviderPreflight(
        runner=runner,
        use_model_cache=False,
    ).check(agent)

    assert result.ready is False
    assert result.state == ProviderState.CWD_INACCESSIBLE
    assert "does not exist" in result.reason
    assert runner.calls == []


def test_one_shot_preflight_distinguishes_missing_cli(tmp_path):
    agent = FakePrintAgent(
        Provider.CODEX,
        "trinity-definitely-missing-provider-cli",
        name="codex",
    )
    agent.configure_launch(cwd=tmp_path)
    runner = FakeProcessRunner()

    result = OneShotProviderPreflight(
        runner=runner,
        use_model_cache=False,
    ).check(agent)

    assert result.ready is False
    assert result.state == ProviderState.CLI_NOT_FOUND
    assert "was not found" in result.reason
    assert "Install" in result.action_hint
    assert runner.calls == []


def test_one_shot_preflight_reports_cli_probe_failure(tmp_path):
    cli = tmp_path / "codex"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")
    argv = (str(cli), "--version")
    agent = FakePrintAgent(Provider.CODEX, str(cli), name="codex")
    agent.configure_launch(cwd=tmp_path)

    result = OneShotProviderPreflight(
        runner=FakeProcessRunner(
            responses={
                argv: _completed(argv, stderr="runtime boom", returncode=2),
            }
        ),
        use_model_cache=False,
    ).check(agent)

    assert result.ready is False
    assert result.state == ProviderState.CLI_PROBE_FAILED
    assert result.probe_returncode == 2
    assert "runtime boom" in result.excerpt


def test_one_shot_preflight_rejects_unavailable_discoverable_model(tmp_path):
    cli = tmp_path / "codex"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")
    version_argv = (str(cli), "--version")
    models_argv = (str(cli), "debug", "models")
    agent = FakePrintAgent(
        Provider.CODEX,
        str(cli),
        model="gpt-missing",
        name="codex",
    )
    agent.configure_launch(cwd=tmp_path)

    result = OneShotProviderPreflight(
        runner=FakeProcessRunner(
            responses={
                version_argv: _completed(version_argv),
                models_argv: _completed(
                    models_argv,
                    stdout=json.dumps(
                        {"models": [{"slug": "gpt-5", "visibility": "list"}]}
                    ),
                ),
            }
        ),
        use_model_cache=False,
    ).check(agent)

    assert result.ready is False
    assert result.state == ProviderState.MODEL_UNAVAILABLE
    assert result.model_source == "cli-live"
    assert result.discovered_models == ("gpt-5",)
    assert "gpt-missing" in result.reason


def test_one_shot_preflight_allows_custom_model_when_discovery_is_static(tmp_path):
    cli = tmp_path / "claude"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")
    version_argv = (str(cli), "--version")
    agent = FakePrintAgent(
        Provider.CLAUDE_CODE,
        str(cli),
        model="custom-account-alias",
        name="claude",
    )
    agent.configure_launch(cwd=tmp_path)

    result = OneShotProviderPreflight(
        runner=FakeProcessRunner(
            responses={
                version_argv: _completed(version_argv),
            }
        ),
        use_model_cache=False,
    ).check(agent)

    assert result.ready is True
    assert result.model == "custom-account-alias"
    assert result.model_source == "static-fallback"
    assert "does not expose CLI model discovery" in result.model_source_reason


def test_one_shot_preflight_surfaces_permission_plan_diagnostics(tmp_path):
    cli = tmp_path / "codex"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")
    version_argv = (str(cli), "--version")
    models_argv = (str(cli), "debug", "models")
    agent = FakePrintAgent(
        Provider.CODEX,
        str(cli),
        extra_args=[
            "--sandbox",
            "danger-full-access",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ignore-rules",
        ],
        name="codex",
    )
    agent.configure_launch(cwd=tmp_path)

    result = OneShotProviderPreflight(
        runner=FakeProcessRunner(
            responses={
                version_argv: _completed(version_argv),
                models_argv: _completed(
                    models_argv,
                    stdout=json.dumps(
                        {"models": [{"slug": "gpt-5", "visibility": "list"}]}
                    ),
                ),
            }
        ),
        use_model_cache=False,
    ).check(agent)

    assert result.ready is True
    assert result.permission_args == ("--sandbox", "read-only", "--cd", str(tmp_path))
    assert result.permission_extra_args == ("--ignore-rules",)
    assert any("removed_controlled_arg:--sandbox" in item for item in result.permission_diagnostics)
    assert any("removed_dangerous_arg" in item for item in result.permission_diagnostics)


def test_claude_oauth_screen_is_auth_required():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Claude Code",
            "Open the following OAuth URL to authenticate:",
            "https://claude.ai/oauth/authorize?...",
            "Invalid code. Try again.",
        ],
        provider=Provider.CLAUDE_CODE,
        agent_name="claude",
    )

    assert result.ready is False
    assert result.state == ProviderState.AUTH_REQUIRED
    assert "authentication" in result.reason
    assert "trinity bootstrap --agents claude" in result.action_hint
    assert "OAuth" in result.excerpt


def test_claude_auth_and_trust_variants_are_classified():
    gate = ProviderReadinessGate()

    for line in (
        "Enter authorization code to continue",
        "You need to auth login before proceeding",
        "Error: requires authentication",
        "Select login method:",
        "Claude account with subscription",
    ):
        result = gate.classify_pane_state(
            ["Claude Code", line],
            provider=Provider.CLAUDE_CODE,
            agent_name="claude",
        )
        assert result.state == ProviderState.AUTH_REQUIRED

    result = gate.classify_pane_state(
        ["Do you trust the files in this folder?"],
        provider=Provider.CLAUDE_CODE,
        agent_name="claude",
    )
    assert result.state == ProviderState.WORKSPACE_TRUST_REQUIRED


def test_antigravity_auth_is_auth_required():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Welcome to Antigravity CLI",
            "Please sign in with your Google account",
        ],
        provider=Provider.ANTIGRAVITY_CLI,
        agent_name="antigravity",
    )

    assert result.ready is False
    assert result.state == ProviderState.AUTH_REQUIRED
    assert "Run `agy`" in result.action_hint


def test_codex_model_loading_banner_is_model_loading():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "model: loading   /model to change",
            "gpt-5.5 default",
            "/model to change",
            "/help for commands",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is False
    assert result.state == ProviderState.MODEL_LOADING
    assert "loading" in result.reason


def test_codex_ready_prompt_with_default_model_is_ready():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "model:     gpt-5.5   /model to change",
            "Tip: Build faster with Codex.",
            "› Run /review on my changes",
            "gpt-5.5 default …",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is True
    assert result.state == ProviderState.READY


def test_codex_ready_prompt_wins_over_stale_loading_scrollback():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "model: loading   /model to change",
            "directory: /home/zaemi/workspace/Trinity",
            "› Summarize recent",
            "gpt-5.5 default …",
            "Codex",
            "model:     gpt-5.5   /model to change",
            "directory: /home/zaemi/workspace/Trinity",
            "Tip: New Build faster with Codex.",
            "› Summarize recent",
            "gpt-5.5 default …",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is True
    assert result.state == ProviderState.READY


def test_codex_auth_and_process_variants_are_classified():
    gate = ProviderReadinessGate()

    for line in (
        "please login to use Codex",
        "Error: authentication required",
        "Please auth login to continue",
    ):
        result = gate.classify_pane_state(
            ["Codex", line],
            provider=Provider.CODEX,
            agent_name="codex",
        )
        assert result.state == ProviderState.AUTH_REQUIRED

    result = gate.classify_pane_state(
        ["process exited with code 1"],
        provider=Provider.CODEX,
        agent_name="codex",
    )
    assert result.state == ProviderState.PROCESS_DEAD


def test_ready_prompt_is_ready():
    gate = ProviderReadinessGate()

    for provider in Provider:
        result = gate.classify_pane_state(
            ["Welcome", ">"],
            provider=provider,
            agent_name=provider.value,
        )
        assert result.ready is True
        assert result.state == ProviderState.READY
        assert result.action_hint == ""


def test_cli_banner_without_prompt_is_banner_only():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "/model to change",
            "/help for commands",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is False
    assert result.state == ProviderState.CLI_BANNER_ONLY


def test_agent_with_dead_pane_is_process_dead():
    gate = ProviderReadinessGate()
    agent = FakeAgent(
        provider=Provider.CLAUDE_CODE,
        lines=[">"],
        alive=False,
        name="claude",
    )

    result = gate.check(agent)

    assert result.ready is False
    assert result.state == ProviderState.PROCESS_DEAD
    assert "Restart" in result.action_hint
