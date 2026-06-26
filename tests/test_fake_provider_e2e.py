from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from tests.harness.fake_providers import install_fake_provider_clis, provider_calls
from trinity.agents.base import AgentWrapper
from trinity.cli import main
from trinity.config import TrinityConfig
from trinity.models import (
    AgentSpec,
    ConsensusResult,
    ContextUsage,
    DeliberationMessage,
    DeliberationResult,
    Provider,
    ResponseStatus,
)
from trinity.providers.invoker import CodexExecInvoker, PromptRequest
from trinity.providers.readiness import OneShotProviderPreflight, ProviderState
from trinity.tui.report import DeliberationReportBuilder
from trinity.workflow import (
    ArchitectureComponent,
    Blueprint,
    ExecutionResult,
    WorkPackage,
    WorkStatus,
    WorkflowEngine,
    WorkflowState,
)


class FakeAgent(AgentWrapper):
    def __init__(self, cli_command: str) -> None:
        super().__init__(
            AgentSpec(
                name="codex",
                provider=Provider.CODEX,
                cli_command=cli_command,
                model="gpt-5",
            )
        )

    async def start(self, initial_prompt: str = "") -> None:
        pass

    async def send_and_wait(
        self,
        prompt: str,
        timeout: float = 300.0,
        access=None,
    ) -> DeliberationMessage:
        raise NotImplementedError

    async def get_context_usage(self) -> ContextUsage:
        return self.context_usage

    async def is_alive(self) -> bool:
        return True

    async def graceful_shutdown(self) -> None:
        pass


@pytest.mark.asyncio
async def test_fake_provider_account_free_workflow_retry_report_e2e(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    fake = install_fake_provider_clis(tmp_path / "fake-providers")

    monkeypatch.chdir(project_dir)
    init_result = CliRunner().invoke(
        main,
        ["init", "--non-interactive"],
        env=fake.env(),
    )

    assert init_result.exit_code == 0
    config = TrinityConfig.load(project_dir / ".trinity" / "trinity.config")
    assert config.effective_state_dir == project_dir / ".trinity"

    agent = FakeAgent(str(fake.codex))
    agent.configure_launch(cwd=project_dir, env_overrides=fake.env())
    readiness = OneShotProviderPreflight(
        timeout_seconds=5.0,
        use_model_cache=False,
    ).check(agent)

    assert readiness.ready is True
    assert readiness.state == ProviderState.READY
    assert "gpt-5" in readiness.discovered_models

    invoke_result = await CodexExecInvoker().invoke(
        PromptRequest(
            agent_name="codex",
            provider=Provider.CODEX,
            cli_command=str(fake.codex),
            prompt="Build a deterministic fake-provider E2E workflow.",
            cwd=project_dir,
            env=fake.env(),
            model="gpt-5",
        )
    )

    assert invoke_result.status == ResponseStatus.OK
    fake_payload = json.loads(invoke_result.content)
    assert fake_payload["blueprint"]["work_packages"][0]["owner_agent"] == "codex"

    engine = WorkflowEngine(config.effective_state_dir)
    engine.start("Build a deterministic fake-provider E2E workflow.", ["codex"])
    package = WorkPackage(
        id="WP-001",
        title="fake provider package",
        owner_agent="codex",
        objective="Exercise fake provider execution, retry, and reporting.",
        expected_files=["fake_e2e.txt"],
        acceptance_criteria=["Report includes retry and completion events."],
    )
    engine.session.blueprint = Blueprint(
        title="Fake Provider E2E",
        summary="Account-free workflow smoke path.",
        architecture=[
            ArchitectureComponent(
                name="FakeProviderHarness",
                responsibility="Drive provider contracts without credentials.",
                owner_agent="codex",
            )
        ],
        acceptance_criteria=["Retry path is visible in the report."],
        work_packages=[package],
    )
    engine.session.work_packages = [package]
    engine.set_target_workspace(project_dir / "target")
    engine.begin_execution()
    engine.record_work_package_started("WP-001", "codex", occurred_at=1710000000.0)
    engine.record_work_package_completed(
        "WP-001",
        "codex",
        status=WorkStatus.FAILED.value,
        summary="First fake execution failed.",
        occurred_at=1710000001.0,
    )

    retry_plan = engine.prepare_execution_retry("all")
    assert retry_plan.selected == ("WP-001",)
    assert engine.session.execution_run["state"] == "retry_requested"

    engine.begin_execution()
    engine.record_work_package_started("WP-001", "codex", occurred_at=1710000002.0)
    engine.record_work_package_completed(
        "WP-001",
        "codex",
        status=WorkStatus.DONE.value,
        summary="Fake provider E2E completed after retry.",
        occurred_at=1710000003.0,
    )
    engine.session.execution_results = [
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.DONE,
            summary="Fake provider E2E completed after retry.",
            files_changed=["fake_e2e.txt"],
        )
    ]
    engine.set_state(WorkflowState.DONE, reason="fake provider E2E complete")
    engine.save()

    report = DeliberationReportBuilder(
        engine.session,
        DeliberationResult(
            user_prompt=engine.session.goal,
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"codex": "approve"},
                summary="Fake provider E2E path completed.",
            ),
        ),
        events=engine.persistence.load_events(),
    ).build()
    markdown = report.to_markdown()

    assert "Fake Provider E2E" in markdown
    assert "work_package_retry_requested" in markdown
    assert "Fake provider E2E completed after retry" in markdown
    codex_calls = provider_calls(fake.read_calls(), "codex")
    assert [call["provider"] for call in codex_calls] == [
        "codex",
        "codex",
        "codex",
    ]
