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
    Interactive mode (Phase 4): uses tmux pane with explicit marker detection.

    Gemini is the most challenging provider:
    - Completion detection relies on an explicit marker plus prompt fallback
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
        self._last_response_start_line = 0
        self._sent_text = ""
        self._completion_marker = COMPLETION_MARKER

    async def start(self, initial_prompt: str = "") -> None:
        self._started = True
        self._initial_prompt = initial_prompt
        logger.info(f"[{self.name}] Gemini agent initialized")

        if self._pane and self._detector:
            cmd_parts = self._command_parts()
            cmd_parts.extend(self.spec.extra_args)
            self._pane.send_text(self._shell_command(cmd_parts))
            logger.info(f"[{self.name}] Gemini launched in tmux pane")

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started")

        self._message_count += 1
        self._completion_marker = f"{COMPLETION_MARKER}#{self._message_count}"
        full_prompt = self._build_prompt(prompt)

        start_time = time.time()

        if self._pane and self._detector:
            # Interactive mode with hard timeout
            effective_timeout = min(timeout, self._hard_timeout)
            pre_lines = self._capture_pane_lines()
            self._last_response_start_line = len(pre_lines)
            self._sent_text = full_prompt
            self._prepare_marker_detector()
            from trinity.completion.base import prepare_detector_for_request

            prepare_detector_for_request(
                detector=self._detector,
                pane=self._pane,
                start_line=self._last_response_start_line,
                sent_text=full_prompt,
            )
            self._pane.send_text_heredoc(full_prompt)

            result = await self._detector.wait_for_completion(
                self._pane, timeout=effective_timeout
            )
            elapsed = time.time() - start_time
            response_text = self._extract_response_from_pane(result.output)

            # Try to parse usage from output
            usage = self._parse_usage_from_output(response_text)
            if usage["used"] > 0:
                self._update_usage(**usage)

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
                "detector": result.detector_name,
                "completed": result.completed,
                "detector_metadata": detector_metadata,
            }
            if completion_timeout:
                metadata["completion_timeout"] = True
                if timeout_reason:
                    metadata["completion_timeout_reason"] = timeout_reason

            return DeliberationMessage(
                source=self.name, target="all", round_num=0,
                role=MessageRole.OPINION, content=response_text,
                metadata=metadata,
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
            except Exception as e:
                logger.debug("[%s] Graceful shutdown failed: %s", self.name, e)
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
        parts.append(
            f"\n\nAfter completing your response, output: {self._completion_marker}"
        )
        return "\n\n".join(parts)

    def _run_subprocess(self, prompt: str, timeout: float) -> str:
        cmd = self._command_parts("-p", prompt)
        cmd.extend(self.spec.extra_args)

        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
            **self._subprocess_kwargs(),
        )

        if proc.returncode != 0:
            logger.error(f"[{self.name}] gemini exited with code {proc.returncode}")
            return f"[Error: exit code {proc.returncode}]"

        output = proc.stdout
        # Strip completion marker if present
        output = self._strip_completion_markers(output)
        return output

    def _prepare_marker_detector(self) -> None:
        """Use a per-request marker so stale Gemini output cannot complete later requests."""
        from trinity.completion.base import FallbackChainDetector
        from trinity.completion.marker import MarkerDetector

        detectors = []
        if isinstance(self._detector, FallbackChainDetector):
            detectors = self._detector.detectors
        elif isinstance(self._detector, MarkerDetector):
            detectors = [self._detector]

        for detector in detectors:
            if isinstance(detector, MarkerDetector):
                detector.marker = self._completion_marker

    def _capture_pane_lines(self) -> list[str]:
        """Capture full pane output defensively for interactive extraction."""
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

    def _extract_response_from_pane(self, fallback_output: str = "") -> str:
        """Extract text, preferring detector-scoped output over full pane text."""
        if fallback_output.strip():
            scoped = self._extract_response(fallback_output)
            if scoped:
                return scoped

        all_lines = self._capture_pane_lines()
        if all_lines:
            return self._extract_response_from_lines(
                all_lines,
                use_line_boundary=True,
            )
        return ""

    def _extract_response(self, raw_output: str) -> str:
        """Extract response from pane output, stripping markers and prompts."""
        return self._extract_response_from_lines(
            raw_output.splitlines(),
            use_line_boundary=False,
        )

    def _extract_response_from_lines(
        self,
        lines: list[str],
        use_line_boundary: bool = True,
    ) -> str:
        """Slice captured lines to the current response and remove CLI echoes."""
        from trinity.agents.response_cleaner import ResponseCleaner

        response_lines = self._slice_response_lines(
            lines,
            use_line_boundary=use_line_boundary,
        )
        response_lines = self._strip_sent_prompt_echo(response_lines)
        response_lines = self._strip_cli_status_lines(response_lines)
        response_lines = self._truncate_at_completion_marker(response_lines)
        response_lines = self._strip_prompt_and_marker_lines(response_lines)

        text = "\n".join(response_lines[-50:]).strip()
        if text:
            cleaned = ResponseCleaner.clean(text)
            if cleaned:
                return cleaned

        return ""

    def _slice_response_lines(
        self,
        lines: list[str],
        use_line_boundary: bool = True,
    ) -> list[str]:
        echo_idx = self._find_last_echo_anchor(lines)
        if echo_idx >= 0:
            return lines[echo_idx + 1:]

        if (
            use_line_boundary
            and self._last_response_start_line > 0
            and len(lines) > self._last_response_start_line
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

    def _truncate_at_completion_marker(self, lines: list[str]) -> list[str]:
        truncated: list[str] = []

        for line in lines:
            match = re.search(r"\[TRINITY_DONE\](?:#\d+)?", line)
            if not match:
                truncated.append(line)
                continue

            before_marker = line[:match.start()].rstrip()
            if before_marker:
                truncated.append(before_marker)
            return truncated

        return truncated

    def _strip_prompt_and_marker_lines(self, lines: list[str]) -> list[str]:
        cleaned: list[str] = []
        for line in lines:
            stripped = line.strip()
            without_marker = self._strip_completion_markers(line)
            if self._is_prompt_line(stripped):
                continue
            if re.fullmatch(r"\[TRINITY_DONE\](?:#\d+)?", stripped):
                continue
            if without_marker.strip() or cleaned:
                cleaned.append(without_marker)
        return cleaned

    def _strip_completion_markers(self, text: str) -> str:
        return re.sub(r"\[TRINITY_DONE\](?:#\d+)?", "", text).strip()

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
        if (
            re.fullmatch(r"\[TRINITY_DONE\](?:#\d+)?", line.strip())
            and line.strip() != sent_line.strip()
        ):
            return False
        return line in sent_line or sent_line in line

    @staticmethod
    def _is_prompt_line(line: str) -> bool:
        return bool(re.match(r"^[>$❯]\s*$", line.strip()))

    def _is_response_body_line(self, line: str) -> bool:
        stripped = self._strip_completion_markers(line).strip()
        return bool(
            stripped
            and not self._is_prompt_line(stripped)
            and not self._is_cli_status_line(stripped)
        )

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
