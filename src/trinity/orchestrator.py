"""Trinity orchestrator — top-level coordinator for the entire system."""

from __future__ import annotations

import logging
import time

from trinity.agents.base import AgentWrapper
from trinity.agents.claude_agent import PrintModeClaudeAgent
from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.models import DeliberationResult, Provider

logger = logging.getLogger(__name__)


class TrinityOrchestrator:
    """Owns all components and drives the deliberation lifecycle."""

    def __init__(self, config: TrinityConfig):
        self.config = config
        self.agents: dict[str, AgentWrapper] = {}
        self.shared: SharedContextEngine | None = None
        self.protocol: DeliberationProtocol | None = None

    def _ensure_initialized(self) -> None:
        """Lazy initialization: create agents, shared context, protocol."""
        if self.agents and self.shared:
            return

        # Ensure state directory exists
        state_dir = self.config.effective_state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "agents").mkdir(exist_ok=True)
        (state_dir / "history").mkdir(exist_ok=True)
        (state_dir / "logs").mkdir(exist_ok=True)

        # Create shared context engine
        self.shared = SharedContextEngine(
            path=self.config.shared_context_path,
            keep_sections=self.config.keep_sections,
        )

        # Create agent wrappers
        for name, spec in self.config.active_agents.items():
            agent = self._create_agent(spec)
            self.agents[name] = agent
            logger.info(f"Created agent: {agent}")

        if not self.agents:
            raise ValueError(
                "No active agents configured. Enable at least one agent in config."
            )

        # Create deliberation protocol
        self.protocol = DeliberationProtocol(
            agents=self.agents,
            shared=self.shared,
            consensus_engine=ConsensusEngine(
                required_fraction=self.config.consensus_threshold,
            ),
            distributor=TaskDistributor(),
            max_rounds=self.config.max_deliberation_rounds,
            round_timeout=self.config.round_timeout_seconds,
        )

    def _create_agent(self, spec) -> AgentWrapper:
        """Factory: create the appropriate agent wrapper based on provider."""
        if spec.provider == Provider.CLAUDE_CODE:
            return PrintModeClaudeAgent(spec)
        elif spec.provider == Provider.CODEX:
            # Phase 4: CodexAgent
            logger.warning(
                f"Codex agent not yet implemented. "
                f"Falling back to Claude print-mode for '{spec.name}'."
            )
            return PrintModeClaudeAgent(spec)
        elif spec.provider == Provider.GEMINI_CLI:
            # Phase 4: GeminiAgent
            logger.warning(
                f"Gemini agent not yet implemented. "
                f"Falling back to Claude print-mode for '{spec.name}'."
            )
            return PrintModeClaudeAgent(spec)
        else:
            raise ValueError(f"Unknown provider: {spec.provider}")

    async def ask(self, prompt: str) -> DeliberationResult:
        """Main entry point: run deliberation on a user prompt."""
        self._ensure_initialized()

        logger.info(f"Starting deliberation: {prompt[:100]}...")
        start_time = time.time()

        # Start all agents
        for name, agent in self.agents.items():
            role_prompt = agent.spec.role_prompt or ""
            await agent.start(initial_prompt=role_prompt)

        # Run the deliberation protocol
        result = await self.protocol.run(prompt)

        elapsed = time.time() - start_time
        logger.info(
            f"Deliberation complete: {result.rounds_completed} rounds, "
            f"{elapsed:.1f}s, consensus={'YES' if result.has_consensus else 'NO'}"
        )

        return result

    def get_status(self) -> dict:
        """Return current orchestrator status."""
        self._ensure_initialized()
        return {
            "agents": {
                name: {
                    "provider": agent.spec.provider.value,
                    "alive": True,  # Print mode always "alive"
                    "context": str(agent.context_usage),
                }
                for name, agent in self.agents.items()
            },
            "shared_context_path": str(self.config.shared_context_path),
            "max_rounds": self.config.max_deliberation_rounds,
        }
