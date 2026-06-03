"""Lifecycle guard — context monitoring at all workflow boundaries.

Wraps TokenBudgetChecker to provide guard checks before and after agent
calls, at round boundaries, and before work-package dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from trinity.context.budget import TokenBudgetChecker
from trinity.models import ContextUsage

if TYPE_CHECKING:
    from trinity.agents.base import AgentWrapper
    from trinity.models import WorkPackage


@dataclass
class GuardResult:
    """Result of a lifecycle guard check."""

    agent_name: str
    safe: bool
    current_ratio: float
    recommendation: str  # "proceed" | "rotate_before_send" | "rotate_after_response"


class LifecycleGuard:
    """Monitor context usage at every workflow boundary.

    Parameters
    ----------
    agents:
        Mapping of agent name to AgentWrapper instance.
    threshold:
        Context ratio above which an agent is considered unsafe (default 0.60).
    warning_threshold:
        Context ratio above which a warning is emitted (default 0.55).
    """

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        threshold: float = 0.60,
        warning_threshold: float = 0.55,
    ) -> None:
        self._agents = agents
        self._threshold = threshold
        self._warning_threshold = warning_threshold
        self._checker = TokenBudgetChecker(threshold=threshold)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def before_agent_call(self, agent_name: str, prompt: str) -> GuardResult:
        """Check projected context before sending a prompt to an agent.

        Returns safe=True for unknown agents.
        """
        agent = self._agents.get(agent_name)
        if agent is None:
            return GuardResult(
                agent_name=agent_name,
                safe=True,
                current_ratio=0.0,
                recommendation="proceed",
            )

        usage: ContextUsage = agent.context_usage
        result = self._checker.check(prompt, usage, agent.spec)

        if not result.safe:
            recommendation = "rotate_before_send"
        elif result.projected_ratio >= self._warning_threshold:
            recommendation = "rotate_after_response"
        else:
            recommendation = "proceed"

        return GuardResult(
            agent_name=agent_name,
            safe=result.safe,
            current_ratio=result.projected_ratio,
            recommendation=recommendation,
        )

    def after_agent_call(self, agent_name: str) -> GuardResult:
        """Check actual context ratio after a response.

        Returns safe=True for unknown agents.
        """
        agent = self._agents.get(agent_name)
        if agent is None:
            return GuardResult(
                agent_name=agent_name,
                safe=True,
                current_ratio=0.0,
                recommendation="proceed",
            )

        usage: ContextUsage = agent.context_usage
        ratio = usage.ratio

        if ratio >= self._threshold:
            safe = False
            recommendation = "rotate_after_response"
        elif ratio >= self._warning_threshold:
            safe = True
            recommendation = "rotate_after_response"
        else:
            safe = True
            recommendation = "proceed"

        return GuardResult(
            agent_name=agent_name,
            safe=safe,
            current_ratio=ratio,
            recommendation=recommendation,
        )

    def before_round(self, round_num: int) -> list[GuardResult]:
        """Check all agents and return those above the warning threshold."""
        warnings: list[GuardResult] = []
        for name, agent in self._agents.items():
            ratio = agent.context_usage.ratio
            if ratio >= self._warning_threshold:
                safe = ratio < self._threshold
                recommendation = (
                    "rotate_after_response" if safe else "rotate_before_send"
                )
                warnings.append(
                    GuardResult(
                        agent_name=name,
                        safe=safe,
                        current_ratio=ratio,
                        recommendation=recommendation,
                    )
                )
        return warnings

    def before_work_package(self, package: WorkPackage) -> GuardResult:
        """Check agent before dispatching a work package."""
        return self.before_agent_call(package.owner_agent, package.objective)
