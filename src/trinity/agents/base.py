"""Agent wrapper — abstract base class for provider-specific agent control."""

from __future__ import annotations

import os
import shlex
from abc import ABC, abstractmethod
from pathlib import Path

from trinity.models import AgentSpec, ContextUsage, DeliberationMessage


class AgentWrapper(ABC):
    """Abstract base for controlling an AI CLI agent.

    Each provider (Claude, Codex, Gemini) implements this interface.
    Phase 1 uses subprocess-based print mode; Phase 2 adds tmux interactive mode.
    """

    def __init__(self, spec: AgentSpec):
        self.spec = spec
        self._context_usage = ContextUsage(total=spec.effective_context_budget)
        self.launch_cwd: Path | None = None
        self.env_overrides: dict[str, str] = {}

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

    def configure_launch(
        self,
        cwd: Path | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        """Apply prepared cwd/env metadata to future provider launches."""
        self.launch_cwd = cwd
        self.env_overrides = dict(env_overrides or {})

    def _subprocess_kwargs(self) -> dict:
        """Return cwd/env kwargs for subprocess.run."""
        kwargs = {}
        if self.launch_cwd is not None:
            kwargs["cwd"] = self.launch_cwd
        if self.env_overrides:
            env = os.environ.copy()
            env.update(self.env_overrides)
            kwargs["env"] = env
        return kwargs

    def _model_args(self) -> list[str]:
        """Return CLI args that pin the configured model for this agent."""
        model = (self.spec.model or "").strip()
        if not model or model == "default":
            return []
        return ["--model", model]

    def _command_parts(self, *parts: str) -> list[str]:
        """Build provider command parts with model selection applied."""
        return [self.spec.cli_command, *self._model_args(), *parts]

    def _shell_command(self, args: list[str]) -> str:
        """Build a shell command with per-agent environment overrides."""
        command = " ".join(shlex.quote(str(arg)) for arg in args)
        if not self.env_overrides:
            return command

        env_parts = [
            f"{key}={shlex.quote(str(value))}"
            for key, value in sorted(self.env_overrides.items())
        ]
        return " ".join(["env", *env_parts, command])

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r}, provider={self.spec.provider.value})"
