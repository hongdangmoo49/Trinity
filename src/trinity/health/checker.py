"""Health checker — monitor agent status across all providers."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from trinity.agents.base import AgentWrapper
from trinity.models import AgentHealth

logger = logging.getLogger(__name__)


@dataclass
class HealthReport:
    """Aggregate health report for all agents."""

    agents: dict[str, AgentHealth]
    timestamp: float = field(default_factory=time.time)
    all_healthy: bool = True

    @property
    def unhealthy_agents(self) -> list[str]:
        return [name for name, h in self.agents.items() if not h.alive]


class HealthChecker:
    """Periodically check agent health: pane alive, context ratio, activity.

    Usage:
        checker = HealthChecker(agents=my_agents)
        report = checker.check_all()
        for name in report.unhealthy_agents:
            print(f"{name} is down!")
    """

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        check_interval: float = 30.0,
        stale_threshold: float = 300.0,
    ):
        self.agents = agents
        self.check_interval = check_interval
        self.stale_threshold = stale_threshold  # seconds without activity

    def check_all(self) -> HealthReport:
        """Run a health check on all agents (synchronous, fast)."""
        agent_health: dict[str, AgentHealth] = {}

        for name, agent in self.agents.items():
            health = self._check_single(name, agent)
            agent_health[name] = health

        all_healthy = all(h.alive for h in agent_health.values())
        return HealthReport(agents=agent_health, all_healthy=all_healthy)

    async def check_all_async(self) -> HealthReport:
        """Run health checks asynchronously."""
        tasks = {
            name: self._check_single_async(name, agent)
            for name, agent in self.agents.items()
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        agent_health: dict[str, AgentHealth] = {}
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                agent_health[name] = AgentHealth(
                    name=name, alive=False, status="error",
                )
                logger.error(f"Health check failed for {name}: {result}")
            else:
                agent_health[name] = result

        all_healthy = all(h.alive for h in agent_health.values())
        return HealthReport(agents=agent_health, all_healthy=all_healthy)

    def _check_single(self, name: str, agent: AgentWrapper) -> AgentHealth:
        """Check a single agent's health synchronously."""
        try:
            usage = agent.context_usage
            alive = True  # Print mode always alive; interactive checked separately

            return AgentHealth(
                name=name,
                alive=alive,
                context_ratio=usage.ratio,
                last_activity=time.time(),
                status="idle" if usage.used == 0 else "working",
            )
        except Exception as e:
            logger.error(f"Health check error for {name}: {e}")
            return AgentHealth(name=name, alive=False, status="error")

    async def _check_single_async(self, name: str, agent: AgentWrapper) -> AgentHealth:
        """Check a single agent's health asynchronously."""
        try:
            alive = await agent.is_alive()
            usage = await agent.get_context_usage()

            return AgentHealth(
                name=name,
                alive=alive,
                context_ratio=usage.ratio,
                last_activity=time.time(),
                status="idle" if not alive else ("working" if usage.used > 0 else "idle"),
            )
        except Exception as e:
            logger.error(f"Health check error for {name}: {e}")
            return AgentHealth(name=name, alive=False, status="error")

    async def ping(self, from_agent: str, to_agent: str) -> bool:
        """Check if one agent can reach another (agent-to-agent ping).

        In practice, this checks if the target agent's pane is alive.
        """
        target = self.agents.get(to_agent)
        if not target:
            logger.warning(f"Ping target '{to_agent}' not found")
            return False

        try:
            alive = await target.is_alive()
            logger.debug(f"Ping {from_agent} → {to_agent}: {'OK' if alive else 'DOWN'}")
            return alive
        except Exception:
            return False

    async def start_monitoring(self, callback=None) -> None:
        """Start periodic health monitoring loop.

        Args:
            callback: Optional async function(HealthReport) called after each check.
        """
        logger.info(f"Starting health monitoring (interval={self.check_interval}s)")

        while True:
            report = await self.check_all_async()

            if not report.all_healthy:
                unhealthy = report.unhealthy_agents
                logger.warning(f"Unhealthy agents: {unhealthy}")

            if callback:
                try:
                    await callback(report)
                except Exception as e:
                    logger.error(f"Health callback error: {e}")

            await asyncio.sleep(self.check_interval)
