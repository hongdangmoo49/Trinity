"""Tests for ExecutionProtocol — dispatching work packages to agents."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from trinity.models import DeliberationMessage, MessageRole, WorkPackage, WorkStatus
from trinity.workflow.execution import ExecutionProtocol


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(name: str, response_text: str = "Work completed successfully."):
    """Create a mock AgentWrapper with the given *name* and *response_text*."""
    agent = MagicMock()
    agent.spec = MagicMock()
    agent.spec.name = name
    msg = DeliberationMessage(
        source=name,
        target="all",
        round_num=0,
        role=MessageRole.TASK,
        content=response_text,
    )
    agent.send_and_wait = AsyncMock(return_value=msg)
    return agent


def _make_package(agent_name: str) -> WorkPackage:
    """Create a minimal WorkPackage for testing."""
    return WorkPackage(
        id="WP-001",
        title="Test task",
        owner_agent=agent_name,
        objective="Implement the feature",
        scope=["API endpoint", "Unit tests"],
        acceptance_criteria=["Tests pass"],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent_alpha():
    return _make_agent("alpha", "## Completed\nFeature done.\n## Files Changed\n- src/api.py\n- tests/test_api.py")


@pytest.fixture()
def agent_beta():
    return _make_agent("beta", "## Completed\nTests written.\n## Files Changed\n- tests/test_beta.py")


@pytest.fixture()
def package_alpha():
    return _make_package("alpha")


@pytest.fixture()
def package_beta():
    return WorkPackage(
        id="WP-002",
        title="Beta task",
        owner_agent="beta",
        objective="Write tests",
        scope=["Integration tests"],
        acceptance_criteria=["Coverage > 80%"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio()
async def test_dispatch_single_package(agent_alpha, package_alpha):
    """One agent, one package — result status should be DONE."""
    protocol = ExecutionProtocol(agents={"alpha": agent_alpha})
    results = await protocol.run([package_alpha])

    assert len(results) == 1
    result = results[0]
    assert result.package_id == "WP-001"
    assert result.agent_name == "alpha"
    assert result.status == WorkStatus.DONE
    assert "src/api.py" in result.files_changed
    assert "tests/test_api.py" in result.files_changed
    agent_alpha.send_and_wait.assert_awaited_once()


@pytest.mark.asyncio()
async def test_dispatch_multiple_packages_parallel(agent_alpha, agent_beta, package_alpha, package_beta):
    """Two agents, two packages — both should complete."""
    protocol = ExecutionProtocol(
        agents={"alpha": agent_alpha, "beta": agent_beta}
    )
    results = await protocol.run([package_alpha, package_beta])

    assert len(results) == 2
    by_id = {r.package_id: r for r in results}
    assert by_id["WP-001"].status == WorkStatus.DONE
    assert by_id["WP-002"].status == WorkStatus.DONE
    agent_alpha.send_and_wait.assert_awaited_once()
    agent_beta.send_and_wait.assert_awaited_once()


@pytest.mark.asyncio()
async def test_agent_error_marks_failed(package_alpha):
    """Agent raises RuntimeError — result should be FAILED."""
    failing_agent = _make_agent("alpha")
    failing_agent.send_and_wait = AsyncMock(side_effect=RuntimeError("Agent crashed"))

    protocol = ExecutionProtocol(agents={"alpha": failing_agent})
    results = await protocol.run([package_alpha])

    assert len(results) == 1
    assert results[0].status == WorkStatus.FAILED
    assert "Agent crashed" in results[0].summary


@pytest.mark.asyncio()
async def test_missing_agent_marks_failed():
    """Package owner has no matching agent — result should be FAILED."""
    protocol = ExecutionProtocol(agents={})
    wp = _make_package("nonexistent_agent")
    results = await protocol.run([wp])

    assert len(results) == 1
    assert results[0].status == WorkStatus.FAILED
    assert "nonexistent_agent" in results[0].summary


def test_build_execution_prompt():
    """Verify the prompt contains package_id, owner, and objective."""
    wp = WorkPackage(
        id="WP-042",
        title="Sample task",
        owner_agent="coder",
        objective="Refactor the module",
        scope=["src/module.py"],
        acceptance_criteria=["All tests pass"],
    )
    prompt = ExecutionProtocol.build_execution_prompt(wp)

    assert "WP-042" in prompt
    assert "coder" in prompt
    assert "Refactor the module" in prompt
    assert "src/module.py" in prompt
    assert "All tests pass" in prompt


def test_build_execution_prompt_with_decisions():
    """Decisions section is included when provided."""
    wp = _make_package("alpha")
    prompt = ExecutionProtocol.build_execution_prompt(wp, decisions=["Use SQLite", "REST API"])

    assert "Relevant Decisions:" in prompt
    assert "Use SQLite" in prompt
    assert "REST API" in prompt


def test_extract_files_changed():
    """Parse ## Files Changed section from agent output."""
    content = "## Completed\nDone.\n## Files Changed\n- src/main.py\n- tests/test.py\n## Blockers\nNone"
    files = ExecutionProtocol._extract_files_changed(content)
    assert files == ["src/main.py", "tests/test.py"]


def test_extract_blockers():
    """Parse ## Blockers section — non-empty list means BLOCKED status."""
    content = "## Completed\nPartial.\n## Blockers\n- Missing API key\n- Timeout issue"
    blockers = ExecutionProtocol._extract_blockers(content)
    assert blockers == ["Missing API key", "Timeout issue"]


def test_extract_blockers_empty():
    """No blockers section means empty list."""
    content = "## Completed\nAll done.\n## Files Changed\n- a.py"
    blockers = ExecutionProtocol._extract_blockers(content)
    assert blockers == []
