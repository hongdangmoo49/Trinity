"""Claude Code agent wrapper — print mode (Phase 1) and interactive mode (Phase 2)."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole

logger = logging.getLogger(__name__)


class PrintModeClaudeAgent(AgentWrapper):
    """Claude Code agent using `claude -p --output-format json` subprocess.

    Phase 1 implementation: each send_and_wait() spawns a new claude -p call.
    No tmux needed. Completion detection is trivial (subprocess blocks).
    Token counts come from the JSON response's `usage` field.
    """

    def __init__(self, spec: AgentSpec):
        super().__init__(spec)
        self._started = False
        self._message_count = 0

    async def start(self, initial_prompt: str = "") -> None:
        """Mark agent as started. In print mode, there's no persistent process."""
        self._started = True
        logger.info(f"[{self.name}] Print-mode agent initialized")

        if initial_prompt:
            # In print mode, we don't pre-inject — just store for context
            logger.debug(f"[{self.name}] Initial prompt stored (will be prepended on first call)")
            self._initial_prompt = initial_prompt
        else:
            self._initial_prompt = ""

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        """Send prompt via `claude -p` and wait for JSON response."""
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started. Call start() first.")

        self._message_count += 1

        # Build full prompt with role + initial context
        full_prompt = self._build_prompt(prompt)

        # Build CLI command
        cmd = [
            self.spec.cli_command,
            "-p",
            "--output-format", "json",
        ]
        cmd.extend(self.spec.extra_args)
        cmd.append(full_prompt)

        logger.info(f"[{self.name}] Sending prompt ({len(full_prompt)} chars)...")

        start_time = time.time()
        try:
            result = await asyncio.to_thread(
                self._run_subprocess, cmd, timeout
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"[{self.name}] Timeout after {timeout}s")
            return DeliberationMessage(
                source=self.name,
                target="all",
                round_num=0,
                role=MessageRole.OPINION,
                content=f"[Timeout after {timeout}s]",
                metadata={"error": "timeout"},
            )

        elapsed = time.time() - start_time
        logger.info(f"[{self.name}] Response received in {elapsed:.1f}s")

        # Parse JSON response
        response_text, usage = self._parse_response(result)
        self._update_usage(**usage)

        return DeliberationMessage(
            source=self.name,
            target="all",
            round_num=0,  # Set by protocol
            role=MessageRole.OPINION,
            content=response_text,
            metadata={
                "elapsed_seconds": elapsed,
                "token_count": usage.get("used", 0),
                "model": result.get("model", "unknown"),
            },
        )

    async def get_context_usage(self) -> ContextUsage:
        return self._context_usage

    async def is_alive(self) -> bool:
        return self._started

    async def graceful_shutdown(self) -> None:
        """No persistent process to shut down in print mode."""
        self._started = False
        logger.info(f"[{self.name}] Print-mode agent stopped")

    def _build_prompt(self, user_prompt: str) -> str:
        """Build the full prompt with role description."""
        parts: list[str] = []

        if self.spec.role_prompt:
            parts.append(f"[System Role]\n{self.spec.role_prompt}\n")

        if self._initial_prompt:
            parts.append(f"[Context]\n{self._initial_prompt}\n")

        parts.append(user_prompt)

        return "\n\n".join(parts)

    def _run_subprocess(self, cmd: list[str], timeout: float) -> dict:
        """Run claude -p in a subprocess (blocking). Returns parsed JSON."""
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if proc.returncode != 0:
            logger.error(f"[{self.name}] claude exited with code {proc.returncode}")
            logger.error(f"[{self.name}] stderr: {proc.stderr[:500]}")
            return {
                "result": f"[Error: claude exited with code {proc.returncode}]",
                "usage": {},
            }

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            # If not JSON, treat stdout as plain text response
            return {
                "result": proc.stdout,
                "usage": {},
            }

    def _parse_response(self, data: dict) -> tuple[str, dict]:
        """Extract response text and usage from Claude JSON output.

        Returns (response_text, {"used": N, "total": N}).
        """
        response_text = data.get("result", str(data))

        usage_data = data.get("usage", {})
        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)
        total_used = input_tokens + output_tokens

        # Estimate total from budget
        total = self._context_usage.total

        return response_text, {"used": total_used, "total": total}


class InteractiveClaudeAgent(AgentWrapper):
    """Claude Code agent in interactive tmux mode (Phase 2 — stub).

    Will launch `claude` in a tmux pane, send prompts via send-keys,
    and detect completion via prompt pattern or hooks.
    """

    def __init__(self, spec: AgentSpec):
        super().__init__(spec)
        raise NotImplementedError("InteractiveClaudeAgent is a Phase 2 feature")
