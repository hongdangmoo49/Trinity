"""Claude Code agent wrapper — print mode (Phase 1) and interactive mode (Phase 2)."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole
from trinity.providers.invoker import ClaudePrintInvoker

if TYPE_CHECKING:
    from trinity.completion.base import CompletionDetector, CompletionResult
    from trinity.legacy.tmux.pane import TmuxPane

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
        self._invoker = ClaudePrintInvoker()

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
        self, prompt: str, timeout: float = 120.0, access=None
    ) -> DeliberationMessage:
        """Send prompt via `claude -p` and wait for JSON response."""
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started. Call start() first.")

        self._message_count += 1

        request = self._prompt_request(
            prompt=prompt,
            timeout=timeout,
            context_prompt=self._initial_prompt,
            access=access,
        )
        logger.info(f"[{self.name}] Sending prompt ({len(prompt)} chars)...")

        start_time = time.time()
        result = await self._invoker.invoke(request)
        elapsed = result.elapsed_seconds or (time.time() - start_time)
        logger.info(f"[{self.name}] Response received in {elapsed:.1f}s")

        token_count = 0
        if result.usage is not None:
            token_count = result.usage.used
            self._update_usage(used=token_count, total=self._context_usage.total)

        return DeliberationMessage(
            source=self.name,
            target="all",
            round_num=0,  # Set by protocol
            role=MessageRole.OPINION,
            content=result.content,
            metadata={
                "elapsed_seconds": elapsed,
                "token_count": token_count,
                "model": result.metadata.get("model", "unknown"),
                "response_status": result.status.value,
                "raw_output": result.raw_output,
                "diagnostics": list(result.diagnostics),
                "execution_authority": result.execution_authority.value,
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
        cmd_parts = self._command_parts()
        cmd_parts.extend(self.spec.extra_args)
        cmd = self._shell_command(cmd_parts)

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
        self, prompt: str, timeout: float = 120.0, access=None
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
        pre_lines = self._capture_pane_lines()
        self._last_response_start_line = len(pre_lines)

        # Send the prompt
        full_prompt = self._build_prompt(prompt)
        self._sent_text = full_prompt
        from trinity.completion.base import prepare_detector_for_request

        prepare_detector_for_request(
            detector=self._detector,
            pane=self._pane,
            start_line=self._last_response_start_line,
            sent_text=full_prompt,
        )
        self._pane.send_text_heredoc(full_prompt)

        # Wait for completion
        start_time = time.time()
        result = await self._send_and_wait_for_response(full_prompt, timeout)
        elapsed = time.time() - start_time

        # Prefer detector-scoped output; fall back to pane capture only if needed.
        response_text = self._extract_response_from_pane(result.output)

        # Parse token usage if possible — accumulate across calls
        parsed = self._parse_usage_from_output(result.output)
        if parsed["used"] > 0:
            new_used = self._context_usage.used + parsed["used"]
            self._update_usage(used=new_used, total=parsed.get("total"))
        # If no usage data, preserve existing count (don't reset to 0)

        detector_metadata = (
            result.metadata if isinstance(result.metadata, dict) else {}
        )
        timeout_reason = detector_metadata.get("reason")
        completion_timeout = (
            not result.completed
            or timeout_reason in {"timeout", "hard_timeout"}
        )
        metadata = {
            "elapsed_seconds": elapsed,
            "token_count": parsed.get("used", 0),
            "detector": result.detector_name,
            "completed": result.completed,
            "detector_metadata": detector_metadata,
            "raw_output": result.output,
            "prompt_num": self._prompt_counter,
        }
        if completion_timeout:
            metadata["completion_timeout"] = True
            if timeout_reason:
                metadata["completion_timeout_reason"] = timeout_reason

        return DeliberationMessage(
            source=self.name,
            target="all",
            round_num=0,  # Set by protocol
            role=MessageRole.OPINION,
            content=response_text,
            metadata=metadata,
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
            except Exception as e:
                logger.debug("[%s] Graceful shutdown failed: %s", self.name, e)
        self._started = False
        logger.info(f"[{self.name}] Interactive agent stopped")

    def _build_prompt(self, user_prompt: str) -> str:
        """Build prompt text. For interactive mode, just the user prompt."""
        return user_prompt

    async def _wait_for_ready(self, timeout: float = 30.0) -> None:
        """Wait for Claude CLI to be ready (prompt appears)."""
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

    def _capture_pane_lines(self) -> list[str]:
        """Capture pane output defensively for interactive extraction."""
        if not self._pane:
            return []

        try:
            captured = self._pane.capture(lines=-9999)
        except Exception:
            logger.exception("[%s] Failed to capture pane output", self.name)
            return []

        if isinstance(captured, list):
            return [str(line) for line in captured]
        if isinstance(captured, str):
            return captured.splitlines()
        return []

    def _extract_response_from_pane(self, detector_output: str = "") -> str:
        """Extract response, preferring detector-scoped output over full pane text."""
        if detector_output.strip():
            scoped = self._extract_response(detector_output)
            if scoped:
                return scoped

        all_lines = self._capture_pane_lines()
        if not all_lines:
            return ""
        return self._extract_response_from_lines(all_lines, use_line_boundary=True)

    def _extract_response(self, raw_output: str) -> str:
        """Extract the agent's response from the raw pane output.

        Uses three strategies in priority order:
        1. Last prompt echo anchor based on all sent lines
        2. Fallback: last N lines with aggressive cleaning

        Then strips trailing prompt characters and applies ResponseCleaner.
        """
        return self._extract_response_from_lines(
            raw_output.splitlines(),
            use_line_boundary=False,
        )

    def _extract_response_from_lines(
        self,
        lines: list[str],
        use_line_boundary: bool = False,
    ) -> str:
        """Slice captured lines to the current response and remove CLI echoes."""
        from trinity.agents.response_cleaner import ResponseCleaner

        response_lines = self._slice_response_lines(
            lines,
            use_line_boundary=use_line_boundary,
        )
        response_lines = self._strip_sent_prompt_echo(response_lines)
        response_lines = self._strip_cli_status_lines(response_lines)
        response_lines = self._strip_prompt_lines(response_lines)

        text = "\n".join(response_lines[-50:]).strip()
        if not text:
            return ""

        return ResponseCleaner.clean(text)

    def _slice_response_lines(
        self,
        lines: list[str],
        use_line_boundary: bool = True,
    ) -> list[str]:
        echo_idx = self._find_last_echo_anchor(lines)
        if echo_idx >= 0:
            return lines[echo_idx + 1:]

        total_lines = len(lines)
        if (
            use_line_boundary
            and self._last_response_start_line > 0
            and total_lines > self._last_response_start_line
        ):
            return lines[self._last_response_start_line:]

        return lines[-50:]

    def _strip_sent_prompt_echo(self, lines: list[str]) -> list[str]:
        sent_lines = self._sent_lines()
        if not sent_lines:
            return lines

        search_limit = min(len(lines), max(len(sent_lines) + 20, 50))
        echo_idx = self._find_last_echo_anchor(lines, search_limit=search_limit)
        if echo_idx >= 0:
            return lines[echo_idx + 1:]
        return lines

    def _find_last_echo_anchor(
        self,
        lines: list[str],
        search_limit: int | None = None,
    ) -> int:
        sent_lines = self._sent_lines()
        if not sent_lines:
            return -1

        last_echo_idx = -1
        sent_idx = 0
        limit = len(lines) if search_limit is None else min(len(lines), search_limit)

        for i, line in enumerate(lines[:limit]):
            normalized = self._normalize_echo_line(line)
            if not normalized:
                if last_echo_idx >= 0 and sent_idx < len(sent_lines):
                    last_echo_idx = i
                continue

            for j in range(sent_idx, len(sent_lines)):
                if self._is_echo_match(normalized, sent_lines[j]):
                    last_echo_idx = i
                    sent_idx = j + 1
                    break

            if sent_idx >= len(sent_lines):
                break

        return last_echo_idx

    def _strip_cli_status_lines(self, lines: list[str]) -> list[str]:
        return [line for line in lines if not self._is_cli_status_line(line)]

    def _strip_prompt_lines(self, lines: list[str]) -> list[str]:
        return [line for line in lines if not self._is_prompt_line(line)]

    def _sent_lines(self) -> list[str]:
        return [
            self._normalize_echo_line(line)
            for line in self._sent_text.splitlines()
            if self._normalize_echo_line(line)
        ]

    @staticmethod
    def _normalize_echo_line(line: str) -> str:
        return line.strip().lstrip(">❯$ ").strip()

    @staticmethod
    def _is_echo_match(line: str, sent_line: str) -> bool:
        if not line or not sent_line:
            return False
        return line in sent_line or sent_line in line

    @staticmethod
    def _is_prompt_line(line: str) -> bool:
        return bool(re.match(r"^[>$❯]\s*$", line.strip()))

    @staticmethod
    def _is_cli_status_line(line: str) -> bool:
        stripped = line.strip()
        status_patterns = (
            r"^(?:thinking|processing|working|waiting)(?:[.\s…]|$)",
            r"^(?:thinking|processing|working|waiting)\s+for\s+\d+",
            r"^press\s+esc\s+to\s+(?:cancel|interrupt|stop)",
        )
        return any(
            re.search(pattern, stripped, re.IGNORECASE)
            for pattern in status_patterns
        )

    def _parse_usage_from_output(self, output: str) -> dict:
        """Try to extract token usage from the pane output."""
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
