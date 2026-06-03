"""Lifecycle guard hooks for workflow rotation and provider health checks.

The guard is intentionally integration-free: it evaluates current agent state and
returns structured actions for the caller to execute. It does not rotate,
restart, skip, or wait on its own.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from trinity.models import ContextUsage, Provider
from trinity.providers.readiness import (
    ProviderReadinessGate,
    ProviderState,
    ReadinessResult,
)


class LifecycleHook(str, Enum):
    """Workflow hook points guarded by lifecycle checks."""

    BEFORE_AGENT_CALL = "before_agent_call"
    AFTER_AGENT_CALL = "after_agent_call"
    BEFORE_ROUND = "before_round"
    AFTER_ROUND = "after_round"
    BEFORE_WORK_PACKAGE = "before_work_package"
    AFTER_WORK_PACKAGE = "after_work_package"


class LifecycleActionKind(str, Enum):
    """Action a workflow caller should consider after a lifecycle check."""

    CONTINUE = "continue"
    ROTATE_SESSION = "rotate_session"
    WAIT_FOR_READY = "wait_for_ready"
    RESTART_PROCESS = "restart_process"
    SKIP_AGENT = "skip_agent"


class LifecycleReason(str, Enum):
    """Reason that produced a lifecycle action."""

    OK = "ok"
    CONTEXT_THRESHOLD = "context_threshold"
    PROCESS_NOT_ALIVE = "process_not_alive"
    READINESS_UNAVAILABLE = "readiness_unavailable"
    PROJECTED_RATIO = "projected_ratio"
    AGENT_UNAVAILABLE = "agent_unavailable"


@dataclass(frozen=True)
class LifecycleAction:
    """One structured lifecycle action/recommendation."""

    kind: LifecycleActionKind
    reason: LifecycleReason
    agent_name: str | None = None
    message: str = ""
    recommendation: str = ""
    blocking: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "kind": self.kind.value,
            "reason": self.reason.value,
            "agent_name": self.agent_name,
            "message": self.message,
            "recommendation": self.recommendation,
            "blocking": self.blocking,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class LifecycleDecision:
    """Result returned from a lifecycle guard hook."""

    hook: LifecycleHook
    actions: tuple[LifecycleAction, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def recommendations(self) -> tuple[str, ...]:
        """Return non-empty recommendation strings from actions."""
        return tuple(action.recommendation for action in self.actions if action.recommendation)

    @property
    def blocking_actions(self) -> tuple[LifecycleAction, ...]:
        """Return actions that should block the next workflow step."""
        return tuple(action for action in self.actions if action.blocking)

    @property
    def can_continue(self) -> bool:
        """Return True when no blocking action was recommended."""
        return not self.blocking_actions

    @property
    def needs_rotation(self) -> bool:
        """Return True when any agent should be rotated."""
        return any(
            action.kind == LifecycleActionKind.ROTATE_SESSION
            for action in self.actions
        )

    @property
    def rotation_agents(self) -> tuple[str, ...]:
        """Return agents with session rotation recommendations."""
        return tuple(
            action.agent_name
            for action in self.actions
            if action.kind == LifecycleActionKind.ROTATE_SESSION
            and action.agent_name is not None
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "hook": self.hook.value,
            "actions": [action.to_dict() for action in self.actions],
            "recommendations": list(self.recommendations),
            "can_continue": self.can_continue,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LifecycleTarget:
    """Normalized input used by the guard evaluator."""

    agent_name: str
    provider: Provider | None
    context_usage: ContextUsage
    process_alive: bool | None = None
    readiness: ReadinessResult | None = None
    readiness_error: str = ""


class LifecycleGuard:
    """Evaluate lifecycle hooks and return caller-executable actions.

    The guard covers the MVP checks needed before and after workflow traffic:
    context threshold, process liveness, provider readiness, and projected
    context ratio for planned calls.
    """

    def __init__(
        self,
        rotate_threshold: float = 0.60,
        projected_threshold: float | None = None,
        readiness_gate: ProviderReadinessGate | None = None,
        check_readiness: bool = True,
    ):
        self.rotate_threshold = rotate_threshold
        self.projected_threshold = (
            rotate_threshold if projected_threshold is None else projected_threshold
        )
        self.readiness_gate = readiness_gate or ProviderReadinessGate()
        self.check_readiness = check_readiness

    def before_agent_call(
        self,
        agent: Any,
        *,
        projected_tokens: int = 0,
        readiness: ReadinessResult | None = None,
        process_alive: bool | None = None,
    ) -> LifecycleDecision:
        """Check an agent immediately before a provider request."""
        target = self._target_from_agent(
            agent,
            readiness=readiness,
            process_alive=process_alive,
        )
        return self._decision(
            LifecycleHook.BEFORE_AGENT_CALL,
            [target],
            {target.agent_name: projected_tokens},
        )

    def after_agent_call(
        self,
        agent: Any,
        *,
        token_usage: ContextUsage | None = None,
        readiness: ReadinessResult | None = None,
        process_alive: bool | None = None,
    ) -> LifecycleDecision:
        """Check an agent immediately after a provider response."""
        target = self._target_from_agent(
            agent,
            token_usage=token_usage,
            readiness=readiness,
            process_alive=process_alive,
        )
        return self._decision(LifecycleHook.AFTER_AGENT_CALL, [target])

    def before_round(
        self,
        agents: Mapping[str, Any] | Iterable[Any],
        *,
        projected_tokens_by_agent: Mapping[str, int] | None = None,
        readiness_by_agent: Mapping[str, ReadinessResult] | None = None,
        process_alive_by_agent: Mapping[str, bool] | None = None,
    ) -> LifecycleDecision:
        """Check all active agents before a deliberation/user-decision round."""
        targets = self._targets_from_agents(
            agents,
            readiness_by_agent=readiness_by_agent,
            process_alive_by_agent=process_alive_by_agent,
        )
        return self._decision(
            LifecycleHook.BEFORE_ROUND,
            targets,
            dict(projected_tokens_by_agent or {}),
        )

    def after_round(
        self,
        agents: Mapping[str, Any] | Iterable[Any],
        *,
        readiness_by_agent: Mapping[str, ReadinessResult] | None = None,
        process_alive_by_agent: Mapping[str, bool] | None = None,
    ) -> LifecycleDecision:
        """Check all active agents after a deliberation/user-decision round."""
        targets = self._targets_from_agents(
            agents,
            readiness_by_agent=readiness_by_agent,
            process_alive_by_agent=process_alive_by_agent,
        )
        return self._decision(LifecycleHook.AFTER_ROUND, targets)

    def before_work_package(
        self,
        package: Any,
        agents: Mapping[str, Any] | Iterable[Any],
        *,
        projected_tokens: int = 0,
        readiness: ReadinessResult | None = None,
        process_alive: bool | None = None,
    ) -> LifecycleDecision:
        """Check the owner agent before a work package is dispatched."""
        return self._work_package_decision(
            LifecycleHook.BEFORE_WORK_PACKAGE,
            package,
            agents,
            projected_tokens=projected_tokens,
            readiness=readiness,
            process_alive=process_alive,
        )

    def after_work_package(
        self,
        package: Any,
        agents: Mapping[str, Any] | Iterable[Any],
        *,
        readiness: ReadinessResult | None = None,
        process_alive: bool | None = None,
    ) -> LifecycleDecision:
        """Check the owner agent after a work package finishes."""
        return self._work_package_decision(
            LifecycleHook.AFTER_WORK_PACKAGE,
            package,
            agents,
            readiness=readiness,
            process_alive=process_alive,
        )

    def _work_package_decision(
        self,
        hook: LifecycleHook,
        package: Any,
        agents: Mapping[str, Any] | Iterable[Any],
        *,
        projected_tokens: int = 0,
        readiness: ReadinessResult | None = None,
        process_alive: bool | None = None,
    ) -> LifecycleDecision:
        owner = str(getattr(package, "owner_agent", ""))
        package_id = str(getattr(package, "id", ""))
        agent = self._agent_by_name(agents, owner)
        metadata = {"package_id": package_id, "owner_agent": owner}
        if agent is None:
            action = LifecycleAction(
                kind=LifecycleActionKind.SKIP_AGENT,
                reason=LifecycleReason.AGENT_UNAVAILABLE,
                agent_name=owner or None,
                message=f"Owner agent '{owner}' is not available for package {package_id}.",
                recommendation=f"Skip package {package_id} or assign it to an active agent.",
                blocking=True,
                details=metadata,
            )
            return LifecycleDecision(hook=hook, actions=(action,), metadata=metadata)

        target = self._target_from_agent(
            agent,
            readiness=readiness,
            process_alive=process_alive,
        )
        return self._decision(
            hook,
            [target],
            {target.agent_name: projected_tokens},
            metadata=metadata,
        )

    def _decision(
        self,
        hook: LifecycleHook,
        targets: Iterable[LifecycleTarget],
        projected_tokens_by_agent: Mapping[str, int] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> LifecycleDecision:
        actions: list[LifecycleAction] = []
        projected = projected_tokens_by_agent or {}
        checked_agents: list[str] = []

        for target in targets:
            checked_agents.append(target.agent_name)
            actions.extend(
                self._actions_for_target(
                    target,
                    projected_tokens=max(0, int(projected.get(target.agent_name, 0))),
                )
            )

        decision_metadata = {
            "checked_agents": checked_agents,
            "rotate_threshold": self.rotate_threshold,
            "projected_threshold": self.projected_threshold,
        }
        decision_metadata.update(dict(metadata or {}))

        if not actions:
            actions.append(
                LifecycleAction(
                    kind=LifecycleActionKind.CONTINUE,
                    reason=LifecycleReason.OK,
                    message=f"{hook.value} passed lifecycle checks.",
                    recommendation="Continue workflow.",
                    details={"checked_agents": checked_agents},
                )
            )

        return LifecycleDecision(
            hook=hook,
            actions=tuple(actions),
            metadata=decision_metadata,
        )

    def _actions_for_target(
        self,
        target: LifecycleTarget,
        *,
        projected_tokens: int = 0,
    ) -> list[LifecycleAction]:
        actions: list[LifecycleAction] = []

        if target.process_alive is False:
            actions.append(self._process_dead_action(target))

        if target.readiness_error:
            actions.append(self._readiness_error_action(target))
        elif (
            target.readiness is not None
            and not target.readiness.ready
            and target.readiness.state != ProviderState.PROCESS_DEAD
        ):
            actions.append(self._readiness_unavailable_action(target))

        usage = target.context_usage
        if usage.ratio >= self.rotate_threshold:
            actions.append(self._context_threshold_action(target))
        elif projected_tokens > 0:
            projected_ratio = self._projected_ratio(usage, projected_tokens)
            if projected_ratio >= self.projected_threshold:
                actions.append(
                    self._projected_ratio_action(
                        target,
                        projected_tokens=projected_tokens,
                        projected_ratio=projected_ratio,
                    )
                )

        return actions

    def _process_dead_action(self, target: LifecycleTarget) -> LifecycleAction:
        return LifecycleAction(
            kind=LifecycleActionKind.RESTART_PROCESS,
            reason=LifecycleReason.PROCESS_NOT_ALIVE,
            agent_name=target.agent_name,
            message=f"{target.agent_name} process is not alive.",
            recommendation=f"Restart {target.agent_name} before sending workflow traffic.",
            blocking=True,
            details=self._usage_details(target.context_usage),
        )

    def _readiness_error_action(self, target: LifecycleTarget) -> LifecycleAction:
        return LifecycleAction(
            kind=LifecycleActionKind.WAIT_FOR_READY,
            reason=LifecycleReason.READINESS_UNAVAILABLE,
            agent_name=target.agent_name,
            message=f"{target.agent_name} readiness could not be checked.",
            recommendation=(
                f"Inspect {target.agent_name} readiness before sending workflow traffic."
            ),
            blocking=True,
            details={"error": target.readiness_error},
        )

    def _readiness_unavailable_action(self, target: LifecycleTarget) -> LifecycleAction:
        assert target.readiness is not None
        readiness = target.readiness
        return LifecycleAction(
            kind=LifecycleActionKind.WAIT_FOR_READY,
            reason=LifecycleReason.READINESS_UNAVAILABLE,
            agent_name=target.agent_name,
            message=f"{target.agent_name} readiness is unavailable: {readiness.reason}",
            recommendation=readiness.action_hint
            or f"Wait until {target.agent_name} is ready for input.",
            blocking=True,
            details={
                "provider": readiness.provider.value,
                "state": readiness.state.value,
                "excerpt": readiness.excerpt,
            },
        )

    def _context_threshold_action(self, target: LifecycleTarget) -> LifecycleAction:
        details = self._usage_details(target.context_usage)
        details["threshold"] = self.rotate_threshold
        return LifecycleAction(
            kind=LifecycleActionKind.ROTATE_SESSION,
            reason=LifecycleReason.CONTEXT_THRESHOLD,
            agent_name=target.agent_name,
            message=(
                f"{target.agent_name} context ratio {target.context_usage.ratio:.1%} "
                f"is at or above the {self.rotate_threshold:.1%} threshold."
            ),
            recommendation=f"Rotate {target.agent_name} before continuing.",
            blocking=True,
            details=details,
        )

    def _projected_ratio_action(
        self,
        target: LifecycleTarget,
        *,
        projected_tokens: int,
        projected_ratio: float,
    ) -> LifecycleAction:
        details = self._usage_details(target.context_usage)
        details.update(
            {
                "projected_tokens": projected_tokens,
                "projected_ratio": projected_ratio,
                "threshold": self.projected_threshold,
            }
        )
        return LifecycleAction(
            kind=LifecycleActionKind.ROTATE_SESSION,
            reason=LifecycleReason.PROJECTED_RATIO,
            agent_name=target.agent_name,
            message=(
                f"{target.agent_name} projected context ratio {projected_ratio:.1%} "
                f"would reach the {self.projected_threshold:.1%} threshold."
            ),
            recommendation=f"Rotate {target.agent_name} before the projected call.",
            blocking=True,
            details=details,
        )

    def _target_from_agent(
        self,
        agent: Any,
        *,
        token_usage: ContextUsage | None = None,
        readiness: ReadinessResult | None = None,
        process_alive: bool | None = None,
    ) -> LifecycleTarget:
        agent_name = self._agent_name(agent)
        provider = self._agent_provider(agent)
        resolved_readiness, readiness_error = self._resolve_readiness(agent, readiness)
        resolved_process_alive = self._resolve_process_alive(
            agent,
            process_alive,
            resolved_readiness,
        )

        return LifecycleTarget(
            agent_name=agent_name,
            provider=provider,
            context_usage=token_usage or self._agent_context_usage(agent),
            process_alive=resolved_process_alive,
            readiness=resolved_readiness,
            readiness_error=readiness_error,
        )

    def _targets_from_agents(
        self,
        agents: Mapping[str, Any] | Iterable[Any],
        *,
        readiness_by_agent: Mapping[str, ReadinessResult] | None = None,
        process_alive_by_agent: Mapping[str, bool] | None = None,
    ) -> list[LifecycleTarget]:
        readiness_by_agent = readiness_by_agent or {}
        process_alive_by_agent = process_alive_by_agent or {}
        targets: list[LifecycleTarget] = []

        for agent in self._iter_agents(agents):
            name = self._agent_name(agent)
            targets.append(
                self._target_from_agent(
                    agent,
                    readiness=readiness_by_agent.get(name),
                    process_alive=process_alive_by_agent.get(name),
                )
            )

        return targets

    def _resolve_readiness(
        self,
        agent: Any,
        readiness: ReadinessResult | None,
    ) -> tuple[ReadinessResult | None, str]:
        if readiness is not None or not self.check_readiness:
            return readiness, ""

        try:
            return self.readiness_gate.check(agent), ""
        except Exception as exc:
            return None, str(exc)

    def _resolve_process_alive(
        self,
        agent: Any,
        process_alive: bool | None,
        readiness: ReadinessResult | None,
    ) -> bool | None:
        if process_alive is not None:
            return process_alive
        if readiness is not None and readiness.state == ProviderState.PROCESS_DEAD:
            return False

        pane = getattr(agent, "pane", None) or getattr(agent, "_pane", None)
        if pane is not None and hasattr(pane, "is_alive"):
            try:
                return bool(pane.is_alive())
            except Exception:
                return False

        alive_attr = getattr(agent, "alive", None)
        if isinstance(alive_attr, bool):
            return alive_attr

        process = getattr(agent, "process", None)
        if process is not None and hasattr(process, "poll"):
            try:
                return process.poll() is None
            except Exception:
                return False

        is_alive = getattr(agent, "is_alive", None)
        if callable(is_alive) and not inspect.iscoroutinefunction(is_alive):
            try:
                result = is_alive()
            except Exception:
                return False
            if not inspect.isawaitable(result):
                return bool(result)

        return None

    def _agent_context_usage(self, agent: Any) -> ContextUsage:
        usage = getattr(agent, "context_usage", None)
        if isinstance(usage, ContextUsage):
            return usage

        spec = getattr(agent, "spec", None)
        effective_budget = getattr(spec, "effective_context_budget", None)
        if isinstance(effective_budget, int) and effective_budget > 0:
            return ContextUsage(total=effective_budget)

        return ContextUsage()

    def _agent_name(self, agent: Any) -> str:
        name = getattr(agent, "name", None)
        if name:
            return str(name)

        spec = getattr(agent, "spec", None)
        spec_name = getattr(spec, "name", None)
        if spec_name:
            return str(spec_name)

        return str(agent)

    def _agent_provider(self, agent: Any) -> Provider | None:
        spec = getattr(agent, "spec", None)
        provider = getattr(spec, "provider", None)
        return provider if isinstance(provider, Provider) else None

    def _iter_agents(self, agents: Mapping[str, Any] | Iterable[Any]) -> Iterable[Any]:
        if isinstance(agents, Mapping):
            return agents.values()
        return agents

    def _agent_by_name(
        self,
        agents: Mapping[str, Any] | Iterable[Any],
        name: str,
    ) -> Any | None:
        if isinstance(agents, Mapping):
            return agents.get(name)

        for agent in agents:
            if self._agent_name(agent) == name:
                return agent
        return None

    def _projected_ratio(self, usage: ContextUsage, projected_tokens: int) -> float:
        if usage.total <= 0:
            return 0.0
        return (usage.used + projected_tokens) / usage.total

    def _usage_details(self, usage: ContextUsage) -> dict[str, Any]:
        return {
            "used": usage.used,
            "total": usage.total,
            "remaining": usage.remaining,
            "ratio": usage.ratio,
        }
