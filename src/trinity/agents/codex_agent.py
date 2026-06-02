"""Codex (OpenAI) agent wrapper — supports both print and interactive modes."""

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
    from trinity.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


class CodexAgent(AgentWrapper):
    """Codex CLI agent.

    Print mode: spawns `codex -q "<prompt>"` subprocess and parses JSON output.
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
            cmd_parts = [self.spec.cli_command]
            cmd_parts.extend(self.spec.extra_args)
            self._pane.send_text(" ".join(cmd_parts))
            logger.info(f"[{self.name}] Codex launched in tmux pane")

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        if not self._started:
            raise RuntimeError(f"Agent {self.name} not started")

        self._message_count += 1
        full_prompt = self._build_prompt(prompt)

        start_time = time.time()

        if self._pane and self._detector:
            # Interactive mode
            result = await self._detector.wait_for_completion(
                self._pane, timeout=timeout
            )
            elapsed = time.time() - start_time
            response_text = self._extract_response(result.output)
            return DeliberationMessage(
                source=self.name, target="all", round_num=0,
                role=MessageRole.OPINION, content=response_text,
                metadata={"elapsed_seconds": elapsed, "detector": result.detector_name},
            )
        else:
            # Print mode: subprocess
            try:
                raw = await asyncio.to_thread(
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
            response_text, usage = self._parse_response(raw)
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
            except Exception:
                pass
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

    def _run_subprocess(self, prompt: str, timeout: float) -> dict:
        cmd = [self.spec.cli_command, "-q", prompt]
        cmd.extend(self.spec.extra_args)

        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )

        if proc.returncode != 0:
            logger.error(f"[{self.name}] codex exited with code {proc.returncode}")
            return {"result": f"[Error: exit code {proc.returncode}]", "usage": {}}

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"result": proc.stdout, "usage": {}}

    def _parse_response(self, data: dict) -> tuple[str, dict]:
        response_text = data.get("result", str(data))
        usage_data = data.get("usage", {})
        total_used = usage_data.get("total_tokens", 0)
        return response_text, {"used": total_used, "total": self._context_usage.total}

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

    def _extract_response(self, raw_output: str) -> str:
        """Extract response from pane output (interactive mode)."""
        from trinity.agents.response_cleaner import ResponseCleaner

        lines = raw_output.splitlines()
        # Filter out prompt lines
        import re
        prompt_re = re.compile(r"^[$>]\s*$")
        cleaned = [l for l in lines if not prompt_re.match(l.strip())]
        text = "\n".join(cleaned[-50:]).strip() or raw_output.strip()

        # Apply shared response cleaner
        return ResponseCleaner.clean(text) if text else text
