"""Tests for role-aware context projection profiles."""

from unittest.mock import AsyncMock

import pytest

from trinity.context.profiles import project_shared_context
from trinity.context.shared import SharedContextEngine
from trinity.models import (
    AgentProfile,
    AgentSpec,
    DeliberationMessage,
    MessageRole,
    Provider,
)
from trinity.tui.events import TUIEventType
from trinity.workflow import ExecutionProtocol, WorkPackage, WorkStatus


def test_project_shared_context_selects_profile_sections(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    shared.initialize("Ship workflow", ["codex"])
    shared.append_to_section("Agreed Conclusion", "Implement the execution path.")
    shared.append_to_section("Task Results", "WP-001 done.")
    shared.append_to_section("Response Diagnostics", "Noisy prompt ignored.")

    projection = project_shared_context(shared, "reviewer")

    assert projection.profile_id == "reviewer"
    assert "Agreed Conclusion" in projection.sections
    assert "Task Results" in projection.sections
    assert "Response Diagnostics" in projection.sections
    assert "Implement the execution path." in projection.text


@pytest.mark.asyncio
async def test_execution_prompt_includes_agent_context_profile(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    shared.initialize("Implement routing", ["codex"])
    shared.append_to_section("Task Results", "Earlier package completed.")
    agent = AsyncMock()
    agent.spec = AgentSpec(
        name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        profile=AgentProfile(
            mission="Implementer",
            strengths={"implementation": 1.0},
            supported_turn_modes=["execute"],
            context_profile="implementer",
        ),
    )
    agent.send_and_wait.return_value = DeliberationMessage(
        source="codex",
        target="all",
        round_num=0,
        role=MessageRole.TASK,
        content="## Completed\n- Done\n\n## Blockers\n- none\n",
        metadata={"raw_output": "## Completed\n- Done\n\n## Blockers\n- none\n"},
    )
    events = []
    protocol = ExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "execution",
        event_callback=events.append,
    )

    results = await protocol.run(
        [
            WorkPackage(
                id="WP-001",
                title="Routing",
                owner_agent="codex",
                objective="Implement routing.",
            )
        ]
    )

    prompt = agent.send_and_wait.call_args.args[0]
    assert results[0].status == WorkStatus.DONE
    assert "[Context Projection]" in prompt
    assert "Profile: implementer" in prompt
    assert "Earlier package completed." in prompt
    started_event = next(
        event for event in events if event.type == TUIEventType.WORK_PACKAGE_STARTED
    )
    assert started_event.data["context_profile"] == "implementer"
