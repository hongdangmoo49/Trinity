"""Idle detector — detects completion when pane output stops changing."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time

from trinity.completion.base import CompletionDetector, CompletionResult
from trinity.legacy.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


class IdleDetector(CompletionDetector):
    """Detects completion by watching for output to stop changing.

    Polls capture-pane at regular intervals. If the output hash
    hasn't changed for `idle_timeout` seconds, considers the agent done.

    This is the least reliable detector (generic fallback)
    and should be used last in the fallback chain.
    """

    def __init__(self, idle_timeout: float = 10.0):
        """
        Args:
            idle_timeout: Seconds of unchanged output before declaring complete.
        """
        self.idle_timeout = idle_timeout

    @property
    def name(self) -> str:
        return f"IdleDetector({self.idle_timeout}s)"

    async def wait_for_completion(
        self,
        pane: TmuxPane,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> CompletionResult:
        start = time.monotonic()
        last_hash = ""
        last_change_time = start

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                output = "\n".join(pane.capture(lines=-200))
                return CompletionResult(
                    completed=False,
                    output=output,
                    detector_name=self.name,
                    elapsed_seconds=elapsed,
                    metadata={"reason": "hard_timeout"},
                )

            # Capture current output
            lines = pane.capture(lines=-200)
            current_output = "\n".join(lines)
            current_hash = hashlib.md5(current_output.encode()).hexdigest()

            if current_hash != last_hash:
                last_hash = current_hash
                last_change_time = time.monotonic()
            else:
                idle_duration = time.monotonic() - last_change_time
                if idle_duration >= self.idle_timeout:
                    logger.debug(
                        f"Idle detected: no output change for "
                        f"{idle_duration:.1f}s"
                    )
                    return CompletionResult(
                        completed=True,
                        output=current_output,
                        detector_name=self.name,
                        elapsed_seconds=elapsed,
                        metadata={"idle_seconds": idle_duration},
                    )

            await asyncio.sleep(poll_interval)
