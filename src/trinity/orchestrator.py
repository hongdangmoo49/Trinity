"""Trinity orchestrator — top-level coordinator for the entire system."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from trinity.agents.base import AgentWrapper
from trinity.agents.factory import AgentFactory
from trinity.config import TrinityConfig
from trinity.context.analytics import analytics_history_path
from trinity.context.monitor import ContextMonitor
from trinity.context.rotator import SessionRotator
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.health.checker import HealthChecker
from trinity.models import AgentSpec, DeliberationResult
from trinity.providers.readiness import ProviderReadinessGate
from trinity.tmux.session import TmuxSessionManager
from trinity.workflow.engine import WorkflowEngine
from trinity.workspace.isolation import WorkspaceIsolation
from trinity.workspace.managed_home import ManagedHome

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentLaunchContext:
    """Prepared launch paths for a single active agent."""

    agent_name: str
    cwd: Path
    env_overrides: dict[str, str] = field(default_factory=dict)
    managed_home: Path | None = None
    workspace_path: Path | None = None


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
        self.managed_home: ManagedHome | None = None
        self.workspace_isolation: WorkspaceIsolation | None = None
        self.agent_launch_contexts: dict[str, AgentLaunchContext] = {}
        self._event_bus = None
        self.readiness_gate: ProviderReadinessGate | None = None
        self.workflow_engine: WorkflowEngine | None = None
        self.lifecycle_guard = None  # created during _ensure_initialized
        self.workflow_persistence = None  # created during _ensure_initialized

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
        active_agents = self.config.active_agents
        self._prepare_agent_launch_contexts(active_agents, state_dir)

        # Create shared context engine
        self.shared = SharedContextEngine(
            path=self.config.shared_context_path,
            keep_sections=self.config.keep_sections,
        )

        if self.interactive:
            self._init_interactive_mode(state_dir, active_agents)
        else:
            self._init_print_mode(active_agents)

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
            lang=self.config.lang,
            analytics_path=analytics_history_path(state_dir),
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

    def _prepare_agent_launch_contexts(
        self, active_agents: dict[str, AgentSpec], state_dir: Path
    ) -> None:
        """Prepare per-agent cwd/env metadata before wrappers are created."""
        self.managed_home = ManagedHome(state_dir=state_dir)
        self.agent_launch_contexts = {}

        needs_worktree = any(
            spec.workspace_mode == "git-worktree" for spec in active_agents.values()
        )
        self.workspace_isolation = (
            WorkspaceIsolation(
                project_root=self.config.project_dir,
                state_dir=state_dir / "workspace",
            )
            if needs_worktree
            else None
        )

        for name, spec in active_agents.items():
            provider_name = getattr(spec.provider, "value", str(spec.provider))
            managed_home = self.managed_home.setup(name, provider=provider_name)
            env_overrides = self.managed_home.get_env_overrides(name)

            cwd = self.config.project_dir.resolve()
            workspace_path: Path | None = None
            if spec.workspace_mode == "git-worktree":
                if self.workspace_isolation is None:
                    raise RuntimeError("Workspace isolation was not initialized")
                workspace_path = self.workspace_isolation.create(name)
                cwd = workspace_path
            elif spec.workspace_mode != "inplace":
                raise ValueError(
                    f"Unsupported workspace_mode for agent '{name}': "
                    f"{spec.workspace_mode!r}"
                )

            self.agent_launch_contexts[name] = AgentLaunchContext(
                agent_name=name,
                cwd=cwd,
                env_overrides=env_overrides,
                managed_home=managed_home,
                workspace_path=workspace_path,
            )

    def get_agent_launch_context(self, agent_name: str) -> AgentLaunchContext | None:
        """Return prepared launch metadata for an agent, initializing if needed."""
        self._ensure_initialized()
        return self.agent_launch_contexts.get(agent_name)

    def get_agent_env_overrides(self, agent_name: str) -> dict[str, str]:
        """Return a copy of env overrides prepared for an agent launch."""
        context = self.get_agent_launch_context(agent_name)
        return dict(context.env_overrides) if context else {}

    def get_agent_cwd(self, agent_name: str) -> Path | None:
        """Return the prepared launch cwd for an agent."""
        context = self.get_agent_launch_context(agent_name)
        return context.cwd if context else None

    def _init_print_mode(self, active_agents: dict[str, AgentSpec] | None = None) -> None:
        """Initialize agents in print mode (Phase 1 — subprocess-based)."""
        for name, spec in (active_agents or self.config.active_agents).items():
            agent = self._create_print_agent(spec)
            self._apply_launch_context(name, agent)
            self.agents[name] = agent
            logger.info(f"Created agent (print mode): {agent}")

    def _init_interactive_mode(
        self, state_dir: Path, active_agents: dict[str, AgentSpec] | None = None
    ) -> None:
        """Initialize agents in interactive tmux mode (Phase 2)."""
        active_agents = active_agents or self.config.active_agents

        # Create tmux session with panes for each agent
        self.tmux_manager = TmuxSessionManager(
            session_name=self.config.session_name,
        )
        self.tmux_manager.create_session(
            list(active_agents.values()),
            launch_contexts=self.agent_launch_contexts,
        )

        # Create agents with panes and completion detectors
        for name, spec in active_agents.items():
            pane = self.tmux_manager.get_pane(name)
            if not pane:
                logger.warning(f"No pane for agent '{name}', falling back to print mode")
                agent = self._create_print_agent(spec)
                self._apply_launch_context(name, agent)
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
            self._apply_launch_context(name, agent)
            self.agents[name] = agent
            logger.info(f"Created agent (interactive): {agent}")

    def _create_print_agent(self, spec) -> AgentWrapper:
        """Factory: create a print-mode agent using AgentFactory."""
        return AgentFactory.create(spec, mode="print")

    def _apply_launch_context(self, agent_name: str, agent: AgentWrapper) -> None:
        """Attach prepared cwd/env metadata to an agent wrapper."""
        context = self.agent_launch_contexts.get(agent_name)
        if context:
            agent.configure_launch(
                cwd=context.cwd,
                env_overrides=context.env_overrides,
            )

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
