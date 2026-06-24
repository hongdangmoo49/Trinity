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
from trinity.prompts.context_projection import (
    agent_context_profile,
    render_context_projection_block,
)
from trinity.tui.events import TUIEventType
from trinity.workflow import (
    ExecutionProtocol,
    ExecutionResult,
    ReviewExecutionProtocol,
    ReviewPackage,
    ReviewStatus,
    WorkPackage,
    WorkStatus,
)


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


def test_context_projection_prompt_helper_renders_profile_block(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    shared.initialize("Ship workflow", ["codex"])
    shared.append_to_section("Task Results", "WP-001 done.")

    block = render_context_projection_block(
        shared,
        "implementer",
        heading="[Context Projection]",
    )

    assert block.startswith("[Context Projection]\n")
    assert "Profile: implementer" in block
    assert "Task Results" in block
    assert "WP-001 done." in block


def test_agent_context_profile_defaults_to_balanced() -> None:
    assert agent_context_profile({}, "missing") == "balanced"


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


@pytest.mark.asyncio
async def test_review_prompt_includes_agent_context_profile(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    shared.initialize("Review routing", ["claude"])
    shared.append_to_section("Task Results", "WP-001 changed routing files.")
    agent = AsyncMock()
    agent.spec = AgentSpec(
        name="claude",
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        profile=AgentProfile(
            mission="Reviewer",
            strengths={"review": 1.0},
            supported_turn_modes=["review"],
            context_profile="reviewer",
        ),
    )
    agent.send_and_wait.return_value = DeliberationMessage(
        source="claude",
        target="all",
        round_num=0,
        role=MessageRole.TASK,
        content=(
            "REVIEW STATUS: APPROVED\n"
            "SEVERITY: LOW\n\n"
            "SUMMARY:\n"
            "Looks good.\n\n"
            "FINDINGS:\n"
            "- none\n\n"
            "REQUIRED CHANGES:\n"
            "- none\n"
        ),
        metadata={"raw_output": "REVIEW STATUS: APPROVED\nSUMMARY:\nLooks good."},
    )
    protocol = ReviewExecutionProtocol(
        agents={"claude": agent},
        shared=shared,
        artifact_dir=tmp_path / "reviews",
    )

    results = await protocol.review_work_packages(
        [
            ReviewPackage(
                package_id="WP-001",
                reviewer_agent="claude",
                target_agent="codex",
            )
        ],
        [
            WorkPackage(
                id="WP-001",
                title="Routing",
                owner_agent="codex",
                objective="Implement routing.",
            )
        ],
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="Changed routing.",
            )
        ],
    )

    prompt = agent.send_and_wait.call_args.args[0]
    assert results[0].status == ReviewStatus.APPROVED
    assert "Context Projection:" in prompt
    assert "Profile: reviewer" in prompt
    assert "WP-001 changed routing files." in prompt
