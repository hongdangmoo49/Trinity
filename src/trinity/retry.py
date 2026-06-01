"""Retry logic — configurable retry with exponential backoff.

Supports retry based on:
- CLI exit codes (e.g., rate-limit 429 → retry)
- Output pattern matching (e.g., "error" in response → retry)
- Exponential backoff with jitter
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Usage:
        config = RetryConfig(max_retries=3, base_delay=1.0)
        result = await config.run_with_retry(fn)
    """

    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_factor: float = 2.0
    jitter: bool = True

    # Retry triggers
    retry_on_exit_codes: list[int] = field(
        default_factory=lambda: [429, 503, 502, -1]
    )
    retry_on_patterns: list[str] = field(
        default_factory=lambda: ["rate limit", "overloaded", "timeout", "connection reset"]
    )

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt (0-indexed).

        Uses exponential backoff: base_delay * backoff_factor^attempt
        With optional jitter: ±25% random variation.
        """
        delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
        if self.jitter:
            delay *= random.uniform(0.75, 1.25)
        return delay

    def should_retry(
        self,
        exit_code: int | None = None,
        output: str | None = None,
        exception: Exception | None = None,
    ) -> bool:
        """Determine if a failed attempt should be retried.

        Args:
            exit_code: Process exit code (None if not applicable).
            output: Process stdout/stderr output.
            exception: Caught exception.

        Returns:
            True if the attempt should be retried.
        """
        # Retry on specific exit codes
        if exit_code is not None and exit_code in self.retry_on_exit_codes:
            logger.debug(f"Retry triggered by exit code: {exit_code}")
            return True

        # Retry on output patterns
        if output:
            output_lower = output.lower()
            for pattern in self.retry_on_patterns:
                if pattern.lower() in output_lower:
                    logger.debug(f"Retry triggered by pattern: '{pattern}'")
                    return True

        # Retry on specific exceptions
        if exception:
            retry_exceptions = (
                ConnectionError,
                TimeoutError,
                asyncio.TimeoutError,
                OSError,
            )
            if isinstance(exception, retry_exceptions):
                logger.debug(f"Retry triggered by exception: {type(exception).__name__}")
                return True

        return False

    async def run_with_retry(
        self,
        fn,
        *args,
        **kwargs,
    ):
        """Run an async function with retry logic.

        Args:
            fn: Async callable to execute.
            *args, **kwargs: Arguments to pass to fn.

        Returns:
            The result of fn on success.

        Raises:
            The last exception if all retries exhausted.
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await fn(*args, **kwargs)
                return result
            except Exception as e:
                last_exception = e

                if attempt >= self.max_retries:
                    logger.error(
                        f"All {self.max_retries} retries exhausted: {e}"
                    )
                    raise

                if not self.should_retry(exception=e):
                    raise

                delay = self.get_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

        # Should not reach here, but just in case
        raise last_exception  # type: ignore

    def run_with_retry_sync(
        self,
        fn,
        *args,
        **kwargs,
    ):
        """Synchronous version of run_with_retry."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                last_exception = e

                if attempt >= self.max_retries:
                    logger.error(
                        f"All {self.max_retries} retries exhausted: {e}"
                    )
                    raise

                if not self.should_retry(exception=e):
                    raise

                delay = self.get_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        raise last_exception  # type: ignore
