"""Context monitor — track token usage and trigger session rotation."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from trinity.agents.base import AgentWrapper
from trinity.models import ContextUsage, Provider

logger = logging.getLogger(__name__)


@dataclass
class ProviderContextLimits:
    """Default context limits per provider (tokens)."""

    defaults: dict[str, int] = field(default_factory=lambda: {
        Provider.CLAUDE_CODE: 200_000,
        Provider.CODEX: 128_000,
        Provider.ANTIGRAVITY_CLI: 1_000_000,
    })

    def get_limit(self, provider: str) -> int:
        return self.defaults.get(provider, 200_000)


class ContextMonitor:
    """Periodically check agents' context usage and flag when rotation is needed.

    Usage:
        monitor = ContextMonitor(agents=my_agents)
        # After each round:
        for name in monitor.check_usage():
            print(f"{name} needs rotation!")
    """

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        rotate_threshold: float = 0.60,
        provider_limits: ProviderContextLimits | None = None,
    ):
        self.agents = agents
        self.rotate_threshold = rotate_threshold
        self.provider_limits = provider_limits or ProviderContextLimits()

    def check_usage(self) -> list[str]:
        """Check all agents and return names of those needing rotation.

        Call this after each deliberation round.
        """
        needs_rotation: list[str] = []

        for name, agent in self.agents.items():
            usage = agent.context_usage
            if usage.ratio >= self.rotate_threshold:
                needs_rotation.append(name)
                logger.warning(
                    f"[{name}] Context at {usage.ratio:.0%} "
                    f"({usage.used:,}/{usage.total:,}) — rotation needed"
                )
            else:
                logger.debug(
                    f"[{name}] Context at {usage.ratio:.0%} — OK"
                )

        return needs_rotation

    def get_all_usage(self) -> dict[str, ContextUsage]:
        """Return current usage for all agents."""
        return {name: agent.context_usage for name, agent in self.agents.items()}

    def update_usage(self, agent_name: str, used: int, total: int | None = None) -> None:
        """Manually update an agent's context usage."""
        agent = self.agents.get(agent_name)
        if not agent:
            logger.warning(f"Agent '{agent_name}' not found for usage update")
            return

        current_total = total or agent.context_usage.total
        agent._update_usage(used=used, total=current_total)
        logger.debug(f"[{agent_name}] Usage updated: {used:,}/{current_total:,}")

    def parse_usage_from_claude_json(self, agent_name: str, data: dict) -> None:
        """Parse token usage from Claude's JSON response.

        Expected data format:
            {"usage": {"input_tokens": N, "output_tokens": N}}
        """
        usage_data = data.get("usage", {})
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)
        total_used = input_tokens + output_tokens

        if total_used > 0:
            self.update_usage(agent_name, used=total_used)

    def parse_usage_from_codex_session(self, agent_name: str, data: dict) -> None:
        """Parse token usage from Codex's session JSON.

        Expected data format:
            {"usage": {"total_tokens": N}}
        """
        usage_data = data.get("usage", {})
        total_tokens = usage_data.get("total_tokens", 0)

        if total_tokens > 0:
            self.update_usage(agent_name, used=total_tokens)

    def parse_usage_from_plain_output(self, agent_name: str, output: str) -> None:
        """Parse token usage from plain CLI output.

        Tries multiple patterns:
            - "Token count: N"
            - "Tokens: N"
            - "input_tokens: N, output_tokens: N"
        """
        patterns = [
            r"[Tt]oken\s*(?:count)?\s*:\s*(\d+)",
            r"total_tokens[\":\s]+(\d+)",
            r"input_tokens[\":\s]+(\d+).*?output_tokens[\":\s]+(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    total_used = int(groups[0]) + int(groups[1])
                else:
                    total_used = int(groups[0])

                if total_used > 0:
                    self.update_usage(agent_name, used=total_used)
                    return

        logger.debug(f"[{agent_name}] No token usage found in plain CLI output")
