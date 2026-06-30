from __future__ import annotations

import json
import os

import pytest

from tests.harness.fake_providers import (
    _windows_wrapper_script,
    install_fake_provider_clis,
    provider_calls,
    run_fake_cli,
)
from trinity.agents.base import AgentWrapper
from trinity.config import TrinityConfig
from trinity.models import (
    AgentSpec,
    ContextUsage,
    DeliberationMessage,
    Provider,
    ResponseStatus,
)
from trinity.orchestrator import TrinityOrchestrator
from trinity.providers.invoker import (
    AntigravityPrintInvoker,
    ClaudePrintInvoker,
    CodexExecInvoker,
    PromptRequest,
)
from trinity.providers.model_discovery import (
    clear_model_discovery_cache,
    discover_provider_models,
)
from trinity.providers.policy import InvocationAccess
from trinity.providers.readiness import OneShotProviderPreflight, ProviderState


class FakeAgent(AgentWrapper):
    def __init__(
        self,
        provider: Provider,
        cli_command: str,
        *,
        model: str = "default",
        name: str = "agent",
    ) -> None:
        super().__init__(
            AgentSpec(
                name=name,
                provider=provider,
                cli_command=cli_command,
                model=model,
            )
        )

    async def start(self, initial_prompt: str = "") -> None:
        pass

    async def send_and_wait(
        self, prompt: str, timeout: float = 300.0, access=None
    ) -> DeliberationMessage:
        raise NotImplementedError

    async def get_context_usage(self) -> ContextUsage:
        return self.context_usage

    async def is_alive(self) -> bool:
        return True

    async def graceful_shutdown(self) -> None:
        pass


def test_fake_provider_clis_use_platform_executable_names(tmp_path) -> None:
    fake = install_fake_provider_clis(tmp_path / "fake-providers")

    expected_suffix = ".cmd" if os.name == "nt" else ""
    assert fake.claude.name == f"claude{expected_suffix}"
    assert fake.codex.name == f"codex{expected_suffix}"
    assert fake.agy.name == f"agy{expected_suffix}"


def test_windows_fake_provider_wrapper_invokes_python_script() -> None:
    script = _windows_wrapper_script("codex.py")

    assert '"%~dp0codex.py" %*' in script
    assert "exit /b %ERRORLEVEL%" in script


def test_fake_provider_clis_support_versions_and_model_discovery(tmp_path) -> None:
    fake = install_fake_provider_clis(tmp_path / "fake-providers")
    env = fake.env()

    for executable, label in (
        (fake.claude, "claude fake-cli"),
        (fake.codex, "codex fake-cli"),
        (fake.agy, "agy fake-cli"),
    ):
        completed = run_fake_cli([str(executable), "--version"], cwd=tmp_path, env=env)
        assert completed.returncode == 0
        assert label in completed.stdout

    def discovery_runner(argv, timeout_seconds):
        return run_fake_cli(
            list(argv),
            cwd=tmp_path,
            env=env,
            timeout_seconds=timeout_seconds,
        )

    clear_model_discovery_cache()
    codex_choices = discover_provider_models(
        Provider.CODEX,
        str(fake.codex),
        use_cache=False,
        runner=discovery_runner,
    )
    agy_choices = discover_provider_models(
        Provider.ANTIGRAVITY_CLI,
        str(fake.agy),
        use_cache=False,
        runner=discovery_runner,
    )

    assert [choice.model for choice in codex_choices[:3]] == [
        "default",
        "gpt-5",
        "gpt-5.5",
    ]
    assert codex_choices[1].source == "cli-live"
    assert [choice.model for choice in agy_choices[:3]] == [
        "default",
        "Gemini 3.5 Flash (Medium)",
        "GPT-OSS 120B (Medium)",
    ]
    assert agy_choices[1].source == "cli-live"


def test_fake_provider_clis_drive_real_one_shot_preflight(tmp_path) -> None:
    fake = install_fake_provider_clis(tmp_path / "fake-providers")
    agent = FakeAgent(
        Provider.CODEX,
        str(fake.codex),
        model="gpt-5",
        name="codex",
    )
    agent.configure_launch(cwd=tmp_path, env_overrides=fake.env())

    result = OneShotProviderPreflight(
        timeout_seconds=5.0,
        use_model_cache=False,
    ).check(agent)

    assert result.ready is True
    assert result.state == ProviderState.READY
    assert result.discovered_models == ("gpt-5", "gpt-5.5")
    assert result.model_source == "cli-live"
    codex_calls = provider_calls(fake.read_calls(), "codex")
    assert [call["argv"] for call in codex_calls] == [
        ["--version"],
        ["debug", "models"],
    ]


