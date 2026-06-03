"""Tests for LifecycleGuard context monitoring at workflow boundaries."""

from unittest.mock import MagicMock

import pytest

from trinity.models import ContextUsage, WorkPackage, WorkStatus
from trinity.workflow.guard import GuardResult, LifecycleGuard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(name: str, used: int = 50_000, total: int = 200_000) -> MagicMock:
    """Create a mock AgentWrapper with spec and context_usage."""
    agent = MagicMock()
    agent.name = name
    agent.spec = MagicMock()
    agent.spec.name = name
    agent.context_usage = ContextUsage(used=used, total=total)
    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBeforeAgentCall:
    def test_check_before_agent_call_safe(self):
        """Low usage with short prompt should be safe."""
        agent = _make_agent("alice", used=50_000, total=200_000)
        guard = LifecycleGuard({"alice": agent})

        result = guard.before_agent_call("alice", "Hello world")
        assert isinstance(result, GuardResult)
        assert result.agent_name == "alice"
        assert result.safe is True
        assert result.recommendation == "proceed"
        assert result.current_ratio < 0.60

    def test_check_before_agent_call_threshold_exceeded(self):
        """High usage (150K/200K) plus a long prompt should exceed threshold."""
        agent = _make_agent("bob", used=150_000, total=200_000)
        guard = LifecycleGuard({"bob": agent})

        # 10_000 chars * 1.6 tok/char = 16_000 estimated tokens
        # projected = 150_000 + 16_000 = 166_000 -> 166_000/200_000 = 0.83
        long_prompt = "x" * 10_000
        result = guard.before_agent_call("bob", long_prompt)
        assert result.agent_name == "bob"
        assert result.safe is False
        assert result.recommendation == "rotate_before_send"
        assert result.current_ratio >= 0.60


class TestBeforeRound:
    def test_check_before_round(self):
        """Two agents under warning threshold should produce no warnings."""
        agents = {
            "alice": _make_agent("alice", used=50_000, total=200_000),  # 0.25
            "bob": _make_agent("bob", used=80_000, total=200_000),  # 0.40
        }
        guard = LifecycleGuard(agents)
        warnings = guard.before_round(round_num=1)
        assert warnings == []

    def test_check_before_round_with_warning(self):
        """One agent over warning threshold should produce 1 warning."""
        agents = {
            "alice": _make_agent("alice", used=50_000, total=200_000),  # 0.25
            "bob": _make_agent("bob", used=120_000, total=200_000),  # 0.60
        }
        guard = LifecycleGuard(agents)
        warnings = guard.before_round(round_num=1)
        assert len(warnings) == 1
        assert warnings[0].agent_name == "bob"
        assert warnings[0].safe is False


class TestBeforeWorkPackage:
    def test_check_before_work_package(self):
        """before_work_package should return a GuardResult."""
        agent = _make_agent("alice", used=50_000, total=200_000)
        guard = LifecycleGuard({"alice": agent})

        package = WorkPackage(
            id="wp-1",
            title="Test package",
            owner_agent="alice",
            objective="Do some work",
        )
        result = guard.before_work_package(package)
        assert isinstance(result, GuardResult)
        assert result.agent_name == "alice"
        assert result.safe is True


class TestAfterAgentCall:
    def test_check_after_agent_call(self):
        """after_agent_call should return GuardResult with correct agent name."""
        agent = _make_agent("carol", used=50_000, total=200_000)
        guard = LifecycleGuard({"carol": agent})

        result = guard.after_agent_call("carol")
        assert isinstance(result, GuardResult)
        assert result.agent_name == "carol"
        assert result.safe is True
        assert result.recommendation == "proceed"


class TestUnknownAgent:
    def test_unknown_agent_always_safe(self):
        """Nonexistent agent should always return safe=True."""
        guard = LifecycleGuard({})
        result = guard.before_agent_call("ghost", "any prompt")
        assert result.agent_name == "ghost"
        assert result.safe is True
        assert result.recommendation == "proceed"
