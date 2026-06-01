"""Error handling — Provider crash recovery and agent respawn.

Monitors agents and automatically respawns crashed ones,
preserving session context where possible.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.retry import RetryConfig

logger = logging.getLogger(__name__)


class RecoveryAction(str, Enum):
    """Actions to take when an agent crashes."""

    RESPAWN = "respawn"       # Restart the agent process
    FALLBACK = "fallback"     # Switch to print mode
    DISABLE = "disable"       # Mark agent as disabled
    ABORT = "abort"           # Stop the entire deliberation


@dataclass
class CrashEvent:
    """Record of an agent crash."""

    agent_name: str
    timestamp: float
    reason: str
    exit_code: int | None = None
    output: str = ""
    recovery_action: RecoveryAction = RecoveryAction.RESPAWN


@dataclass
class RecoveryPolicy:
    """Policy for handling agent crashes."""

    max_crashes: int = 3          # Max crashes before disabling agent
    crash_window: float = 300.0   # Seconds to count crashes within
    respawn_delay: float = 2.0    # Seconds to wait before respawn
    fallback_on_tmux_fail: bool = True  # Fall back to print mode if tmux fails


class ErrorHandler:
    """Handles agent crashes with automatic recovery.

    Usage:
        handler = ErrorHandler(agents=my_agents, shared=my_shared)
        await handler.start_monitoring()
        # Crashes are automatically detected and handled
    """

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        shared: SharedContextEngine | None = None,
        policy: RecoveryPolicy | None = None,
        retry_config: RetryConfig | None = None,
    ):
        self.agents = agents
        self.shared = shared
        self.policy = policy or RecoveryPolicy()
        self.retry_config = retry_config or RetryConfig(max_retries=2)
        self._crash_history: dict[str, list[CrashEvent]] = {}
        self._disabled_agents: set[str] = set()
        self._on_crash_callbacks: list[Callable[[CrashEvent], Any]] = []

    def on_crash(self, callback: Callable[[CrashEvent], Any]) -> None:
        """Register a callback to be called when an agent crashes."""
        self._on_crash_callbacks.append(callback)

    def _record_crash(self, event: CrashEvent) -> None:
        """Record a crash event and check if agent should be disabled."""
        if event.agent_name not in self._crash_history:
            self._crash_history[event.agent_name] = []

        self._crash_history[event.agent_name].append(event)

        # Clean old crashes outside the window
        cutoff = time.time() - self.policy.crash_window
        self._crash_history[event.agent_name] = [
            e for e in self._crash_history[event.agent_name]
            if e.timestamp > cutoff
        ]

        # Check if max crashes exceeded
        crash_count = len(self._crash_history[event.agent_name])
        if crash_count >= self.policy.max_crashes:
            logger.warning(
                f"Agent '{event.agent_name}' crashed {crash_count} times "
                f"within {self.policy.crash_window}s — disabling"
            )
            self._disabled_agents.add(event.agent_name)

    def is_disabled(self, agent_name: str) -> bool:
        """Check if an agent has been disabled due to crashes."""
        return agent_name in self._disabled_agents

    def get_active_agents(self) -> dict[str, AgentWrapper]:
        """Return only non-disabled agents."""
        return {
            name: agent
            for name, agent in self.agents.items()
            if name not in self._disabled_agents
        }

    async def handle_crash(
        self,
        agent_name: str,
        reason: str,
        exit_code: int | None = None,
        output: str = "",
    ) -> CrashEvent:
        """Handle an agent crash.

        Records the crash, determines recovery action, and executes it.

        Returns:
            CrashEvent with the recovery action taken.
        """
        event = CrashEvent(
            agent_name=agent_name,
            timestamp=time.time(),
            reason=reason,
            exit_code=exit_code,
            output=output,
        )

        self._record_crash(event)

        # Determine recovery action
        if agent_name in self._disabled_agents:
            event.recovery_action = RecoveryAction.DISABLE
        else:
            event.recovery_action = RecoveryAction.RESPAWN

        logger.info(
            f"Crash handler: '{agent_name}' crashed ({reason}). "
            f"Action: {event.recovery_action.value}"
        )

        # Execute recovery
        if event.recovery_action == RecoveryAction.RESPAWN:
            await self._respawn_agent(agent_name)
        elif event.recovery_action == RecoveryAction.DISABLE:
            logger.warning(f"Agent '{agent_name}' disabled due to repeated crashes")

        # Notify callbacks
        for callback in self._on_crash_callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Crash callback error: {e}")

        return event

    async def _respawn_agent(self, agent_name: str) -> bool:
        """Attempt to respawn a crashed agent.

        Returns:
            True if respawn succeeded.
        """
        agent = self.agents.get(agent_name)
        if not agent:
            return False

        try:
            # Graceful shutdown (in case process is zombie)
            try:
                await agent.graceful_shutdown()
            except Exception:
                pass

            # Wait before respawn
            await asyncio.sleep(self.policy.respawn_delay)

            # Rebuild context for new session
            initial_prompt = ""
            if self.shared:
                context = self.shared.read()
                role = agent.spec.role_prompt or ""
                initial_prompt = role
                if context.strip():
                    initial_prompt = f"{role}\n\nPrevious context:\n{context[:2000]}"

            await agent.start(initial_prompt=initial_prompt)
            logger.info(f"Agent '{agent_name}' respawned successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to respawn '{agent_name}': {e}")
            return False

    async def check_agents(self) -> list[CrashEvent]:
        """Check all agents for crashes and handle them.

        Returns:
            List of crash events that were handled.
        """
        events = []

        for name, agent in list(self.agents.items()):
            if name in self._disabled_agents:
                continue

            try:
                alive = await agent.is_alive()
                if not alive:
                    event = await self.handle_crash(
                        agent_name=name,
                        reason="Agent process not alive",
                    )
                    events.append(event)
            except Exception as e:
                event = await self.handle_crash(
                    agent_name=name,
                    reason=f"Health check failed: {e}",
                )
                events.append(event)

        return events

    def get_crash_history(self, agent_name: str | None = None) -> list[CrashEvent]:
        """Get crash history, optionally filtered by agent."""
        if agent_name:
            return self._crash_history.get(agent_name, [])
        return [
            event
            for events in self._crash_history.values()
            for event in events
        ]

    def reset(self, agent_name: str | None = None) -> None:
        """Reset crash history and re-enable agents."""
        if agent_name:
            self._crash_history.pop(agent_name, None)
            self._disabled_agents.discard(agent_name)
        else:
            self._crash_history.clear()
            self._disabled_agents.clear()
