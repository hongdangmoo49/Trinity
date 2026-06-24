"""Tests for trinity.error_handler — ErrorHandler."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.error_handler import CrashEvent, ErrorHandler, RecoveryAction, RecoveryPolicy
from trinity.models import AgentSpec, Provider


def _make_agent(name: str, alive: bool = True) -> MagicMock:
    spec = AgentSpec(name=name, provider=Provider.CLAUDE_CODE, cli_command="claude")
    agent = MagicMock()
    agent.name = name
    agent.spec = spec
    agent.is_alive = AsyncMock(return_value=alive)
    agent.graceful_shutdown = AsyncMock()
    agent.start = AsyncMock()
    return agent


@pytest.fixture
def agents():
    return {
        "alpha": _make_agent("alpha", alive=True),
        "beta": _make_agent("beta", alive=True),
    }


@pytest.fixture
def shared(tmp_path):
    path = tmp_path / "shared.md"
    path.write_text("# Shared Context\n\n## Goal\nTest goal\n", encoding="utf-8")
    return SharedContextEngine(path=path)


@pytest.fixture
def handler(agents, shared):
    return ErrorHandler(
        agents=agents,
        shared=shared,
        policy=RecoveryPolicy(max_crashes=3, crash_window=300.0),
    )


# ===========================================================================
# Crash recording
# ===========================================================================

class TestCrashRecording:
    def test_records_crash(self, handler):
        event = CrashEvent(
            agent_name="alpha", timestamp=time.time(), reason="crashed",
        )
        handler._record_crash(event)
        history = handler.get_crash_history("alpha")
        assert len(history) == 1

    def test_disables_after_max_crashes(self, handler):
        for i in range(3):
            handler._record_crash(CrashEvent(
                agent_name="alpha", timestamp=time.time(), reason=f"crash {i}",
            ))
        assert handler.is_disabled("alpha")

    def test_not_disabled_below_threshold(self, handler):
        handler._record_crash(CrashEvent(
            agent_name="alpha", timestamp=time.time(), reason="crash",
        ))
        assert not handler.is_disabled("alpha")

    def test_cleans_old_crashes(self):
        policy = RecoveryPolicy(max_crashes=2, crash_window=1.0)
        h = ErrorHandler(agents={}, policy=policy)

        # Old crash
        h._record_crash(CrashEvent(
            agent_name="alpha", timestamp=time.time() - 10, reason="old",
        ))
        # New crash
        h._record_crash(CrashEvent(
            agent_name="alpha", timestamp=time.time(), reason="new",
        ))

        # Old crash should be cleaned, only 1 remaining
        assert len(h.get_crash_history("alpha")) == 1

    def test_history_all_agents(self, handler):
        handler._record_crash(CrashEvent(
            agent_name="alpha", timestamp=time.time(), reason="crash",
        ))
        handler._record_crash(CrashEvent(
            agent_name="beta", timestamp=time.time(), reason="crash",
        ))
        assert len(handler.get_crash_history()) == 2


# ===========================================================================
# Active agents
# ===========================================================================

class TestActiveAgents:
    def test_returns_all_when_no_crashes(self, handler):
        active = handler.get_active_agents()
        assert set(active.keys()) == {"alpha", "beta"}

    def test_excludes_disabled(self, handler):
        handler._disabled_agents.add("alpha")
        active = handler.get_active_agents()
        assert "alpha" not in active
        assert "beta" in active


# ===========================================================================
# Crash handling
# ===========================================================================

class TestHandleCrash:
    @pytest.mark.asyncio
    async def test_respawns_on_first_crash(self, handler):
        event = await handler.handle_crash("alpha", reason="process died")
        assert event.recovery_action == RecoveryAction.RESPAWN
        handler.agents["alpha"].start.assert_called_once()

    @pytest.mark.asyncio
    async def test_disables_after_max_crashes(self, handler):
        for i in range(handler.policy.max_crashes):
            await handler.handle_crash("alpha", reason=f"crash {i}")
        assert handler.is_disabled("alpha")

    @pytest.mark.asyncio
    async def test_injects_context_on_respawn(self, handler):
        await handler.handle_crash("alpha", reason="crash")
        # start should have been called with context
        call_args = handler.agents["alpha"].start.call_args
        initial_prompt = call_args.kwargs.get("initial_prompt", "")
        assert "Previous context" in initial_prompt

    @pytest.mark.asyncio
    async def test_crash_callback(self, handler):
        events = []
        handler.on_crash(lambda e: events.append(e))
        await handler.handle_crash("alpha", reason="test")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_async_callback(self, handler):
        events = []
        async def on_crash(event):
            events.append(event)
        handler.on_crash(on_crash)
        await handler.handle_crash("alpha", reason="test")
        assert len(events) == 1


# ===========================================================================
# Check agents
# ===========================================================================

class TestCheckAgents:
    @pytest.mark.asyncio
    async def test_detects_dead_agent(self, handler):
        handler.agents["alpha"].is_alive = AsyncMock(return_value=False)
        events = await handler.check_agents()
        assert len(events) == 1
        assert events[0].agent_name == "alpha"

    @pytest.mark.asyncio
    async def test_ignores_disabled(self, handler):
        handler._disabled_agents.add("alpha")
        handler.agents["alpha"].is_alive = AsyncMock(return_value=False)
        events = await handler.check_agents()
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_no_events_when_healthy(self, handler):
        events = await handler.check_agents()
        assert len(events) == 0


# ===========================================================================
# Reset
# ===========================================================================

class TestReset:
    def test_reset_specific_agent(self, handler):
        handler._disabled_agents.add("alpha")
        handler.reset("alpha")
        assert not handler.is_disabled("alpha")
        assert handler.get_crash_history("alpha") == []

    def test_reset_all(self, handler):
        handler._disabled_agents.add("alpha")
        handler._disabled_agents.add("beta")
        handler.reset()
        assert not handler.is_disabled("alpha")
        assert not handler.is_disabled("beta")
