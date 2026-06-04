"""Hook detector — detects completion via Claude's stop-hook file signal."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from trinity.completion.base import CompletionDetector, CompletionResult
from trinity.legacy.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


class HookDetector(CompletionDetector):
    """Detects completion by watching for a signal file written by
    Claude Code's stop-hook.

    Setup: In ~/.claude/settings.json, add a Stop hook that writes
    a completion signal file when Claude finishes:

        {
          "hooks": {
            "Stop": [{
              "matcher": "",
              "hooks": [{
                "type": "command",
                "command": "echo '{\"completed\":true,\"timestamp\":\"$(date -Is)\"}' > $TRINITY_HOOK_SIGNAL"
              }]
            }]
          }
        }

    The signal file is watched for creation/modification.
    This is the most reliable detector for Claude Code.
    """

    def __init__(self, signal_path: Path):
        """
        Args:
            signal_path: Path to the signal file that the hook writes.
        """
        self.signal_path = signal_path
        self._last_mtime: float = 0.0

    @property
    def name(self) -> str:
        return f"HookDetector({self.signal_path.name})"

    def reset(self) -> None:
        """Reset the detector state. Call before sending a new prompt."""
        self._last_mtime = 0.0
        # Clean up old signal file
        if self.signal_path.exists():
            try:
                self.signal_path.unlink()
            except OSError:
                pass

    async def wait_for_completion(
        self,
        pane: TmuxPane,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> CompletionResult:
        start = time.monotonic()

        # Record current mtime as baseline
        if self.signal_path.exists():
            self._last_mtime = self.signal_path.stat().st_mtime

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

            # Check if signal file has been updated
            if self.signal_path.exists():
                try:
                    current_mtime = self.signal_path.stat().st_mtime
                    if current_mtime > self._last_mtime:
                        # New signal detected
                        content = self.signal_path.read_text(encoding="utf-8").strip()
                        logger.debug(f"Hook signal received: {content[:100]}")

                        output = "\n".join(pane.capture(lines=-200))

                        # Try to parse usage data from signal
                        metadata = {}
                        try:
                            signal_data = json.loads(content)
                            metadata["signal"] = signal_data
                        except (json.JSONDecodeError, ValueError):
                            metadata["signal_raw"] = content

                        return CompletionResult(
                            completed=True,
                            output=output,
                            detector_name=self.name,
                            elapsed_seconds=elapsed,
                            metadata=metadata,
                        )
                except OSError:
                    pass  # File might have been deleted between checks

            await asyncio.sleep(poll_interval)
