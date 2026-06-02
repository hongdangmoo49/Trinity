"""Response cleaner — strips CLI splash screens, banners, and boilerplate from agent output.

When agents run in interactive tmux mode, their raw pane output contains:
- CLI splash screens (Claude Code ASCII art, Codex banner, Gemini tips)
- Prompt characters (>, ❯, $)
- Model/version info, migration notices
- Progress indicators, shell mode messages

This module provides a shared cleaning pipeline applied after each agent's
own _extract_response() to remove known CLI boilerplate patterns.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class ResponseCleaner:
    """Strips CLI boilerplate from raw tmux pane output.

    Usage:
        cleaner = ResponseCleaner()
        cleaned = cleaner.clean(raw_pane_output)
    """

    # Lines matching these patterns are removed entirely.
    # Each pattern is compiled once at class level.
    SPLASH_PATTERNS: list[re.Pattern[str]] = [
        # Claude Code splash art (block characters, logo)
        re.compile(r"[▐▝▀▄█▛▜▘▌]{3,}"),
        re.compile(r"Welcome back!"),
        re.compile(r"GLM-\d"),  # Model badge in splash
        re.compile(r"API Usage"),
        re.compile(r"Billing"),
        re.compile(r"with high\s+effort", re.IGNORECASE),
        # Codex banner
        re.compile(r">_\s*OpenAI\s+Codex", re.IGNORECASE),
        re.compile(r"model:\s+gpt", re.IGNORECASE),
        re.compile(r"/model to change", re.IGNORECASE),
        re.compile(r"directory:"),
        re.compile(r"Tip:\s*GPT", re.IGNORECASE),
        re.compile(r"It'?s our strongest agentic", re.IGNORECASE),
        re.compile(r"built to reason through", re.IGNORECASE),
        re.compile(r"check assumptions", re.IGNORECASE),
        re.compile(r"keep going until", re.IGNORECASE),
        # Gemini banner / migration notice
        re.compile(r"Gemini CLI (?:now|will)", re.IGNORECASE),
        re.compile(r"stop serving requests", re.IGNORECASE),
        re.compile(r"Google One", re.IGNORECASE),
        re.compile(r"unpaid tiers", re.IGNORECASE),
        re.compile(r"migrate to\s+Antigravity", re.IGNORECASE),
        re.compile(r"gemini-cli-migra", re.IGNORECASE),
        re.compile(r"CLI now\s+available", re.IGNORECASE),
        re.compile(r"avoid\s+disruption", re.IGNORECASE),
        # Generic CLI tips
        re.compile(r"^Tips? (?:for|on)", re.IGNORECASE),
        re.compile(r"Create \w+\.md files", re.IGNORECASE),
        re.compile(r"/help for more", re.IGNORECASE),
        re.compile(r"Be specific for", re.IGNORECASE),
        re.compile(r"shell mode enabled", re.IGNORECASE),
        re.compile(r"esc to disable", re.IGNORECASE),
        # Claude Code prompt prefix
        re.compile(r"Read the shared context below", re.IGNORECASE),
        re.compile(r"^─+\s*❯", re.IGNORECASE),  # Rich separator with prompt
    ]

    # Patterns for lines that are purely decorative borders/separators
    BORDER_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"^[─═━╭╰╮╯╔╗╚╝║│┃┏┓┗┛┣┫╠╣╬╼╾╴╶╵╷]+\s*$"),
        re.compile(r"^╭[─]+[╮╯╰]\s*$"),
        re.compile(r"^│\s*$"),
    ]

    # Minimum ratio of meaningful text lines to total lines.
    # Below this threshold, the response is considered mostly garbage.
    MIN_MEANINGFUL_RATIO = 0.15

    @classmethod
    def clean(cls, raw: str) -> str:
        """Clean CLI boilerplate from raw pane output.

        Args:
            raw: Raw text captured from tmux pane.

        Returns:
            Cleaned response text with boilerplate removed.
        """
        if not raw or not raw.strip():
            return raw

        lines = raw.splitlines()
        kept: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Skip empty lines (will collapse later)
            if not stripped:
                kept.append("")
                continue

            # Check splash/banner patterns
            if cls._is_splash_line(stripped):
                continue

            # Check border/decoration patterns
            if cls._is_border_line(stripped):
                continue

            kept.append(line)

        # Collapse multiple consecutive blank lines into one
        collapsed = cls._collapse_blanks(kept)

        cleaned = "\n".join(collapsed).strip()

        # Quality check: if too little meaningful content, log warning
        if cleaned:
            meaningful = sum(1 for l in cleaned.splitlines() if l.strip() and len(l.strip()) > 5)
            total = len(cleaned.splitlines())
            if total > 10 and meaningful / total < cls.MIN_MEANINGFUL_RATIO:
                logger.warning(
                    "Response appears mostly boilerplate (%d/%d meaningful lines)",
                    meaningful, total,
                )

        return cleaned

    @classmethod
    def _is_splash_line(cls, line: str) -> bool:
        """Check if a line matches a known CLI splash/banner pattern."""
        for pattern in cls.SPLASH_PATTERNS:
            if pattern.search(line):
                return True
        return False

    @classmethod
    def _is_border_line(cls, line: str) -> bool:
        """Check if a line is purely a decorative border."""
        for pattern in cls.BORDER_PATTERNS:
            if pattern.search(line):
                return True
        return False

    @staticmethod
    def _collapse_blanks(lines: list[str]) -> list[str]:
        """Collapse consecutive blank lines into a single blank line."""
        result: list[str] = []
        prev_blank = False
        for line in lines:
            is_blank = not line.strip()
            if is_blank and prev_blank:
                continue
            result.append(line)
            prev_blank = is_blank
        return result
