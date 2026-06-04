"""Tests for workflow execution protocol."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from trinity.context.shared import SharedContextEngine
from trinity.models import DeliberationMessage, MessageRole, ResponseStatus
from trinity.providers.policy import InvocationAccess
from trinity.tui.events import TUIEventType
from trinity.workflow import ExecutionProtocol, WorkPackage, WorkStatus


def _message(content: str, metadata: dict | None = None) -> DeliberationMessage:
    return DeliberationMessage(
        source="codex",
        target="all",
        round_num=0,
        role=MessageRole.TASK,
        content=content,
        metadata={"raw_output": content, **(metadata or {})},
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
    progress = []
    protocol = ExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "execution",
        event_callback=events.append,
        result_callback=progress.append,
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
    assert progress == [result]
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
    assert "Estimated Weight: 1" in sent_prompt
    assert "[Workspace Boundary]" in sent_prompt
    assert "Do not switch branches, merge, commit, or push" in sent_prompt
    assert "[Subagent Delegation Policy]" in sent_prompt
    assert "## Subtasks" in sent_prompt
    assert agent.send_and_wait.call_args.kwargs["access"] == (
        InvocationAccess.WORKSPACE_WRITE
    )
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
async def test_execution_protocol_marks_non_ok_provider_status_failed(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    agent.send_and_wait.return_value = _message(
        "[Error: exit code 1]",
        metadata={"response_status": ResponseStatus.AUTH_REQUIRED.value},
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

    assert results[0].status == WorkStatus.FAILED
    assert results[0].summary == "[Error: exit code 1]"
    assert package.status == WorkStatus.FAILED


@pytest.mark.asyncio
async def test_execution_protocol_falls_back_after_owner_failure(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    gemini = AsyncMock()
    codex = AsyncMock()
    gemini.send_and_wait.return_value = _message(
        "[Timeout after 300.0s]",
        metadata={"error": "timeout"},
    )
    codex.send_and_wait.return_value = _message(
        "## Completed\n"
        "- Fallback implementation complete\n\n"
        "## Files Changed\n"
        "- src/routes.py\n\n"
        "## Blockers\n"
        "- none\n"
    )
    events = []
    package = WorkPackage(
        id="WP-001",
        title="fallback package",
        owner_agent="gemini",
        objective="Implement with fallback.",
    )
    protocol = ExecutionProtocol(
        agents={"gemini": gemini, "codex": codex},
        shared=shared,
        artifact_dir=tmp_path / "execution",
        event_callback=events.append,
    )

    results = await protocol.run([package])

    assert results[0].status == WorkStatus.DONE
    assert results[0].agent_name == "codex"
    assert results[0].summary == "Fallback implementation complete"
    assert gemini.send_and_wait.call_count == 1
    assert codex.send_and_wait.call_count == 1
    fallback_prompt = codex.send_and_wait.call_args.args[0]
    assert "Original owner: gemini" in fallback_prompt
    assert "Current executor: codex" in fallback_prompt
    assert [
        event.data.get("agent")
        for event in events
        if event.type == TUIEventType.WORK_PACKAGE_STARTED
    ] == ["gemini", "codex"]


@pytest.mark.asyncio
async def test_execution_protocol_falls_back_when_owner_missing(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    codex = AsyncMock()
    codex.send_and_wait.return_value = _message(
        "## Completed\n- Missing owner recovered\n\n## Blockers\n- none\n"
    )
    package = WorkPackage(
        id="WP-001",
        title="missing owner package",
        owner_agent="gemini",
        objective="Recover with available agent.",
    )
    protocol = ExecutionProtocol(
        agents={"codex": codex},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run([package])

    assert results[0].status == WorkStatus.DONE
    assert results[0].agent_name == "codex"
    codex.send_and_wait.assert_called_once()


@pytest.mark.asyncio
async def test_execution_protocol_runs_independent_packages_in_parallel(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    claude = AsyncMock()
    codex = AsyncMock()
    claude.launch_cwd = tmp_path / "worktrees" / "claude"
    codex.launch_cwd = tmp_path / "worktrees" / "codex"
    claude_started = asyncio.Event()
    codex_started = asyncio.Event()

    async def _claude_send(prompt: str, timeout: float, access=None):
        claude_started.set()
        assert access == InvocationAccess.WORKSPACE_WRITE
        await asyncio.wait_for(codex_started.wait(), timeout=0.5)
        return _message("## Completed\n- Claude done\n\n## Blockers\n- none\n")

    async def _codex_send(prompt: str, timeout: float, access=None):
        codex_started.set()
        assert access == InvocationAccess.WORKSPACE_WRITE
        await asyncio.wait_for(claude_started.wait(), timeout=0.5)
        return _message("## Completed\n- Codex done\n\n## Blockers\n- none\n")

    claude.send_and_wait.side_effect = _claude_send
    codex.send_and_wait.side_effect = _codex_send
    packages = [
        WorkPackage(
            id="WP-001",
            title="claude package",
            owner_agent="claude",
            objective="Plan implementation.",
        ),
        WorkPackage(
            id="WP-002",
            title="codex package",
            owner_agent="codex",
            objective="Implement feature.",
        ),
    ]
    protocol = ExecutionProtocol(
        agents={"claude": claude, "codex": codex},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run(packages)

    assert [result.status for result in results] == [WorkStatus.DONE, WorkStatus.DONE]
    assert [package.status for package in packages] == [WorkStatus.DONE, WorkStatus.DONE]
    assert claude.send_and_wait.call_count == 1
    assert codex.send_and_wait.call_count == 1


@pytest.mark.asyncio
async def test_execution_protocol_serializes_same_worktree_provider_writes(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    claude = AsyncMock()
    codex = AsyncMock()
    claude.launch_cwd = tmp_path
    codex.launch_cwd = tmp_path
    order: list[str] = []

    async def _claude_send(prompt: str, timeout: float, access=None):
        assert access == InvocationAccess.WORKSPACE_WRITE
        order.append("claude-start")
        await asyncio.sleep(0.01)
        order.append("claude-end")
        return _message("## Completed\n- Claude done\n\n## Blockers\n- none\n")

    async def _codex_send(prompt: str, timeout: float, access=None):
        assert access == InvocationAccess.WORKSPACE_WRITE
        order.append("codex-start")
        await asyncio.sleep(0.01)
        order.append("codex-end")
        return _message("## Completed\n- Codex done\n\n## Blockers\n- none\n")

    claude.send_and_wait.side_effect = _claude_send
    codex.send_and_wait.side_effect = _codex_send
    packages = [
        WorkPackage(
            id="WP-001",
            title="claude package",
            owner_agent="claude",
            objective="Implement shared file changes.",
        ),
        WorkPackage(
            id="WP-002",
            title="codex package",
            owner_agent="codex",
            objective="Implement shared file changes.",
        ),
    ]
    protocol = ExecutionProtocol(
        agents={"claude": claude, "codex": codex},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run(packages)

    assert [result.status for result in results] == [WorkStatus.DONE, WorkStatus.DONE]
    assert order == ["claude-start", "claude-end", "codex-start", "codex-end"]


@pytest.mark.asyncio
async def test_execution_protocol_allows_disjoint_expected_files_same_worktree(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    claude = AsyncMock()
    codex = AsyncMock()
    claude.launch_cwd = tmp_path
    codex.launch_cwd = tmp_path
    claude_started = asyncio.Event()
    codex_started = asyncio.Event()

    async def _claude_send(prompt: str, timeout: float, access=None):
        claude_started.set()
        assert access == InvocationAccess.WORKSPACE_WRITE
        await asyncio.wait_for(codex_started.wait(), timeout=0.5)
        return _message("## Completed\n- Claude done\n\n## Blockers\n- none\n")

    async def _codex_send(prompt: str, timeout: float, access=None):
        codex_started.set()
        assert access == InvocationAccess.WORKSPACE_WRITE
        await asyncio.wait_for(claude_started.wait(), timeout=0.5)
        return _message("## Completed\n- Codex done\n\n## Blockers\n- none\n")

    claude.send_and_wait.side_effect = _claude_send
    codex.send_and_wait.side_effect = _codex_send
    packages = [
        WorkPackage(
            id="WP-001",
            title="claude package",
            owner_agent="claude",
            objective="Implement config changes.",
            expected_files=["src/trinity/config.py"],
        ),
        WorkPackage(
            id="WP-002",
            title="codex package",
            owner_agent="codex",
            objective="Implement config tests.",
            expected_files=["tests/test_config.py"],
        ),
    ]
    protocol = ExecutionProtocol(
        agents={"claude": claude, "codex": codex},
        shared=shared,
        artifact_dir=tmp_path / "execution",
    )

    results = await protocol.run(packages)

    assert [result.status for result in results] == [WorkStatus.DONE, WorkStatus.DONE]
    assert claude.send_and_wait.call_count == 1
    assert codex.send_and_wait.call_count == 1


@pytest.mark.asyncio
async def test_execution_protocol_blocks_unfinished_dependencies(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    agent.send_and_wait.return_value = _message(
        "[Error: exit code 1]",
        metadata={"response_status": ResponseStatus.INVALID.value},
    )
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
    agent.send_and_wait.assert_called_once()
