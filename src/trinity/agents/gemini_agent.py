"""Gemini CLI agent wrapper — supports both print and interactive modes."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import time
from typing import TYPE_CHECKING

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole

if TYPE_CHECKING:
    from trinity.completion.base import CompletionDetector
    from trinity.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)

# Marker injected into prompts to help detect completion
COMPLETION_MARKER = "[TRINITY_DONE]"


class GeminiAgent(AgentWrapper):
    """Gemini CLI agent.

    Print mode: spawns `gemini -p "<prompt>"` subprocess.
    Interactive mode (Phase 4): uses tmux pane with idle detection.

    Gemini is the most challenging provider:
    - Completion detection relies on idle timeout (unreliable)
    - Token count extraction is regex-based (fragile)
    - Requires a hard timeout as ultimate fallback
    """

    def __init__(
        self,
        spec: AgentSpec,
        pane: "TmuxPane | None" = None,
        detector: "CompletionDetector | None" = None,
    ):
        super().__init__(spec)
        self._pane = pane
        self._detector = detector
        self._started = False
        self._message_count = 0
        self._initial_prompt = ""
        self._hard_timeout = 120.0  # seconds

    async def start(self, initial_prompt: str = "") -> None:
        self._started = True
        self._initial_prompt = initial_prompt
        logger.info(f"[{self.name}] Gemini agent initialized")

        if self._pane and self._detector:
            cmd_parts = [self.spec.cli_command]
            cmd_parts.extend(self.spec.extra_args)
            self._pane.send_text(" ".join(cmd_parts))
            logger.info(f"[{self.name}] Gemini launched in tmux pane")

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started")

        self._message_count += 1
        full_prompt = self._build_prompt(prompt)

        start_time = time.time()

        if self._pane and self._detector:
            # Interactive mode with hard timeout
            effective_timeout = min(timeout, self._hard_timeout)
            self._pane.send_text_heredoc(full_prompt)

            result = await self._detector.wait_for_completion(
                self._pane, timeout=effective_timeout
            )
            elapsed = time.time() - start_time
            response_text = self._extract_response(result.output)

            # Try to parse usage from output
            usage = self._parse_usage_from_output(response_text)
            if usage["used"] > 0:
                self._update_usage(**usage)

            return DeliberationMessage(
                source=self.name, target="all", round_num=0,
                role=MessageRole.OPINION, content=response_text,
                metadata={
                    "elapsed_seconds": elapsed,
                    "detector": result.detector_name,
                    "completed": result.completed,
                },
            )
        else:
            # Print mode: subprocess
            try:
                output = await asyncio.to_thread(
                    self._run_subprocess, full_prompt, timeout
                )
            except subprocess.TimeoutExpired:
                return DeliberationMessage(
                    source=self.name, target="all", round_num=0,
                    role=MessageRole.OPINION,
                    content=f"[Timeout after {timeout}s]",
                    metadata={"error": "timeout"},
                )

            elapsed = time.time() - start_time
            response_text = output.strip()

            # Parse usage
            usage = self._parse_usage_from_output(response_text)
            if usage["used"] > 0:
                self._update_usage(**usage)

            return DeliberationMessage(
                source=self.name, target="all", round_num=0,
                role=MessageRole.OPINION, content=response_text,
                metadata={
                    "elapsed_seconds": elapsed,
                    "token_count": usage.get("used", 0),
                },
            )

    async def get_context_usage(self) -> ContextUsage:
        return self._context_usage

    async def is_alive(self) -> bool:
        if self._pane:
            return self._started and self._pane.is_alive()
        return self._started

    async def graceful_shutdown(self) -> None:
        if self._pane and self._started:
            try:
                self._pane.send_signal("C-c")
                await asyncio.sleep(0.5)
            except Exception:
                pass
        self._started = False
        logger.info(f"[{self.name}] Gemini agent stopped")

    def _build_prompt(self, user_prompt: str) -> str:
        parts: list[str] = []
        if self.spec.role_prompt:
            parts.append(f"[System Role]\n{self.spec.role_prompt}\n")
        if self._initial_prompt:
            parts.append(f"[Context]\n{self._initial_prompt}\n")
        # Add completion marker for detection
        parts.append(user_prompt)
        parts.append(f"\n\nAfter completing your response, output: {COMPLETION_MARKER}")
        return "\n\n".join(parts)

    def _run_subprocess(self, prompt: str, timeout: float) -> str:
        cmd = [self.spec.cli_command, "-p", prompt]
        cmd.extend(self.spec.extra_args)

        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )

        if proc.returncode != 0:
            logger.error(f"[{self.name}] gemini exited with code {proc.returncode}")
            return f"[Error: exit code {proc.returncode}]"

        output = proc.stdout
        # Strip completion marker if present
        output = output.replace(COMPLETION_MARKER, "").strip()
        return output

    def _extract_response(self, raw_output: str) -> str:
        """Extract response from pane output, stripping markers and prompts."""
        from trinity.agents.response_cleaner import ResponseCleaner

        text = raw_output.replace(COMPLETION_MARKER, "")
        lines = text.splitlines()

        # Filter out empty trailing lines and prompt characters
        prompt_re = re.compile(r"^[$>❯]\s*$")
        cleaned = [l for l in lines if not prompt_re.match(l.strip())]
        text = "\n".join(cleaned[-50:]).strip() or raw_output.strip()

        # Apply shared response cleaner
        return ResponseCleaner.clean(text) if text else text

    def _parse_usage_from_output(self, output: str) -> dict:
        """Try to extract token usage from Gemini output."""
        patterns = [
            r"[Tt]oken\s*(?:count)?\s*:\s*(\d+)",
            r"[Uu]sage:\s*(\d+)",
            r"input_tokens[\":\s]+(\d+).*?output_tokens[\":\s]+(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    used = int(groups[0]) + int(groups[1])
                else:
                    used = int(groups[0])
                if used > 0:
                    return {"used": used, "total": self._context_usage.total}

        return {"used": 0, "total": self._context_usage.total}
