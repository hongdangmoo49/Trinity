"""Claude Code agent wrapper — print mode (Phase 1) and interactive mode (Phase 2)."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole

if TYPE_CHECKING:
    from trinity.completion.base import CompletionDetector
    from trinity.completion.hook import HookDetector
    from trinity.tmux.pane import TmuxPane

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
            encoding="utf-8",
            errors="replace",
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
    """Claude Code agent in interactive tmux mode.

    Launches `claude` in a tmux pane, sends prompts via send-keys,
    detects completion via fallback chain (Hook→PromptReturn→Idle),
    and reads responses via capture-pane.
    """

    def __init__(
        self,
        spec: AgentSpec,
        pane: "TmuxPane | None" = None,
        detector: "CompletionDetector | None" = None,
        signal_path: "Path | None" = None,
    ):
        super().__init__(spec)
        self._pane = pane
        self._detector = detector
        self._signal_path = signal_path
        self._started = False
        self._prompt_counter = 0
        self._last_response_start_line = 0

        # Response parsing
        self._sent_text = ""  # Track what we sent to strip from response

    @property
    def pane(self) -> "TmuxPane | None":
        return self._pane

    @pane.setter
    def pane(self, value: "TmuxPane") -> None:
        self._pane = value

    @property
    def detector(self) -> "CompletionDetector | None":
        return self._detector

    @detector.setter
    def detector(self, value: "CompletionDetector") -> None:
        self._detector = value

    async def start(self, initial_prompt: str = "") -> None:
        """Launch claude CLI in the tmux pane and inject role prompt."""
        if not self._pane:
            raise RuntimeError(f"No tmux pane assigned for agent '{self.name}'")
        if not self._detector:
            raise RuntimeError(f"No completion detector for agent '{self.name}'")

        # Record current pane line count as baseline
        self._last_response_start_line = len(self._pane.capture(lines=-9999))

        # Launch claude CLI
        cmd_parts = [self.spec.cli_command]
        cmd_parts.extend(self.spec.extra_args)
        cmd = " ".join(cmd_parts)

        logger.info(f"[{self.name}] Launching in tmux pane: {cmd}")
        self._pane.send_text(cmd)

        # Wait for claude to be ready (prompt appears)
        await self._wait_for_ready(timeout=30.0)

        # Inject role prompt if provided
        if initial_prompt:
            logger.info(f"[{self.name}] Injecting role prompt")
            await self._send_and_wait_for_response(initial_prompt, timeout=60.0)

        self._started = True
        logger.info(f"[{self.name}] Interactive agent ready")

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        """Send prompt via send-keys and wait for completion."""
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started")

        self._prompt_counter += 1
        logger.info(f"[{self.name}] Sending prompt #{self._prompt_counter}")

        # Reset hook detector if present
        from trinity.completion.base import FallbackChainDetector
        from trinity.completion.hook import HookDetector

        if isinstance(self._detector, FallbackChainDetector):
            for d in self._detector.detectors:
                if isinstance(d, HookDetector):
                    d.reset()
        elif isinstance(self._detector, HookDetector):
            self._detector.reset()

        # Record start position in pane output
        pre_lines = self._pane.capture(lines=-9999)
        self._last_response_start_line = len(pre_lines)

        # Send the prompt
        full_prompt = self._build_prompt(prompt)
        self._sent_text = full_prompt
        self._pane.send_text_heredoc(full_prompt)

        # Wait for completion
        start_time = time.time()
        result = await self._send_and_wait_for_response(full_prompt, timeout)
        elapsed = time.time() - start_time

        # Extract response text (strip what we sent)
        response_text = self._extract_response(result.output)

        # Parse token usage if possible
        usage = self._parse_usage_from_output(result.output)
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
                "detector": result.detector_name,
                "prompt_num": self._prompt_counter,
            },
        )

    async def get_context_usage(self) -> ContextUsage:
        return self._context_usage

    async def is_alive(self) -> bool:
        if not self._pane:
            return False
        return self._started and self._pane.is_alive()

    async def graceful_shutdown(self) -> None:
        """Send /exit to claude, then kill the pane."""
        if self._pane and self._started:
            try:
                self._pane.send_text("/exit")
                await asyncio.sleep(1.0)
            except Exception:
                pass
        self._started = False
        logger.info(f"[{self.name}] Interactive agent stopped")

    def _build_prompt(self, user_prompt: str) -> str:
        """Build prompt text. For interactive mode, just the user prompt."""
        return user_prompt

    async def _wait_for_ready(self, timeout: float = 30.0) -> None:
        """Wait for Claude CLI to be ready (prompt appears)."""
        import re

        prompt_pattern = re.compile(r"[>❯$]\s*$", re.MULTILINE)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            lines = self._pane.capture(lines=-5)
            tail = "\n".join(lines)
            if prompt_pattern.search(tail):
                logger.debug(f"[{self.name}] Claude CLI ready")
                return
            await asyncio.sleep(0.5)

        logger.warning(f"[{self.name}] Timed out waiting for CLI ready")

    async def _send_and_wait_for_response(
        self, prompt: str, timeout: float = 120.0
    ) -> "CompletionResult":
        """Send a prompt and wait for the completion detector to signal done."""
        from trinity.completion.base import CompletionResult

        if not self._detector or not self._pane:
            # Fallback: just wait a fixed time
            await asyncio.sleep(min(timeout, 10.0))
            output = "\n".join(self._pane.capture(lines=-200))
            return CompletionResult(
                completed=True,
                output=output,
                detector_name="fallback",
            )

        result = await self._detector.wait_for_completion(
            self._pane, timeout=timeout
        )
        return result

    def _extract_response(self, raw_output: str) -> str:
        """Extract the agent's response from the raw pane output.

        Strips the sent prompt and any prompt characters from the output.
        """
        # Get lines after what we sent
        lines = raw_output.splitlines()

        # Try to find where our prompt was
        response_lines = []
        found_prompt = False

        for line in lines:
            # Skip lines that are part of what we sent
            if not found_prompt:
                # Look for the last occurrence of our sent text
                if self._sent_text and self._sent_text[:50] in line:
                    found_prompt = True
                continue
            response_lines.append(line)

        if not response_lines:
            # Fallback: return last ~100 lines (skip prompt characters)
            response_lines = lines[-100:]

        # Clean up: remove trailing prompt characters
        cleaned = []
        import re

        prompt_re = re.compile(r"^[>❯$]\s*$")
        for line in reversed(response_lines):
            if prompt_re.match(line.strip()):
                continue
            cleaned.append(line)

        cleaned.reverse()

        text = "\n".join(cleaned).strip()
        return text if text else raw_output.strip()

    def _parse_usage_from_output(self, output: str) -> dict:
        """Try to extract token usage from the pane output."""
        import re

        # Look for patterns like "Tokens: 1234/200000" or "usage: 1234"
        patterns = [
            r"[Tt]okens?:\s*(\d+)[/\s]+(\d+)",
            r"[Uu]sage:\s*(\d+)",
            r"input_tokens[\":\s]+(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                groups = match.groups()
                used = int(groups[0])
                total = int(groups[1]) if len(groups) > 1 else self._context_usage.total
                return {"used": used, "total": total}

        return {"used": 0, "total": self._context_usage.total}
