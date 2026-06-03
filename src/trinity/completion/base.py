"""Completion detection — abstract base and fallback chain."""

from __future__ import annotations

import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from trinity.tmux.pane import TmuxPane

logger = logging.getLogger(__name__)


def prepare_detector_for_request(
    detector: "CompletionDetector | None",
    pane: TmuxPane,
    start_line: int = 0,
    sent_text: str = "",
) -> None:
    """Prepare a detector when it supports request-scoped state."""
    if detector is None:
        return

    prepare = getattr(detector, "prepare_for_request", None)
    if not callable(prepare):
        return

    result = prepare(pane=pane, start_line=start_line, sent_text=sent_text)
    if inspect.isawaitable(result):
        close = getattr(result, "close", None)
        if callable(close):
            close()


@dataclass
class CompletionResult:
    """Result of a completion detection attempt."""

    completed: bool
    output: str = ""
    detector_name: str = ""
    elapsed_seconds: float = 0.0
    metadata: dict = field(default_factory=dict)


class CompletionDetector(ABC):
    """Abstract base for detecting when an agent has finished responding.

    Each detector implements a specific strategy:
    - HookDetector: watches for a file signal from Claude's stop-hook
    - PromptReturnDetector: watches for the CLI prompt to reappear
    - IdleDetector: watches for output to stop changing; useful for stall
      diagnostics, but not a reliable completion signal for provider chains.
    """

    def prepare_for_request(
        self,
        pane: TmuxPane,
        start_line: int = 0,
        sent_text: str = "",
    ) -> None:
        """Prepare detector state for a single prompt/response cycle.

        Most detectors are stateless. Detectors that inspect pane text can use
        the boundary to ignore stale prompts and echoed prompt text from the
        current request.
        """
        return None

    @abstractmethod
    async def wait_for_completion(
        self,
        pane: TmuxPane,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> CompletionResult:
        """Wait until the agent in the given pane has finished responding.

        Args:
            pane: The tmux pane to monitor.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between each poll.

        Returns:
            CompletionResult with completed=True if detected in time.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable detector name."""
        ...


class FallbackChainDetector(CompletionDetector):
    """Runs multiple detectors in priority order, returns first success.

    Phase 10 provider chains avoid idle-as-completion and prefer explicit
    provider signals such as hooks, markers, or prompt return.

    If all detectors fail, the result has completed=False (timeout).
    """

    def __init__(self, detectors: list[CompletionDetector]):
        self.detectors = detectors

    @property
    def name(self) -> str:
        return "FallbackChain(" + ", ".join(d.name for d in self.detectors) + ")"

    async def wait_for_completion(
        self,
        pane: TmuxPane,
        timeout: float = 120.0,
        poll_interval: float = 0.5,
    ) -> CompletionResult:
        """Run all detectors concurrently, return first positive result."""
        import time

        start = time.monotonic()

        # Run all detectors as concurrent tasks
        tasks = [
            asyncio.create_task(
                d.wait_for_completion(pane, timeout, poll_interval)
            )
            for d in self.detectors
        ]

        try:
            # Wait for any to complete with a positive result
            done, pending = await asyncio.wait(
                tasks,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Check completed tasks for a positive result
            for task in done:
                result = task.result()
                if result.completed:
                    # Cancel remaining tasks
                    for t in pending:
                        t.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    result.elapsed_seconds = time.monotonic() - start
                    logger.info(
                        f"Completion detected by {result.detector_name} "
                        f"in {result.elapsed_seconds:.1f}s"
                    )
                    return result

            # No positive result from completed tasks — check pending
            # If we timed out, cancel all and return failure
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            # Collect output from the pane as final fallback
            output = "\n".join(pane.capture(lines=-200))
            elapsed = time.monotonic() - start

            return CompletionResult(
                completed=False,
                output=output,
                detector_name=self.name,
                elapsed_seconds=elapsed,
                metadata={"reason": "timeout"},
            )

        except asyncio.CancelledError:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    def prepare_for_request(
        self,
        pane: TmuxPane,
        start_line: int = 0,
        sent_text: str = "",
    ) -> None:
        """Apply request boundaries to every detector in the chain."""
        for detector in self.detectors:
            detector.prepare_for_request(
                pane=pane,
                start_line=start_line,
                sent_text=sent_text,
            )
