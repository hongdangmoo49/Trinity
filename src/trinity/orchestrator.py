"""Trinity orchestrator — top-level coordinator for the entire system."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

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
from trinity.deliberation.synthesis import (
    FallbackSynthesisAgent,
    HeuristicSynthesisAgent,
    ModelBackedSynthesisAgent,
    SynthesisAgent,
)
from trinity.health.checker import HealthChecker
from trinity.models import AgentSpec, ConsensusResult, DeliberationResult, Provider
from trinity.providers.invoker import (
    AntigravityPrintInvoker,
    ClaudePrintInvoker,
    CodexExecInvoker,
    ProviderInvoker,
)
from trinity.providers.policy import ParallelExecutionPolicy
from trinity.providers.readiness import (
    ProviderReadinessGate,
    ReadinessResult,
)
from trinity.legacy.tmux.session import TmuxSessionManager
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workspace.isolation import WorkspaceIsolation
from trinity.workspace.managed_home import ManagedHome
from trinity.workflow.execution import ExecutionProtocol
from trinity.workflow.lifecycle import LifecycleGuard
from trinity.workflow.models import DecisionRecord, ExecutionResult, WorkPackage
from trinity.workflow.review import ReviewPackage, ReviewResult
from trinity.workflow.review_execution import ReviewExecutionProtocol

logger = logging.getLogger(__name__)


SYNTHESIS_PROVIDER_PRIORITY: tuple[Provider, ...] = (
    Provider.CODEX,
    Provider.CLAUDE_CODE,
    Provider.ANTIGRAVITY_CLI,
)

SYNTHESIS_FAST_MODELS: dict[Provider, str] = {
    Provider.CODEX: "default",
    Provider.CLAUDE_CODE: "sonnet",
    Provider.ANTIGRAVITY_CLI: "default",
}

SYNTHESIS_STRONG_MODELS: dict[Provider, str] = {
    Provider.CODEX: "default",
    Provider.CLAUDE_CODE: "opus",
    Provider.ANTIGRAVITY_CLI: "default",
}


@dataclass(frozen=True)
class AgentLaunchContext:
    """Prepared launch paths for a single active agent."""

    agent_name: str
    cwd: Path
    env_overrides: dict[str, str] = field(default_factory=dict)
    managed_home: Path | None = None
    workspace_path: Path | None = None


class _UnavailableSynthesisAgent:
    """Primary synthesis stub that records why model synthesis is unavailable."""

    def __init__(self, reason: str):
        self.reason = reason

    async def synthesize(self, synthesis_input):
        raise RuntimeError(self.reason)


class TrinityOrchestrator:
    """Owns all components and drives the deliberation lifecycle."""

    def __init__(
        self,
        config: TrinityConfig,
        interactive: bool | None = None,
        *,
        target_workspace: Path | None = None,
        allow_control_repo_writes: bool = False,
        provider_sessions: Mapping[str, object] | None = None,
        active_agent_names: tuple[str, ...] | list[str] = (),
        agent_model_overrides: Mapping[str, str] | None = None,
    ):
        self.config = config
        self.target_workspace = target_workspace.resolve() if target_workspace else None
        self.allow_control_repo_writes = allow_control_repo_writes
        self.provider_sessions = dict(provider_sessions or {})
        self.active_agent_names = tuple(
            str(name).strip() for name in active_agent_names if str(name).strip()
        )
        self.agent_model_overrides = {
            str(name).strip(): str(model).strip()
            for name, model in dict(agent_model_overrides or {}).items()
            if str(name).strip() and str(model).strip()
        }
        self.transport_mode = config.transport_mode
        self.interactive = (
            self.transport_mode == "tmux" if interactive is None else interactive
        )
        if interactive is not None:
            self.transport_mode = "tmux" if interactive else "one-shot"
        self.agents: dict[str, AgentWrapper] = {}
        self.shared: SharedContextEngine | None = None
        self.protocol: DeliberationProtocol | None = None
        self.execution_protocol: ExecutionProtocol | None = None
        self.review_protocol: ReviewExecutionProtocol | None = None
        self.tmux_manager: TmuxSessionManager | None = None
        self.context_monitor: ContextMonitor | None = None
        self.session_rotator: SessionRotator | None = None
        self.health_checker: HealthChecker | None = None
        self.readiness_gate: ProviderReadinessGate | None = None
        self.lifecycle_guard: LifecycleGuard | None = None
        self.readiness_results: dict[str, ReadinessResult] = {}
        self.synthesis_status: dict[str, object] = {}
        self.managed_home: ManagedHome | None = None
        self.workspace_isolation: WorkspaceIsolation | None = None
        self.agent_launch_contexts: dict[str, AgentLaunchContext] = {}
        self._event_bus = None

    def set_event_bus(self, bus) -> None:
        """Set the TUI event bus for real-time deliberation updates.

        Args:
            bus: A TUIEventBus instance from trinity.tui.events.
        """
        self._event_bus = bus
        if self.protocol:
            self.protocol._event_callback = bus.emit
        if self.execution_protocol:
            self.execution_protocol._event_callback = bus.emit
        if self.review_protocol:
            self.review_protocol._event_callback = bus.emit

    def _configured_active_agents(self) -> dict[str, AgentSpec]:
        """Return the active agent projection for this invocation."""
        active_agents = dict(self.config.active_agents)
        if self.active_agent_names:
            requested = set(self.active_agent_names)
            active_agents = {
                name: spec for name, spec in active_agents.items() if name in requested
            }
        if not self.agent_model_overrides:
            return active_agents
        return {
            name: (
                replace(spec, model=self.agent_model_overrides[name])
                if name in self.agent_model_overrides
                else spec
            )
            for name, spec in active_agents.items()
        }

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
        active_agents = self._configured_active_agents()
        self._prepare_agent_launch_contexts(active_agents, state_dir)

        # Create shared context engine
        self.shared = SharedContextEngine(
            path=self.config.shared_context_path,
            keep_sections=self.config.keep_sections,
            max_read_bytes=self.config.shared_max_bytes,
            section_entry_max_chars=self.config.shared_section_entry_max_chars,
            memory_index_enabled=self.config.memory_index_enabled,
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
        self.lifecycle_guard = LifecycleGuard(
            rotate_threshold=self.config.context_rotate_threshold,
            check_readiness=False,
        )
        consensus_engine = ConsensusEngine(
            required_fraction=self.config.consensus_threshold,
        )
        synthesis_agent = self._create_synthesis_agent(state_dir, consensus_engine)
        self.protocol = DeliberationProtocol(
            agents=self.agents,
            shared=self.shared,
            consensus_engine=consensus_engine,
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
            response_artifact_dir=state_dir / "responses",
            synthesis_agent=synthesis_agent,
            lifecycle_guard=self.lifecycle_guard,
            rotation_callback=self._rotate_agent_for_lifecycle,
        )
        self.execution_protocol = ExecutionProtocol(
            agents=self.agents,
            shared=self.shared,
            artifact_dir=state_dir / "execution",
            timeout=self.config.execution_timeout_seconds,
            event_callback=event_callback,
            lifecycle_guard=self.lifecycle_guard,
            rotation_callback=self._rotate_agent_for_lifecycle,
            parallel_policy=ParallelExecutionPolicy(
                shared_write_paths=self.config.parallel_shared_write_paths,
                broad_write_paths=self.config.parallel_broad_write_paths,
            ),
            target_workspace=self.target_workspace,
            control_repo=self.config.project_dir,
            allow_control_repo_writes=self.allow_control_repo_writes,
        )
        self.review_protocol = ReviewExecutionProtocol(
            agents=self.agents,
            shared=self.shared,
            artifact_dir=state_dir / "reviews",
            timeout=self.config.execution_timeout_seconds,
            event_callback=event_callback,
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
        self.readiness_gate = ProviderReadinessGate(
            timeout=self.config.provider_readiness_timeout_seconds,
        )

    def _prepare_agent_launch_contexts(
        self, active_agents: dict[str, AgentSpec], state_dir: Path
    ) -> None:
        """Prepare per-agent cwd/env metadata before wrappers are created."""
        self.agent_launch_contexts = {}
        workspace_root = (
            self.target_workspace
            if self.target_workspace is not None
            else self.config.project_dir.resolve()
        )
        provider_state_mode = self.config.provider_state_mode.lower()
        self.managed_home = (
            ManagedHome(state_dir=state_dir)
            if provider_state_mode == "isolated"
            else None
        )

        needs_worktree = any(
            spec.workspace_mode == "git-worktree" for spec in active_agents.values()
        )
        workspace_state_dir = (
            workspace_root / ".trinity" / "workspace"
            if self.target_workspace is not None
            else state_dir / "workspace"
        )
        self.workspace_isolation = (
            WorkspaceIsolation(
                project_root=workspace_root,
                state_dir=workspace_state_dir,
            )
            if needs_worktree
            else None
        )

        for name, spec in active_agents.items():
            managed_home: Path | None = None
            env_overrides: dict[str, str] = {}
            if self.managed_home is not None:
                provider_name = getattr(spec.provider, "value", str(spec.provider))
                managed_home = self.managed_home.setup(name, provider=provider_name)
                env_overrides = self.managed_home.get_env_overrides(name)

            cwd = workspace_root.resolve()
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

    def _create_synthesis_agent(
        self,
        state_dir: Path,
        consensus_engine: ConsensusEngine,
    ) -> SynthesisAgent:
        """Create the configured central synthesis agent."""
        heuristic = HeuristicSynthesisAgent(consensus_engine=consensus_engine)
        mode = self.config.synthesis_mode.lower()
        self.synthesis_status = {
            "mode": mode,
            "source": "heuristic",
            "fallback_used": mode != "heuristic",
        }
        if mode == "heuristic":
            self.synthesis_status["fallback_used"] = False
            return heuristic

        try:
            model_agent = self._create_model_synthesis_agent(state_dir)
        except RuntimeError as exc:
            reason = str(exc)
            self.synthesis_status.update(
                {
                    "source": "heuristic",
                    "fallback_used": True,
                    "fallback_reason": reason,
                }
            )
            return FallbackSynthesisAgent(
                primary=_UnavailableSynthesisAgent(reason),
                fallback=heuristic,
            )

        self.synthesis_status.update(
            {
                "source": "model-backed",
                "fallback_used": False,
                "provider": model_agent.provider.value,
                "provider_agent": model_agent.agent_name,
                "model": model_agent.model,
                "requested_model": model_agent.requested_model,
            }
        )
        return FallbackSynthesisAgent(primary=model_agent, fallback=heuristic)

    def _create_model_synthesis_agent(self, state_dir: Path) -> ModelBackedSynthesisAgent:
        """Build a provider-backed synthesizer from an active agent launch context."""
        agent_name, spec = self._select_synthesis_provider()
        invoker = self._invoker_for_provider(spec.provider)
        context = self.agent_launch_contexts.get(agent_name)
        cwd = context.cwd if context is not None else self.config.project_dir.resolve()
        env = dict(context.env_overrides) if context is not None else {}
        return ModelBackedSynthesisAgent(
            invoker=invoker,
            agent_name=agent_name,
            provider=spec.provider,
            cli_command=spec.cli_command,
            cwd=cwd,
            env=env,
            model=self._resolve_synthesis_model(spec),
            requested_model=self.config.synthesis_model,
            extra_args=tuple(spec.extra_args),
            timeout_seconds=self.config.synthesis_timeout_seconds,
            max_input_chars=self.config.synthesis_max_input_chars,
            artifact_dir=state_dir / "synthesis",
            lang=self.config.lang,
        )

    def _select_synthesis_provider(self) -> tuple[str, AgentSpec]:
        """Select an enabled one-shot provider by fixed synthesis priority."""
        active_specs = (
            {name: agent.spec for name, agent in self.agents.items()}
            if self.agents
            else self.config.active_agents
        )
        override = self.config.synthesis_agent.strip()
        if override:
            spec = active_specs.get(override)
            if spec is None:
                raise RuntimeError(
                    f"synthesis_agent {override!r} is not an enabled active agent"
                )
            if spec.provider not in self._supported_synthesis_providers():
                raise RuntimeError(
                    f"synthesis_agent {override!r} uses unsupported provider "
                    f"{spec.provider.value!r}"
                )
            return override, spec

        for provider in SYNTHESIS_PROVIDER_PRIORITY:
            for name, spec in active_specs.items():
                if spec.provider == provider:
                    return name, spec
        raise RuntimeError("no active provider supports model-backed synthesis")

    def _resolve_synthesis_model(self, spec: AgentSpec) -> str:
        """Resolve synthesis_model using provider-specific quality tiers."""
        requested = (self.config.synthesis_model or "strong").strip()
        if requested in {"agent-default", "agent_default"}:
            return spec.model or "default"
        if spec.provider == Provider.CODEX and requested in {"fast", "strong"}:
            return spec.model or "default"
        if requested == "fast":
            return SYNTHESIS_FAST_MODELS.get(spec.provider, "default")
        if requested == "strong":
            return SYNTHESIS_STRONG_MODELS.get(spec.provider, "default")
        if requested:
            return requested
        return spec.model or "default"

    @staticmethod
    def _supported_synthesis_providers() -> set[Provider]:
        return set(SYNTHESIS_PROVIDER_PRIORITY)

    @staticmethod
    def _invoker_for_provider(provider: Provider) -> ProviderInvoker:
        if provider == Provider.CLAUDE_CODE:
            return ClaudePrintInvoker()
        if provider == Provider.CODEX:
            return CodexExecInvoker()
        if provider == Provider.ANTIGRAVITY_CLI:
            return AntigravityPrintInvoker()
        raise RuntimeError(f"unsupported synthesis provider: {provider.value}")

    def _init_print_mode(self, active_agents: dict[str, AgentSpec] | None = None) -> None:
        """Initialize agents in print mode (Phase 1 — subprocess-based)."""
        for name, spec in (active_agents or self.config.active_agents).items():
            agent = self._create_print_agent(spec)
            self._apply_launch_context(name, agent)
            self._apply_provider_session(name, agent)
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
                self._apply_provider_session(name, agent)
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
            self._apply_provider_session(name, agent)
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

    def _apply_provider_session(self, agent_name: str, agent: AgentWrapper) -> None:
        """Attach the latest provider session id restored from workflow state."""
        session = self._provider_session_for_agent(agent_name)
        if session:
            agent.configure_provider_session(session)

    def _provider_session_for_agent(self, agent_name: str) -> str:
        """Return latest read-only provider session id for an agent."""
        candidates: list[tuple[float, str]] = []
        for value in self.provider_sessions.values():
            if isinstance(value, Mapping):
                item_agent = str(value.get("agent_name", ""))
                item_access = str(value.get("access", ""))
                session_id = str(value.get("provider_session_id", ""))
                observed_at = float(value.get("last_observed_at", 0) or 0)
            else:
                item_agent = str(getattr(value, "agent_name", ""))
                item_access = str(getattr(value, "access", ""))
                session_id = str(getattr(value, "provider_session_id", ""))
                observed_at = float(getattr(value, "last_observed_at", 0) or 0)
            if item_agent != agent_name or not session_id:
                continue
            if item_access and item_access != "read-only":
                continue
            candidates.append((observed_at, session_id))
        if not candidates:
            return ""
        return sorted(candidates, reverse=True)[0][1]

    async def ask(self, prompt: str) -> DeliberationResult:
        """Main entry point: run deliberation on a user prompt."""
        self._ensure_initialized()

        logger.info(f"Starting deliberation: {prompt[:100]}...")
        start_time = time.time()

        await self._ensure_agents_started()

        readiness_failure = self._check_provider_readiness(prompt, start_time)
        if readiness_failure is not None:
            return readiness_failure

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

    async def execute_work_packages(
        self,
        work_packages: list[WorkPackage],
        decisions: list[DecisionRecord] | None = None,
        result_callback: Callable[[ExecutionResult], None] | None = None,
    ) -> list[ExecutionResult]:
        """Execute approved workflow work packages with active agents."""
        self._ensure_initialized()
        if not self.execution_protocol:
            raise RuntimeError("Execution protocol was not initialized")
        await self._ensure_agents_started()
        run_kwargs = {"decisions": decisions or []}
        if result_callback is not None:
            run_kwargs["result_callback"] = result_callback
        return await self.execution_protocol.run(
            work_packages,
            **run_kwargs,
        )

    async def review_work_packages(
        self,
        review_packages: list[ReviewPackage],
        work_packages: list[WorkPackage],
        execution_results: list[ExecutionResult],
    ) -> list[ReviewResult]:
        """Run provider-backed reviews for completed work packages."""
        self._ensure_initialized()
        if not self.review_protocol:
            raise RuntimeError("Review protocol was not initialized")
        await self._ensure_agents_started()
        return await self.review_protocol.review_work_packages(
            review_packages,
            work_packages,
            execution_results,
        )

    async def review_final_execution(
        self,
        work_packages: list[WorkPackage],
        execution_results: list[ExecutionResult],
        review_results: list[ReviewResult],
    ) -> ReviewResult:
        """Run the final whole-project review with codex/claude/antigravity fallback."""
        self._ensure_initialized()
        if not self.review_protocol:
            raise RuntimeError("Review protocol was not initialized")
        await self._ensure_agents_started()
        return await self.review_protocol.review_final_execution(
            work_packages,
            execution_results,
            review_results,
        )

    async def _ensure_agents_started(self) -> None:
        """Start active agents before a deliberation or execution-only run."""
        for name, agent in self.agents.items():
            try:
                alive = await agent.is_alive()
            except Exception:
                alive = False
            if alive:
                continue
            role_prompt = agent.spec.role_prompt or ""
            await agent.start(initial_prompt=role_prompt)

    async def _rotate_agent_for_lifecycle(self, agent_name: str) -> bool:
        """Rotate one agent when lifecycle guard recommends it."""
        if not self.session_rotator:
            return False
        logger.info("[%s] Lifecycle guard requested session rotation", agent_name)
        return await self.session_rotator.rotate(agent_name)

    def _check_provider_readiness(
        self,
        prompt: str,
        start_time: float,
    ) -> DeliberationResult | None:
        """Run provider readiness checks and enforce configured policy."""
        if not self.readiness_gate:
            return None

        self.readiness_results = self.readiness_gate.check_all(self.agents)
        for result in self.readiness_results.values():
            self._emit_readiness(result)

        not_ready = {
            name: result
            for name, result in self.readiness_results.items()
            if not result.ready
        }
        if not not_ready:
            return None

        mode = self.config.provider_readiness_mode.lower()
        ready_agents = {
            name: agent
            for name, agent in self.agents.items()
            if self.readiness_results.get(name)
            and self.readiness_results[name].ready
        }

        if mode == "degraded" and ready_agents:
            logger.warning(
                "Provider readiness degraded mode: continuing with ready agents: %s",
                ", ".join(ready_agents),
            )
            self._apply_ready_agents(ready_agents)
            return None

        logger.warning("Provider readiness failed; deliberation will not start")
        result = self._build_readiness_failure_result(
            prompt=prompt,
            readiness=not_ready,
            start_time=start_time,
        )
        self._emit_deliberation_done()
        return result

    def _apply_ready_agents(self, ready_agents: dict[str, AgentWrapper]) -> None:
        """Restrict runtime components to the agents that passed readiness."""
        self.agents = ready_agents
        if self.protocol:
            self.protocol.agents = ready_agents
            self.protocol.synthesis_agent = self._create_synthesis_agent(
                self.config.effective_state_dir,
                self.protocol.consensus_engine,
            )
        if self.execution_protocol:
            self.execution_protocol.agents = ready_agents
        if self.review_protocol:
            self.review_protocol.agents = ready_agents
        if self.context_monitor:
            self.context_monitor.agents = ready_agents
        if self.session_rotator:
            self.session_rotator.agents = ready_agents
        if self.health_checker:
            self.health_checker.agents = ready_agents

    def _build_readiness_failure_result(
        self,
        prompt: str,
        readiness: dict[str, ReadinessResult],
        start_time: float,
    ) -> DeliberationResult:
        """Build a user-facing result explaining readiness failures."""
        lines = [
            "Provider readiness check failed. Deliberation was not started.",
            "",
        ]
        for name, result in readiness.items():
            lines.append(
                f"- {name} ({result.provider.value}): {result.state.value} - "
                f"{result.reason}"
            )
            if result.action_hint:
                lines.append(f"  Action: {result.action_hint}")
            if result.excerpt:
                lines.append("  Pane excerpt:")
                for excerpt_line in result.excerpt.splitlines()[-4:]:
                    lines.append(f"    {excerpt_line}")

        summary = "\n".join(lines)
        return DeliberationResult(
            user_prompt=prompt,
            rounds_completed=0,
            consensus=ConsensusResult(
                reached=False,
                agreement_count=0,
                total_agents=len(self.agents),
                opinions={name: result.reason for name, result in readiness.items()},
                summary=summary,
            ),
            tasks=[],
            total_tokens_used=0,
            duration_seconds=time.time() - start_time,
        )

    def _emit_readiness(self, result: ReadinessResult) -> None:
        """Emit a provider readiness TUI event."""
        if not self._event_bus:
            return
        self._event_bus.emit(
            TUIEvent(
                type=TUIEventType.PROVIDER_READINESS,
                data={
                    "agent": result.agent_name,
                    "provider": result.provider.value,
                    "ready": result.ready,
                    "state": result.state.value,
                    "reason": result.reason,
                    "action_hint": result.action_hint,
                    "excerpt": result.excerpt,
                },
            )
        )

    def _emit_deliberation_done(self) -> None:
        """Emit the completion event when deliberation is skipped."""
        if self._event_bus:
            self._event_bus.emit(TUIEvent(type=TUIEventType.DELIBERATION_DONE))

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
                    "readiness": (
                        self.readiness_results[name].state.value
                        if name in self.readiness_results
                        else "unknown"
                    ),
                    "readiness_reason": (
                        self.readiness_results[name].reason
                        if name in self.readiness_results
                        else ""
                    ),
                    "readiness_action_hint": (
                        self.readiness_results[name].action_hint
                        if name in self.readiness_results
                        else ""
                    ),
                }
                for name, agent in self.agents.items()
            },
            "shared_context_path": str(self.config.shared_context_path),
            "max_rounds": self.config.max_deliberation_rounds,
            "interactive": self.interactive,
            "transport_mode": self.transport_mode,
            "target_workspace": str(self.target_workspace) if self.target_workspace else "",
            "tmux_session": (
                self.config.session_name if self.tmux_manager else None
            ),
            "synthesis": dict(self.synthesis_status),
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
