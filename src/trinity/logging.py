"""Logging setup — file logging + Rich console formatting."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.logging import RichHandler


def setup_logging(
    log_file: str | Path | None = None,
    level: str = "INFO",
    console_output: bool = True,
) -> logging.Logger:
    """Configure Trinity logging with file and Rich console output.

    Args:
        log_file: Path to log file. None = file logging disabled.
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        console_output: Enable Rich console logging.

    Returns:
        Configured root logger for 'trinity'.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("trinity")
    logger.setLevel(log_level)

    # Remove existing handlers
    logger.handlers.clear()

    # Rich console handler
    if console_output:
        console_handler = RichHandler(
            level=log_level,
            show_path=False,
            show_time=True,
            markup=True,
            rich_tracebacks=True,
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(
            log_path, encoding="utf-8", mode="a",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the 'trinity' namespace."""
    return logging.getLogger(f"trinity.{name}")
