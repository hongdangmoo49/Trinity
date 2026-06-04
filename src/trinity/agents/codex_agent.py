"""Codex (OpenAI) agent wrapper — supports both print and interactive modes."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, MessageRole
from trinity.providers.invoker import CodexExecInvoker

if TYPE_CHECKING:
    from trinity.completion.base import CompletionDetector
    from trinity.legacy.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


class CodexAgent(AgentWrapper):
    """Codex CLI agent.

    Print mode: spawns `codex exec --json` and parses JSONL output.
    Interactive mode (Phase 4): uses tmux pane for persistent session.
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
        self._session_dir: Path | None = None
        self._last_response_start_line = 0
        self._sent_text = ""
        self._invoker = CodexExecInvoker()

    @property
    def session_dir(self) -> Path | None:
        """Codex session directory for tracking state."""
        return self._session_dir

    @session_dir.setter
    def session_dir(self, value: Path) -> None:
        self._session_dir = value

    async def start(self, initial_prompt: str = "") -> None:
        self._started = True
        self._initial_prompt = initial_prompt
        logger.info(f"[{self.name}] Codex agent initialized (print mode)")

        if self._pane and self._detector:
            # Interactive mode: launch codex in tmux pane
            cmd_parts = self._command_parts()
            cmd_parts.extend(self.spec.extra_args)
            self._pane.send_text(self._shell_command(cmd_parts))
            logger.info(f"[{self.name}] Codex launched in tmux pane")

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0, access=None
    ) -> DeliberationMessage:
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started")

        self._message_count += 1

        start_time = time.time()

        if self._pane and self._detector:
            # Interactive mode
            full_prompt = self._build_prompt(prompt)
            pre_lines = self._capture_pane_lines()
            self._last_response_start_line = len(pre_lines)
            self._sent_text = full_prompt
            from trinity.completion.base import prepare_detector_for_request

            prepare_detector_for_request(
                detector=self._detector,
                pane=self._pane,
                start_line=self._last_response_start_line,
                sent_text=full_prompt,
            )
            self._pane.send_text_heredoc(full_prompt)
            result = await self._detector.wait_for_completion(
                self._pane, timeout=timeout
            )
            elapsed = time.time() - start_time
            response_text = self._extract_response_from_pane(result.output)
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
                "raw_output": result.output,
            }
            if completion_timeout:
                metadata["completion_timeout"] = True
                if timeout_reason:
                    metadata["completion_timeout_reason"] = timeout_reason
            return DeliberationMessage(
                source=self.name, target="all", round_num=0,
                role=MessageRole.OPINION, content=response_text, metadata=metadata,
            )
        else:
            # Print mode: one-shot provider invocation.
            request = self._prompt_request(
                prompt=prompt,
                timeout=timeout,
                context_prompt=self._initial_prompt,
                access=access,
            )
            result = await self._invoker.invoke(request)
            elapsed = time.time() - start_time
            if result.elapsed_seconds:
                elapsed = result.elapsed_seconds

            token_count = 0
            if result.usage is not None:
                token_count = result.usage.used
                self._update_usage(
                    used=token_count,
                    total=self._context_usage.total,
                )

            return DeliberationMessage(
                source=self.name, target="all", round_num=0,
                role=MessageRole.OPINION, content=result.content,
                metadata={
                    "elapsed_seconds": elapsed,
                    "token_count": token_count,
                    "response_status": result.status.value,
                    "raw_output": result.raw_output,
                    "diagnostics": list(result.diagnostics),
                    "execution_authority": result.execution_authority.value,
                    "tool_activity_summary": list(result.tool_activity_summary),
                },
            )

    async def get_context_usage(self) -> ContextUsage:
        # Try to read from session file if available
        if self._session_dir:
            usage = self._parse_session_usage()
            if usage:
                return usage
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
        logger.info(f"[{self.name}] Codex agent stopped")

    def _build_prompt(self, user_prompt: str) -> str:
        parts: list[str] = []
        if self.spec.role_prompt:
            parts.append(f"[System Role]\n{self.spec.role_prompt}\n")
        if self._initial_prompt:
            parts.append(f"[Context]\n{self._initial_prompt}\n")
        parts.append(user_prompt)
        return "\n\n".join(parts)

    def _parse_session_usage(self) -> ContextUsage | None:
        """Try to read usage from Codex session JSON files."""
        if not self._session_dir or not self._session_dir.exists():
            return None

        try:
            session_files = sorted(
                self._session_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not session_files:
                return None

            data = json.loads(session_files[0].read_text(encoding="utf-8"))
            usage = data.get("usage", {})
            total = usage.get("total_tokens", 0)
            if total > 0:
                return ContextUsage(used=total, total=self._context_usage.total)
        except (json.JSONDecodeError, OSError):
            pass

        return None

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
        """Extract response from pane output (interactive mode)."""
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
        response_lines = self._strip_prompt_lines(response_lines)

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
