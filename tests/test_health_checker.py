"""Tests for trinity.health.checker — HealthChecker and HealthReport."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from trinity.agents.base import AgentWrapper
from trinity.health.checker import HealthChecker, HealthReport
from trinity.models import AgentHealth, AgentSpec, ContextUsage, Provider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_agent(name: str, alive: bool = True, used: int = 0, total: int = 100_000) -> AsyncMock:
    """Create a mock agent with configurable health."""
    spec = AgentSpec(
        name=name,
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        context_budget=total,
    )
    agent = AsyncMock(spec=spec)
    agent.name = name
    agent.spec = spec
    agent.context_usage = ContextUsage(used=used, total=total)

    # Async methods
    agent.is_alive = AsyncMock(return_value=alive)
    agent.get_context_usage = AsyncMock(return_value=ContextUsage(used=used, total=total))
    return agent


@pytest.fixture
def healthy_agents():
    return {
        "alpha": _make_agent("alpha", alive=True, used=10_000),
        "beta": _make_agent("beta", alive=True, used=30_000),
    }


@pytest.fixture
def mixed_agents():
    return {
        "alive": _make_agent("alive", alive=True, used=5_000),
        "dead": _make_agent("dead", alive=False, used=0),
    }


@pytest.fixture
def checker(healthy_agents):
    return HealthChecker(agents=healthy_agents, check_interval=5.0, stale_threshold=60.0)


# ===========================================================================
# HealthReport
# ===========================================================================

class TestHealthReport:
    """HealthReport dataclass."""

    def test_all_healthy_true(self):
        report = HealthReport(
            agents={
                "a": AgentHealth(name="a", alive=True),
                "b": AgentHealth(name="b", alive=True),
            },
            all_healthy=True,
        )
        assert report.all_healthy is True
        assert report.unhealthy_agents == []

    def test_unhealthy_agents_list(self):
        report = HealthReport(
            agents={
                "a": AgentHealth(name="a", alive=True),
                "b": AgentHealth(name="b", alive=False),
                "c": AgentHealth(name="c", alive=False),
            },
            all_healthy=False,
        )
        assert sorted(report.unhealthy_agents) == ["b", "c"]

    def test_timestamp_populated(self):
        report = HealthReport(agents={})
        assert report.timestamp > 0


# ===========================================================================
# HealthChecker — synchronous check_all
# ===========================================================================

class TestCheckAll:
    """HealthChecker.check_all() — synchronous path."""

    def test_all_healthy(self, checker):
        report = checker.check_all()
        assert report.all_healthy is True
        assert len(report.agents) == 2
        assert "alpha" in report.agents
        assert "beta" in report.agents

    def test_reports_context_ratio(self, checker):
        report = checker.check_all()
        # alpha has used=10_000, total=100_000
        assert report.agents["alpha"].context_ratio == pytest.approx(0.1)

    def test_status_idle_when_zero_usage(self):
        agents = {"idle_agent": _make_agent("idle_agent", alive=True, used=0)}
        checker = HealthChecker(agents=agents)
        report = checker.check_all()
        assert report.agents["idle_agent"].status == "idle"

    def test_status_working_when_usage_nonzero(self):
        agents = {"worker": _make_agent("worker", alive=True, used=1_000)}
        checker = HealthChecker(agents=agents)
        report = checker.check_all()
        assert report.agents["worker"].status == "working"

    def test_error_handling(self):
        """Agent가 예외를 던지면 alive=False, status='error'."""
        broken = AsyncMock()
        broken.context_usage = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        broken.__class__ = type("Broken", (object,), {
            "context_usage": property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        })

        # Use a simpler approach — make _check_single catch exceptions
        spec = AgentSpec(name="broken", provider=Provider.CLAUDE_CODE, cli_command="x")
        broken_agent = MagicMock(spec=spec)
        broken_agent.name = "broken"
        broken_agent.spec = spec
        # Accessing context_usage raises
        type(broken_agent).context_usage = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

        checker = HealthChecker(agents={"broken": broken_agent})
        report = checker.check_all()
        assert report.agents["broken"].alive is False
        assert report.agents["broken"].status == "error"


# ===========================================================================
# HealthChecker — async check_all_async
# ===========================================================================

class TestCheckAllAsync:
    """HealthChecker.check_all_async()."""

    @pytest.mark.asyncio
    async def test_all_healthy(self, checker):
        report = await checker.check_all_async()
        assert report.all_healthy is True

    @pytest.mark.asyncio
    async def test_mixed_health(self, mixed_agents):
        checker = HealthChecker(agents=mixed_agents)
        report = await checker.check_all_async()
        assert report.all_healthy is False
        assert "dead" in report.unhealthy_agents

    @pytest.mark.asyncio
    async def test_async_alive_status(self, checker):
        report = await checker.check_all_async()
        for name, health in report.agents.items():
            assert health.alive is True
            assert health.status in ("idle", "working")

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """Agent.is_alive()가 예외를 던지면 error 상태."""
        failing = AsyncMock()
        failing.is_alive = AsyncMock(side_effect=RuntimeError("connection lost"))
        failing.get_context_usage = AsyncMock(return_value=ContextUsage())
        spec = AgentSpec(name="fail", provider=Provider.CLAUDE_CODE, cli_command="x")
        failing.spec = spec
        failing.name = "fail"

        checker = HealthChecker(agents={"fail": failing})
        report = await checker.check_all_async()
        assert report.agents["fail"].alive is False
        assert report.agents["fail"].status == "error"


# ===========================================================================
# HealthChecker — ping
# ===========================================================================

class TestPing:
    """HealthChecker.ping() — agent-to-agent ping."""

    @pytest.mark.asyncio
    async def test_ping_alive(self, checker):
        result = await checker.ping(from_agent="alpha", to_agent="beta")
        assert result is True

    @pytest.mark.asyncio
    async def test_ping_unknown_target(self, checker):
        result = await checker.ping(from_agent="alpha", to_agent="nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_dead_agent(self, mixed_agents):
        checker = HealthChecker(agents=mixed_agents)
        result = await checker.ping(from_agent="alive", to_agent="dead")
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_exception_returns_false(self, checker):
        """ping 대상 agent가 예외를 던지면 False."""
        failing = AsyncMock()
        failing.is_alive = AsyncMock(side_effect=RuntimeError("timeout"))
        spec = AgentSpec(name="flaky", provider=Provider.CLAUDE_CODE, cli_command="x")
        failing.spec = spec
        failing.name = "flaky"

        checker = HealthChecker(agents={"flaky": failing})
        result = await checker.ping(from_agent="alpha", to_agent="flaky")
        assert result is False


# ===========================================================================
# HealthChecker — start_monitoring
# ===========================================================================

class TestStartMonitoring:
    """HealthChecker.start_monitoring() — periodic monitoring loop."""

    @pytest.mark.asyncio
    async def test_monitoring_calls_callback(self, checker):
        """callback이 check 이후에 호출됨."""
        callback = AsyncMock()
        # We'll let it run one cycle, then cancel by raising
        call_count = 0

        async def count_callback(report):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        # Use very short interval for testing
        checker.check_interval = 0.1

        with pytest.raises(asyncio.CancelledError):
            await checker.start_monitoring(callback=count_callback)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_monitoring_continues_on_callback_error(self, checker):
        """callback이 일반 예외를 던져도 모니터링은 계속됨."""
        call_count = 0

        async def bad_callback(report):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("bad callback")
            raise asyncio.CancelledError()

        checker.check_interval = 0.1

        with pytest.raises(asyncio.CancelledError):
            await checker.start_monitoring(callback=bad_callback)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_monitoring_no_callback(self, checker):
        """callback 없이도 동작 (무한 루프 방지를 위해 CancelledError로 종료)."""
        checker.check_interval = 0.1
        iterations = 0
        original_check = checker.check_all_async

        async def counting_check():
            nonlocal iterations
            iterations += 1
            if iterations >= 3:
                raise asyncio.CancelledError()
            return await original_check()

        checker.check_all_async = counting_check

        with pytest.raises(asyncio.CancelledError):
            await checker.start_monitoring(callback=None)

        assert iterations == 3
