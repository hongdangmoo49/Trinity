"""Tests for workflow execution protocol."""

from unittest.mock import AsyncMock

import pytest

from trinity.context.shared import SharedContextEngine
from trinity.models import DeliberationMessage, MessageRole
from trinity.tui.events import TUIEventType
from trinity.workflow import ExecutionProtocol, WorkPackage, WorkStatus


def _message(content: str) -> DeliberationMessage:
    return DeliberationMessage(
        source="codex",
        target="all",
        round_num=0,
        role=MessageRole.TASK,
        content=content,
        metadata={"raw_output": content},
    )


@pytest.mark.asyncio
async def test_execution_protocol_dispatches_package_and_records_result(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    shared.initialize("Implement routing", ["codex"])
    agent = AsyncMock()
    agent.send_and_wait.return_value = _message(
        "## Completed\n"
        "- Added routing service\n\n"
        "## Files Changed\n"
        "- src/routes.py\n"
        "- tests/test_routes.py\n\n"
        "## Decisions Made\n"
        "- Keep scoring deterministic\n\n"
        "## Blockers\n"
        "- none\n\n"
        "## Follow-up\n"
        "- Review latency thresholds\n"
    )
    events = []
    protocol = ExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "execution",
        event_callback=events.append,
    )
    package = WorkPackage(
        id="WP-001",
        title="codex package",
        owner_agent="codex",
        objective="Implement route service.",
        scope=["Route service"],
        expected_files=["src/routes.py"],
        acceptance_criteria=["Tests pass"],
    )

    results = await protocol.run([package])

    assert len(results) == 1
    result = results[0]
    assert result.status == WorkStatus.DONE
    assert result.summary == "Added routing service"
    assert result.files_changed == ["src/routes.py", "tests/test_routes.py"]
    assert result.decisions_made[0].decision == "Keep scoring deterministic"
    assert result.follow_up == ["Review latency thresholds"]
    assert result.raw_response_path is not None
    assert result.raw_response_path.exists()
    assert package.status == WorkStatus.DONE

    sent_prompt = agent.send_and_wait.call_args.args[0]
    assert "TRINITY_EXECUTION_START" in sent_prompt
    assert "[Work Package]" in sent_prompt
    assert "ID: WP-001" in sent_prompt
    assert "[Subagent Delegation Policy]" in sent_prompt
    assert "## Subtasks" in sent_prompt
    task_results = shared.read_section("Task Results")
    assert task_results is not None
    assert "WP-001 / codex" in task_results
    assert "src/routes.py" in task_results
    assert [event.type for event in events] == [
        TUIEventType.EXECUTION_START,
        TUIEventType.WORK_PACKAGE_STARTED,
        TUIEventType.WORK_PACKAGE_COMPLETED,
        TUIEventType.EXECUTION_DONE,
    ]


@pytest.mark.asyncio
async def test_execution_protocol_parses_and_records_subtasks(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    agent.send_and_wait.return_value = _message(
        "## Completed\n"
        "- Implemented routing adapter\n\n"
        "## Blockers\n"
        "- none\n\n"
        "## Subtasks\n"
        "### ST-001\n"
        "- delegated_to: code-search tool\n"
        "- objective: Find existing route adapter patterns\n"
        "- result_summary: Found adapter and test layout\n"
        "- status: done\n"
        "- decisions_made: Reuse existing adapter registry\n"
        "- files_changed: src/routes.py, tests/test_routes.py\n"
        "- unresolved_issues: none\n"
    )
    package = WorkPackage(
        id="WP-001",
        title="codex package",
        owner_agent="codex",
        objective="Implement routing adapter.",
    )
    protocol = ExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run([package])

    assert len(results[0].subtasks) == 1
    subtask = results[0].subtasks[0]
    assert subtask.id == "ST-001"
    assert subtask.parent_package_id == "WP-001"
    assert subtask.parent_agent == "codex"
    assert subtask.delegated_to == "code-search tool"
    assert subtask.objective == "Find existing route adapter patterns"
    assert subtask.result_summary == "Found adapter and test layout"
    assert subtask.status == WorkStatus.DONE
    assert subtask.decisions_made == ["Reuse existing adapter registry"]
    assert subtask.files_changed == ["src/routes.py", "tests/test_routes.py"]

    subtasks = shared.read_section("Subtasks")
    assert subtasks is not None
    assert "ST-001 / WP-001" in subtasks
    assert "code-search tool" in subtasks
    assert "Found adapter and test layout" in subtasks


@pytest.mark.asyncio
async def test_execution_protocol_marks_blockers(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    agent.send_and_wait.return_value = _message(
        "## Completed\n"
        "- Started implementation\n\n"
        "## Blockers\n"
        "- Missing API key\n"
    )
    package = WorkPackage(
        id="WP-001",
        title="codex package",
        owner_agent="codex",
        objective="Implement.",
    )
    protocol = ExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run([package])

    assert results[0].status == WorkStatus.BLOCKED
    assert results[0].blockers == ["Missing API key"]
    assert package.status == WorkStatus.BLOCKED


@pytest.mark.asyncio
async def test_execution_protocol_skips_design_only_packages(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    package = WorkPackage(
        id="WP-001",
        title="plan package",
        owner_agent="codex",
        objective="Plan only.",
        requires_execution=False,
    )
    protocol = ExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run([package])

    assert results == []
    agent.send_and_wait.assert_not_called()


@pytest.mark.asyncio
async def test_execution_protocol_blocks_unfinished_dependencies(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    first = WorkPackage(
        id="WP-001",
        title="first",
        owner_agent="missing",
        objective="Missing owner.",
    )
    second = WorkPackage(
        id="WP-002",
        title="second",
        owner_agent="codex",
        objective="Depends on first.",
        dependencies=["WP-001"],
    )
    protocol = ExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run([first, second])

    assert results[0].status == WorkStatus.FAILED
    assert results[1].status == WorkStatus.BLOCKED
    assert "WP-001" in results[1].blockers[0]
    agent.send_and_wait.assert_not_called()
