"""Agent wrapper — abstract base class for provider-specific agent control."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trinity.models import AgentSpec, ContextUsage, DeliberationMessage


class AgentWrapper(ABC):
    """Abstract base for controlling an AI CLI agent.

    Each provider (Claude, Codex, Gemini) implements this interface.
    Phase 1 uses subprocess-based print mode; Phase 2 adds tmux interactive mode.
    """

    def __init__(self, spec: AgentSpec):
        self.spec = spec
        self._context_usage = ContextUsage(total=spec.effective_context_budget)

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def context_usage(self) -> ContextUsage:
        return self._context_usage

    @abstractmethod
    async def start(self, initial_prompt: str = "") -> None:
        """Launch the agent CLI. Optionally inject an initial prompt."""
        ...

    @abstractmethod
    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        """Send a prompt and wait for the agent to respond.

        Returns a DeliberationMessage with the agent's response.
        """
        ...

    @abstractmethod
    async def get_context_usage(self) -> ContextUsage:
        """Return current token usage for this agent."""
        ...

    @abstractmethod
    async def is_alive(self) -> bool:
        """Check if the agent process is still running."""
        ...

    @abstractmethod
    async def graceful_shutdown(self) -> None:
        """Gracefully stop the agent."""
        ...

    def _update_usage(self, used: int, total: int | None = None) -> None:
        """Update context usage tracking."""
        self._context_usage = ContextUsage(
            used=used,
            total=total if total is not None else self._context_usage.total,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r}, provider={self.spec.provider.value})"
