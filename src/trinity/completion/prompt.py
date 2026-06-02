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
        self._start_line: int | None = None

    @property
    def name(self) -> str:
        return "PromptReturnDetector"

    def prepare_for_request(
        self,
        pane: TmuxPane,
        start_line: int = 0,
        sent_text: str = "",
    ) -> None:
        self._start_line = start_line

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

            # Check only the current request region when a boundary is known.
            lines = self._capture_scoped_lines(pane)
            tail = "\n".join(lines[-5:])

            if tail and self._pattern.search(tail):
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
        """Return pane lines relevant to the current request."""
        if self._start_line is None:
            return pane.capture(lines=-5)

        lines = pane.capture(lines=-9999)
        if len(lines) <= self._start_line:
            return []
        return lines[self._start_line:]