def test_fake_provider_mode_can_reproduce_one_shot_preflight_probe_failure(tmp_path) -> None:
    fake = install_fake_provider_clis(tmp_path / "fake-providers")
    agent = FakeAgent(Provider.CODEX, str(fake.codex), name="codex")
    agent.configure_launch(
        cwd=tmp_path,
        env_overrides=fake.env(TRINITY_FAKE_CODEX_MODE="probe_exit1"),
    )

    result = OneShotProviderPreflight(
        timeout_seconds=5.0,
        use_model_cache=False,
    ).check(agent)

    assert result.ready is False
    assert result.state == ProviderState.CLI_PROBE_FAILED
    assert result.probe_returncode == 1
    assert "sign in" in result.excerpt


@pytest.mark.asyncio
async def test_fake_provider_clis_drive_one_shot_invokers(tmp_path) -> None:
    fake = install_fake_provider_clis(tmp_path / "fake-providers")
    env = fake.env()

    claude_result = await ClaudePrintInvoker().invoke(
        PromptRequest(
            agent_name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command=str(fake.claude),
            prompt="Design a test plan.",
            cwd=tmp_path,
            env=env,
            model="opus[1m]",
        )
    )
    codex_result = await CodexExecInvoker().invoke(
        PromptRequest(
            agent_name="codex",
            provider=Provider.CODEX,
            cli_command=str(fake.codex),
            prompt="Implement a test plan.",
            cwd=tmp_path,
            env=env,
            model="gpt-5",
        )
    )
    agy_result = await AntigravityPrintInvoker().invoke(
        PromptRequest(
            agent_name="antigravity",
            provider=Provider.ANTIGRAVITY_CLI,
            cli_command=str(fake.agy),
            prompt="Review a test plan.",
            cwd=tmp_path,
            env=env,
            extra_args=("--log-file", str(tmp_path / "agy.log")),
        )
    )

    assert claude_result.status == ResponseStatus.OK
    assert codex_result.status == ResponseStatus.OK
    assert agy_result.status == ResponseStatus.OK
    assert json.loads(claude_result.content)["vote"] == "APPROVE"
    assert json.loads(codex_result.content)["blueprint"]["work_packages"][0]["owner_agent"] == "codex"
    assert json.loads(agy_result.content)["blueprint"]["work_packages"][0]["owner_agent"] == "antigravity"
    assert claude_result.metadata["provider_session"]["provider_session_id"] == "fake-claude-session"
    assert codex_result.metadata["provider_session"]["provider_session_id"] == "fake-codex-thread"
    assert agy_result.metadata["provider_session"]["provider_session_id"] == "fake-agy-conversation"

    calls = fake.read_calls()
    assert [call["provider"] for call in calls] == ["claude", "codex", "agy"]
    assert "Implement a test plan." in provider_calls(calls, "codex")[0]["stdin"]


@pytest.mark.asyncio
async def test_fake_provider_invocation_uses_selected_target_workspace_cwd(
    tmp_path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "Trinity"
    target_workspace = tmp_path / "customer-app"
    control_repo.mkdir()
    target_workspace.mkdir()
    fake = install_fake_provider_clis(tmp_path / "fake-providers")
    monkeypatch.setenv("TRINITY_FAKE_PROVIDER_LOG", str(fake.calls_log))
    config = TrinityConfig(
        project_dir=control_repo,
        state_dir=control_repo / ".trinity",
        agents={
            "codex": AgentSpec(
                name="codex",
                provider=Provider.CODEX,
                cli_command=str(fake.codex),
                model="gpt-5",
                enabled=True,
            ),
        },
    )
    orchestrator = TrinityOrchestrator(
        config,
        target_workspace=target_workspace,
        active_agent_names=("codex",),
    )
    orchestrator._ensure_initialized()
    agent = orchestrator.agents["codex"]

    assert orchestrator.get_agent_cwd("codex") == target_workspace.resolve()
    assert agent.launch_cwd == target_workspace.resolve()

    await agent.start("Selected workspace smoke context.")
    message = await agent.send_and_wait(
        "Inspect the selected workspace.",
        timeout=5.0,
        access=InvocationAccess.WORKSPACE_WRITE,
    )

    assert message.metadata["response_status"] == ResponseStatus.OK.value
    codex_calls = provider_calls(fake.read_calls(), "codex")
    assert len(codex_calls) == 1
    call = codex_calls[0]
    argv = [str(item) for item in call["argv"]]
    cd_index = argv.index("--cd")
    assert call["cwd"] == str(target_workspace.resolve())
    assert call["cwd"] != str(control_repo.resolve())
    assert argv[cd_index + 1] == str(target_workspace.resolve())
    assert "Selected workspace smoke context." in str(call["stdin"])
    assert "Inspect the selected workspace." in str(call["stdin"])
