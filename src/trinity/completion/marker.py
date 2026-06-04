"""Marker detector — detects explicit completion markers in pane output."""

from __future__ import annotations

import asyncio
import logging
import time

from trinity.completion.base import CompletionDetector, CompletionResult
from trinity.legacy.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


class MarkerDetector(CompletionDetector):
    """Detects completion when an explicit marker appears in pane output."""

    def __init__(self, marker: str, lines: int = -200):
        self.marker = marker
        self.lines = lines
        self._ignored_marker_count = 0
        self._request_start_line = 0

    @property
    def name(self) -> str:
        return f"MarkerDetector({self.marker})"

    def prepare_for_request(
        self,
        pane: TmuxPane,
        start_line: int = 0,
        sent_text: str = "",
    ) -> None:
        self._request_start_line = max(0, start_line)
        self._ignored_marker_count = sent_text.count(self.marker)

    async def wait_for_completion(
        self,
        pane: TmuxPane,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> CompletionResult:
        start = time.monotonic()

        while True:
            elapsed = time.monotonic() - start
            output = self._capture_scoped_output(pane)

            marker_count = output.count(self.marker)
            if marker_count > self._ignored_marker_count:
                logger.debug("Completion marker detected in pane output")
                return CompletionResult(
                    completed=True,
                    output=output,
                    detector_name=self.name,
                    elapsed_seconds=elapsed,
                    metadata={
                        "marker": self.marker,
                        "marker_count": marker_count,
                        "ignored_marker_count": self._ignored_marker_count,
                        "request_start_line": self._request_start_line,
                    },
                )

            if elapsed >= timeout:
                return CompletionResult(
                    completed=False,
                    output=output,
                    detector_name=self.name,
                    elapsed_seconds=elapsed,
                    metadata={
                        "reason": "timeout",
                        "marker": self.marker,
                        "request_start_line": self._request_start_line,
                    },
                )

            await asyncio.sleep(poll_interval)

    def _capture_scoped_output(self, pane: TmuxPane) -> str:
        """Capture only the current request's pane text when a boundary exists."""
        if self._request_start_line <= 0:
            return "\n".join(pane.capture(lines=self.lines))

        captured = pane.capture(lines=-9999)
        return "\n".join(captured[self._request_start_line:])
