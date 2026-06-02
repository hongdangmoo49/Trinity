"""Prompt return detector — detects completion when CLI prompt reappears."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from trinity.completion.base import CompletionDetector, CompletionResult
from trinity.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


class PromptReturnDetector(CompletionDetector):
    """Detects completion by watching for the CLI prompt to reappear.

    When Claude Code finishes responding, it displays a prompt character
    (typically `>` or `$`) at the bottom of the pane. This detector
    watches for that pattern.

    This is the primary detector for Claude Code in interactive mode.
    """

    # Common CLI prompt patterns
    DEFAULT_PATTERNS = [
        r"^\s*>\s*$",       # Claude Code default prompt: >
        r"^\s*\$\s*$",      # Shell-style prompt: $
        r"^\s*›\s*$",       # Codex prompt: ›
        r"^\s*❯\s*$",       # Starship-style prompt: ❯
        r"^\s*╭─+╮\s*$",    # Some CLI custom prompts
    ]

    def __init__(
        self,
        prompt_patterns: list[str] | None = None,
    ):
        """
        Args:
            prompt_patterns: Regex patterns to match against pane output.
                             Checked against the last few lines.
        """
        patterns = prompt_patterns or self.DEFAULT_PATTERNS
        self._pattern = re.compile(
            "|".join(f"({p})" for p in patterns),
            re.MULTILINE,
        )
        self._baseline_text = ""
        self._saw_request_activity = False

    @property
    def name(self) -> str:
        return "PromptReturnDetector"

    def prepare_for_request(
        self,
        pane: TmuxPane,
        start_line: int = 0,
        sent_text: str = "",
    ) -> None:
        self._baseline_text = "\n".join(pane.capture(lines=-200))
        self._saw_request_activity = False

    async def wait_for_completion(
        self,
        pane: TmuxPane,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> CompletionResult:
        start = time.monotonic()

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                output = "\n".join(pane.capture(lines=-200))
                return CompletionResult(
                    completed=False,
                    output=output,
                    detector_name=self.name,
                    elapsed_seconds=elapsed,
                    metadata={"reason": "timeout"},
                )

            lines = self._capture_scoped_lines(pane)
            output = "\n".join(lines)

            if not self._saw_request_activity:
                self._saw_request_activity = bool(
                    output and output != self._baseline_text
                )

            last_line = self._last_meaningful_line(lines)
            if (
                self._saw_request_activity
                and last_line
                and self._pattern.search(last_line)
            ):
                logger.debug(f"Prompt pattern detected in pane output")
                # Capture the full response (before the prompt line)
                full_output = "\n".join(pane.capture(lines=-200))
                return CompletionResult(
                    completed=True,
                    output=full_output,
                    detector_name=self.name,
                    elapsed_seconds=elapsed,
                )

            await asyncio.sleep(poll_interval)

    def _capture_scoped_lines(self, pane: TmuxPane) -> list[str]:
        """Return recent pane lines without assuming append-only scrollback."""
        return pane.capture(lines=-200)

    @staticmethod
    def _last_meaningful_line(lines: list[str]) -> str:
        """Return the last non-empty line in a pane capture."""
        for line in reversed(lines):
            if line.strip():
                return line.strip()
        return ""
