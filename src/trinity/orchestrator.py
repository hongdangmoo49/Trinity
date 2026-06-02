"""Trinity orchestrator — top-level coordinator for the entire system."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from trinity.agents.base import AgentWrapper
from trinity.agents.claude_agent import InteractiveClaudeAgent, PrintModeClaudeAgent
from trinity.agents.factory import AgentFactory
from trinity.completion.base import FallbackChainDetector
from trinity.completion.hook import HookDetector
from trinity.completion.idle import IdleDetector
from trinity.completion.prompt import PromptReturnDetector
from trinity.config import TrinityConfig
from trinity.context.monitor import ContextMonitor
from trinity.context.rotator import SessionRotator
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.health.checker import HealthChecker
from trinity.models import DeliberationResult, Provider
from trinity.tmux.session import TmuxSessionManager

logger = logging.getLogger(__name__)


class TrinityOrchestrator:
    """Owns all components and drives the deliberation lifecycle."""

    def __init__(self, config: TrinityConfig, interactive: bool = False):
        self.config = config
        self.interactive = interactive
        self.agents: dict[str, AgentWrapper] = {}
        self.shared: SharedContextEngine | None = None
        self.protocol: DeliberationProtocol | None = None
        self.tmux_manager: TmuxSessionManager | None = None
        self.context_monitor: ContextMonitor | None = None
        self.session_rotator: SessionRotator | None = None
        self.health_checker: HealthChecker | None = None
        self._event_bus = None

    def set_event_bus(self, bus) -> None:
        """Set the TUI event bus for real-time deliberation updates.

        Args:
            bus: A TUIEventBus instance from trinity.tui.events.
        """
        self._event_bus = bus

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

        if self.interactive:
            self._init_interactive_mode(state_dir)
        else:
            self._init_print_mode()

        if not self.agents:
            raise ValueError(
                "No active agents configured. Enable at least one agent in config."
            )

        # Create deliberation protocol
        event_callback = self._event_bus.emit if self._event_bus else None
        self.protocol = DeliberationProtocol(
            agents=self.agents,
            shared=self.shared,
            consensus_engine=ConsensusEngine(
                required_fraction=self.config.consensus_threshold,
            ),
            distributor=TaskDistributor(),
            max_rounds=self.config.max_deliberation_rounds,
            round_timeout=self.config.round_timeout_seconds,
            tmux_manager=self.tmux_manager if self.interactive else None,
            event_callback=event_callback,
            compression_enabled=self.config.prompt_compression_enabled,
            compression_round_threshold=self.config.prompt_compression_round_threshold,
            compression_max_summary_tokens=self.config.prompt_compression_max_summary_tokens,
            caveman_mode=self.config.caveman_mode,
            caveman_intensity=self.config.caveman_intensity,
        )

        # Create context monitor and session rotator
        self.context_monitor = ContextMonitor(
            agents=self.agents,
            rotate_threshold=self.config.context_rotate_threshold,
        )
        self.session_rotator = SessionRotator(
            agents=self.agents,
            shared=self.shared,
            recent_rounds=self.config.recent_rounds_on_rotate,
        )

        # Create health checker
        self.health_checker = HealthChecker(
            agents=self.agents,
            check_interval=self.config.health_check_interval_seconds,
        )

    def _init_print_mode(self) -> None:
        """Initialize agents in print mode (Phase 1 — subprocess-based)."""
        for name, spec in self.config.active_agents.items():
            agent = self._create_print_agent(spec)
            self.agents[name] = agent
            logger.info(f"Created agent (print mode): {agent}")

    def _init_interactive_mode(self, state_dir: Path) -> None:
        """Initialize agents in interactive tmux mode (Phase 2)."""
        active_agents = self.config.active_agents

        # Create tmux session with panes for each agent
        self.tmux_manager = TmuxSessionManager(
            session_name=self.config.session_name,
        )
        self.tmux_manager.create_session(list(active_agents.values()))

        # Create agents with panes and completion detectors
        for name, spec in active_agents.items():
            pane = self.tmux_manager.get_pane(name)
            if not pane:
                logger.warning(f"No pane for agent '{name}', falling back to print mode")
                agent = self._create_print_agent(spec)
                self.agents[name] = agent
                continue

            # Build completion detector chain for this agent
            signal_path = state_dir / "agents" / name / "completion_signal.json"
            detector = AgentFactory.create_detector_chain(signal_path, spec.provider)

            agent = AgentFactory.create(
                spec=spec,
                mode="interactive",
                pane=pane,
                detector=detector,
                signal_path=signal_path,
            )
            self.agents[name] = agent
            logger.info(f"Created agent (interactive): {agent}")

    def _create_detector_chain(self, signal_path: Path) -> FallbackChainDetector:
        """Create a default fallback chain: Hook → PromptReturn → Idle."""
        return FallbackChainDetector([
            HookDetector(signal_path=signal_path),
            PromptReturnDetector(),
            IdleDetector(idle_timeout=10.0),
        ])

    def _create_print_agent(self, spec) -> AgentWrapper:
        """Factory: create a print-mode agent using AgentFactory."""
        return AgentFactory.create(spec, mode="print")

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

        # Check context usage and rotate if needed
        await self._check_and_rotate()

        elapsed = time.time() - start_time
        logger.info(
            f"Deliberation complete: {result.rounds_completed} rounds, "
            f"{elapsed:.1f}s, consensus={'YES' if result.has_consensus else 'NO'}"
        )

        return result

    async def _check_and_rotate(self) -> None:
        """Check all agents' context usage and rotate those exceeding threshold."""
        if not self.context_monitor or not self.session_rotator:
            return

        needs_rotation = self.context_monitor.check_usage()

        for agent_name in needs_rotation:
            logger.info(f"[{agent_name}] Context threshold reached, rotating session...")
            success = await self.session_rotator.rotate(agent_name)

            if success:
                # Broadcast rotation to other agents
                msg = self.session_rotator.build_broadcast_message(agent_name)
                logger.info(f"Broadcast: {msg}")

    def get_analytics(self) -> dict | None:
        """Return token analytics summary if available."""
        if self.protocol and self.protocol.analytics.history:
            return self.protocol.analytics.summary()
        return None

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
            "interactive": self.interactive,
            "tmux_session": (
                self.config.session_name if self.tmux_manager else None
            ),
        }

    async def shutdown(self) -> None:
        """Gracefully shut down all agents and tmux session."""
        for name, agent in self.agents.items():
            try:
                await agent.graceful_shutdown()
                logger.info(f"Agent '{name}' shut down")
            except Exception as e:
                logger.error(f"Error shutting down agent '{name}': {e}")

        if self.tmux_manager:
            self.tmux_manager.destroy()
            logger.info("tmux session destroyed")
