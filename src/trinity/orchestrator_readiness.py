"""Provider readiness runtime used by TrinityOrchestrator."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from trinity.agents.base import AgentWrapper
from trinity.config import TrinityConfig
from trinity.models import ConsensusResult, DeliberationResult
from trinity.providers.policy import InvocationAccess
from trinity.providers.readiness import (
    OneShotProviderPreflight,
    ProviderReadinessGate,
    ReadinessResult,
)
from trinity.tui.events import TUIEvent, TUIEventType

logger = logging.getLogger(__name__)


ReadinessResults = dict[str, ReadinessResult]
EventEmitter = Callable[[TUIEvent], None]


@dataclass(frozen=True)
class ReadinessRuntimeOutcome:
    """State changes produced by a readiness runtime check."""

    failure_result: DeliberationResult | None = None
    readiness_results: ReadinessResults | None = None
    one_shot_readiness_results: ReadinessResults | None = None
    ready_agents: dict[str, AgentWrapper] | None = None
    emit_deliberation_done: bool = False


class OrchestratorReadinessRuntime:
    """Run provider readiness checks outside the top-level orchestrator."""

    def __init__(
        self,
        *,
        config: TrinityConfig,
        interactive: bool,
        agents: Mapping[str, AgentWrapper],
        readiness_gate: ProviderReadinessGate | None,
        one_shot_preflight: OneShotProviderPreflight | None,
        event_emit: EventEmitter | None = None,
    ) -> None:
        self.config = config
        self.interactive = interactive
        self.agents = dict(agents)
        self.readiness_gate = readiness_gate
        self.one_shot_preflight = one_shot_preflight
        self.event_emit = event_emit

    def check_provider_readiness(
        self,
        *,
        prompt: str,
        start_time: float,
    ) -> ReadinessRuntimeOutcome:
        """Run startup readiness checks and return the orchestration outcome."""
        if not self.interactive and self.one_shot_preflight:
            return self.check_one_shot_provider_readiness(
                prompt=prompt,
                start_time=start_time,
                access=InvocationAccess.READ_ONLY,
            )
        if not self.readiness_gate:
            return ReadinessRuntimeOutcome()

        readiness = dict(self.readiness_gate.check_all(self.agents))
        self._emit_all(readiness)
        not_ready = self._not_ready(readiness)
        if not not_ready:
            return ReadinessRuntimeOutcome(readiness_results=readiness)

        ready_agents = self._ready_agents(readiness)
        if self._can_degrade(ready_agents):
            logger.warning(
                "Provider readiness degraded mode: continuing with ready agents: %s",
                ", ".join(ready_agents),
            )
            return ReadinessRuntimeOutcome(
                readiness_results=readiness,
                ready_agents=ready_agents,
            )

        logger.warning("Provider readiness failed; deliberation will not start")
        return ReadinessRuntimeOutcome(
            failure_result=build_readiness_failure_result(
                prompt=prompt,
                agents=self.agents,
                readiness=not_ready,
                start_time=start_time,
            ),
            readiness_results=readiness,
            emit_deliberation_done=True,
        )

    def check_one_shot_provider_readiness(
        self,
        *,
        prompt: str,
        start_time: float,
        access: InvocationAccess,
    ) -> ReadinessRuntimeOutcome:
        """Run one-shot preflight for deliberation startup."""
        if not self.one_shot_preflight:
            return ReadinessRuntimeOutcome()

        readiness = dict(self.one_shot_preflight.check_all(self.agents, access=access))
        self._emit_all(readiness)
        not_ready = self._not_ready(readiness)
        if not not_ready:
            return ReadinessRuntimeOutcome(
                readiness_results=readiness,
                one_shot_readiness_results=readiness,
            )

        ready_agents = self._ready_agents(readiness)
        if self._can_degrade(ready_agents):
            logger.warning(
                "One-shot provider preflight degraded mode: continuing with "
                "ready agents: %s",
                ", ".join(ready_agents),
            )
            return ReadinessRuntimeOutcome(
                readiness_results=readiness,
                one_shot_readiness_results=readiness,
                ready_agents=ready_agents,
            )

        logger.warning("One-shot provider preflight failed; deliberation will not start")
        return ReadinessRuntimeOutcome(
            failure_result=build_readiness_failure_result(
                prompt=prompt,
                agents=self.agents,
                readiness=not_ready,
                start_time=start_time,
            ),
            readiness_results=readiness,
            one_shot_readiness_results=readiness,
            emit_deliberation_done=True,
        )

    def ensure_one_shot_preflight_or_raise(
        self,
        *,
        access: InvocationAccess,
    ) -> ReadinessRuntimeOutcome:
        """Fail fast before execution/review one-shot provider dispatch."""
        if self.interactive or not self.one_shot_preflight:
            return ReadinessRuntimeOutcome()

        readiness = dict(self.one_shot_preflight.check_all(self.agents, access=access))
        self._emit_all(readiness)
        not_ready = self._not_ready(readiness)
        if not not_ready:
            return ReadinessRuntimeOutcome(
                readiness_results=readiness,
                one_shot_readiness_results=readiness,
            )

        ready_agents = self._ready_agents(readiness)
        if self._can_degrade(ready_agents):
            logger.warning(
                "One-shot provider preflight degraded mode: continuing with "
                "ready agents: %s",
                ", ".join(ready_agents),
            )
            return ReadinessRuntimeOutcome(
                readiness_results=readiness,
                one_shot_readiness_results=readiness,
                ready_agents=ready_agents,
            )

        summary = format_readiness_failure(
            not_ready,
            intro="Provider readiness check failed. Provider dispatch was not started.",
        )
        raise RuntimeError(summary)

    def _not_ready(self, readiness: ReadinessResults) -> ReadinessResults:
        return {name: result for name, result in readiness.items() if not result.ready}

    def _ready_agents(self, readiness: ReadinessResults) -> dict[str, AgentWrapper]:
        return {
            name: agent
            for name, agent in self.agents.items()
            if readiness.get(name) and readiness[name].ready
        }

    def _can_degrade(self, ready_agents: Mapping[str, AgentWrapper]) -> bool:
        return self.config.provider_readiness_mode.lower() == "degraded" and bool(
            ready_agents
        )

    def _emit_all(self, readiness: ReadinessResults) -> None:
        for result in readiness.values():
            emit_readiness(self.event_emit, result)


def build_readiness_failure_result(
    *,
    prompt: str,
    agents: Mapping[str, AgentWrapper],
    readiness: ReadinessResults,
    start_time: float,
) -> DeliberationResult:
    """Build a user-facing result explaining readiness failures."""
    summary = format_readiness_failure(readiness)
    return DeliberationResult(
        user_prompt=prompt,
        rounds_completed=0,
        consensus=ConsensusResult(
            reached=False,
            agreement_count=0,
            total_agents=len(agents),
            opinions={name: result.reason for name, result in readiness.items()},
            summary=summary,
        ),
        tasks=[],
        total_tokens_used=0,
        duration_seconds=time.time() - start_time,
    )


def format_readiness_failure(
    readiness: ReadinessResults,
    *,
    intro: str = "Provider readiness check failed. Deliberation was not started.",
) -> str:
    """Format provider readiness failures for user-facing messages."""
    lines = [
        intro,
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
            lines.append("  Excerpt:")
            for excerpt_line in result.excerpt.splitlines()[-4:]:
                lines.append(f"    {excerpt_line}")
    return "\n".join(lines)


def emit_readiness(event_emit: EventEmitter | None, result: ReadinessResult) -> None:
    """Emit a provider readiness TUI event."""
    if not event_emit:
        return
    event_emit(
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


def emit_deliberation_done(event_emit: EventEmitter | None) -> None:
    """Emit the completion event when deliberation is skipped."""
    if event_emit:
        event_emit(TUIEvent(type=TUIEventType.DELIBERATION_DONE))


def one_shot_status(
    readiness: Mapping[str, ReadinessResult],
    agent_name: str,
) -> dict[str, object]:
    """Return one-shot preflight diagnostics for status output."""
    result = readiness.get(agent_name)
    if result is None:
        return {}
    return {
        "cwd": getattr(result, "cwd", ""),
        "cli_command": getattr(result, "cli_command", ""),
        "resolved_executable": getattr(result, "resolved_executable", ""),
        "model": getattr(result, "model", "default"),
        "model_source": getattr(result, "model_source", "unavailable"),
        "model_source_reason": getattr(result, "model_source_reason", ""),
        "discovered_models": list(getattr(result, "discovered_models", ())),
        "access": getattr(getattr(result, "access", None), "value", ""),
        "permission_args": list(getattr(result, "permission_args", ())),
        "permission_extra_args": list(getattr(result, "permission_extra_args", ())),
        "permission_diagnostics": list(getattr(result, "permission_diagnostics", ())),
    }
