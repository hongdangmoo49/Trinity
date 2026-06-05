"""Shared TUI formatting utilities."""

from __future__ import annotations

import time


def format_timestamp(
    timestamp: float,
    fmt: str = "%Y-%m-%d %H:%M",
) -> str:
    """Format a Unix timestamp for display.

    Args:
        timestamp: Unix timestamp.
        fmt: strftime format string. Defaults to ``"%Y-%m-%d %H:%M"``.
    """
    try:
        return time.strftime(fmt, time.localtime(timestamp))
    except (OSError, ValueError):
        return "unknown"
