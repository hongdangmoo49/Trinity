"""Marker detector — detects explicit completion markers in pane output."""

from __future__ import annotations

import asyncio
import logging
import time

from trinity.completion.base import CompletionDetector, CompletionResult
from trinity.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


class MarkerDetector(CompletionDetector):
    """Detects completion when an explicit marker appears in pane output."""

    def __init__(self, marker: str, lines: int = -200):
        self.marker = marker
        self.lines = lines

    @property
    def name(self) -> str:
        return f"MarkerDetector({self.marker})"

    async def wait_for_completion(
        self,
        pane: TmuxPane,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> CompletionResult:
        start = time.monotonic()

        while True:
            elapsed = time.monotonic() - start
            output = "\n".join(pane.capture(lines=self.lines))

            if self.marker in output:
                logger.debug("Completion marker detected in pane output")
                return CompletionResult(
                    completed=True,
                    output=output,
                    detector_name=self.name,
                    elapsed_seconds=elapsed,
                    metadata={"marker": self.marker},
                )

            if elapsed >= timeout:
                return CompletionResult(
                    completed=False,
                    output=output,
                    detector_name=self.name,
                    elapsed_seconds=elapsed,
                    metadata={"reason": "timeout", "marker": self.marker},
                )

            await asyncio.sleep(poll_interval)
