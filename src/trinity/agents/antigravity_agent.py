"""Antigravity CLI agent wrapper for one-shot print mode."""

from __future__ import annotations

import logging
import time

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole
from trinity.providers.invoker import AntigravityPrintInvoker

logger = logging.getLogger(__name__)


class AntigravityPrintAgent(AgentWrapper):
    """Antigravity CLI agent using `agy --print` subprocess calls."""

    def __init__(self, spec: AgentSpec):
        super().__init__(spec)
        self._started = False
        self._message_count = 0
        self._initial_prompt = ""
        self._invoker = AntigravityPrintInvoker()

    async def start(self, initial_prompt: str = "") -> None:
        """Mark agent as started. Print mode has no persistent process."""
        self._started = True
        self._initial_prompt = initial_prompt
        logger.info("[%s] Antigravity print-mode agent initialized", self.name)

    async def send_and_wait(
        self, prompt: str, timeout: float = 300.0, access=None
    ) -> DeliberationMessage:
        """Send prompt via `agy --print` and wait for stdout response."""
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started")

        self._message_count += 1
        start_time = time.time()
        request = self._prompt_request(
            prompt=prompt,
            timeout=timeout,
            context_prompt=self._initial_prompt,
            access=access,
        )
        result = await self._invoker.invoke(request)
        self._remember_provider_session(result.metadata)
        elapsed = result.elapsed_seconds or (time.time() - start_time)

        return DeliberationMessage(
            source=self.name,
            target="all",
            round_num=0,
            role=MessageRole.OPINION,
            content=result.content,
            metadata={
                "elapsed_seconds": elapsed,
                "token_count": 0,
                "response_status": result.status.value,
                "raw_output": result.raw_output,
                "diagnostics": list(result.diagnostics),
                "execution_authority": result.execution_authority.value,
                "output_format": result.metadata.get("output_format", "plain-text"),
                "machine_readable_output": result.metadata.get(
                    "machine_readable_output", False
                ),
                "usage_source": result.metadata.get("usage_source", "unsupported"),
                "conversation_id": result.metadata.get("conversation_id"),
                "model_label": result.metadata.get("model_label"),
                "provider_session": result.metadata.get("provider_session"),
                "runtime_model": result.metadata.get("runtime_model"),
            },
        )

    async def get_context_usage(self) -> ContextUsage:
        return self._context_usage

    async def is_alive(self) -> bool:
        return self._started

    async def graceful_shutdown(self) -> None:
        """No persistent process to stop in print mode."""
        self._started = False
        logger.info("[%s] Antigravity print-mode agent stopped", self.name)
