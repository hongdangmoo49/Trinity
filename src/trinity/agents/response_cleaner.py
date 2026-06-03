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

from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResponseValidationResult:
    """Classification result for an agent response candidate."""

    usable: bool
    classification: str
    cleaned_text: str
    reasons: tuple[str, ...] = ()
    raw_excerpt: str = ""


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
    MIN_SUBSTANTIVE_TAIL_CHARS = 8

    COMPLETION_MARKER_PATTERN = re.compile(r"\[TRINITY_DONE\](?:#\d+)?")
    REQUEST_BOUNDARY_PATTERN = re.compile(
        r"^\s*TRINITY_REQUEST_(?:START|END)\s+[-\w:.]+\s*$"
    )

    INTERACTIVE_APPROVAL_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"^Action Required$", re.IGNORECASE),
        re.compile(r"^Enter Plan Mode$", re.IGNORECASE),
        re.compile(r"^Allow once$", re.IGNORECASE),
        re.compile(r"^Allow for (?:this )?session$", re.IGNORECASE),
        re.compile(r"^Shift\+Tab\s+to\s+accept\s+edits$", re.IGNORECASE),
    ]

    LEADING_ECHO_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"Read the shared context below", re.IGNORECASE),
        re.compile(r"User'?s request:", re.IGNORECASE),
        re.compile(r"Share your initial opinion", re.IGNORECASE),
        re.compile(r"State your recommendation and key reasoning", re.IGNORECASE),
        re.compile(r"Keep your response under \d+ words", re.IGNORECASE),
        re.compile(r"Previous round opinions:", re.IGNORECASE),
        re.compile(r"For each other agent'?s opinion above", re.IGNORECASE),
        re.compile(r"End your response with either", re.IGNORECASE),
        re.compile(r"I DISAGREE with all", re.IGNORECASE),
        re.compile(r"\[Caveman(?:\s+ULTRA)?:", re.IGNORECASE),
        re.compile(r"^# Shared Context\s*$", re.IGNORECASE),
        re.compile(r"^## Current Goal\s*$", re.IGNORECASE),
        re.compile(r"^## Agents\s*$", re.IGNORECASE),
        re.compile(r"^## Round \d+ Opinions\s*$", re.IGNORECASE),
        re.compile(r"^## Round \d+ Summary\s*$", re.IGNORECASE),
        re.compile(r"^## Agreed Conclusion\s*$", re.IGNORECASE),
        re.compile(r"^## Task Assignment\s*$", re.IGNORECASE),
        re.compile(r"^## Session History\s*$", re.IGNORECASE),
        re.compile(r"^### (?:claude|codex|gemini)\b", re.IGNORECASE),
        re.compile(r"^\*\*(?:claude|codex|gemini)\*\*:", re.IGNORECASE),
    ]

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

        text = cls.strip_completion_marker_tail(raw)
        text = cls.strip_request_boundaries(text)
        text = cls.strip_interactive_approval_ui(text)
        text = cls.strip_leading_prompt_echo(text)

        lines = text.splitlines()
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
            meaningful = sum(
                1
                for line in cleaned.splitlines()
                if line.strip() and len(line.strip()) > 5
            )
            total = len(cleaned.splitlines())
            if total > 10 and meaningful / total < cls.MIN_MEANINGFUL_RATIO:
                logger.warning(
                    "Response appears mostly boilerplate (%d/%d meaningful lines)",
                    meaningful, total,
                )

        return cleaned

    @classmethod
    def strip_completion_marker_tail(cls, text: str) -> str:
        """Remove the completion marker and any captured text after it."""
        match = cls.COMPLETION_MARKER_PATTERN.search(text)
        if not match:
            return text
        return text[: match.start()].rstrip()

    @classmethod
    def strip_request_boundaries(cls, text: str) -> str:
        """Remove Trinity request boundary marker lines from echoed output."""
        return "\n".join(
            line
            for line in text.splitlines()
            if not cls.REQUEST_BOUNDARY_PATTERN.match(line.strip())
        )

    @classmethod
    def strip_interactive_approval_ui(cls, text: str) -> str:
        """Remove trailing interactive approval UI blocks from captured output."""
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if cls._is_interactive_approval_line(line.strip()):
                block_start = cls._interactive_ui_block_start(lines, idx)
                return "\n".join(lines[:block_start]).rstrip()
        return text

    @classmethod
    def strip_leading_prompt_echo(cls, text: str) -> str:
        """Keep the answer tail when a captured response starts with prompt echo."""
        lines = text.splitlines()
        echo_indices = [
            idx
            for idx, line in enumerate(lines)
            if line.strip() and cls._is_leading_echo_line(line.strip())
        ]
        if not echo_indices or not cls._has_leading_echo(lines, echo_indices):
            return text

        tail = "\n".join(lines[echo_indices[-1] + 1 :]).strip()
        if cls._has_substantive_tail(tail):
            return tail
        return text

    @classmethod
    def _is_splash_line(cls, line: str) -> bool:
        """Check if a line matches a known CLI splash/banner pattern."""
        for pattern in cls.SPLASH_PATTERNS:
            if pattern.search(line):
                return True
        return False

    @classmethod
    def _is_interactive_approval_line(cls, line: str) -> bool:
        """Check if a line is part of an interactive approval prompt."""
        normalized = cls._normalize_boxed_ui_line(line)
        for pattern in cls.INTERACTIVE_APPROVAL_PATTERNS:
            if pattern.search(normalized):
                return True
        return False

    @classmethod
    def _interactive_ui_block_start(cls, lines: list[str], trigger_idx: int) -> int:
        block_start = trigger_idx
        while block_start > 0:
            previous = lines[block_start - 1].strip()
            if not previous or cls._is_border_line(previous):
                block_start -= 1
                continue
            break
        return block_start

    @staticmethod
    def _normalize_boxed_ui_line(line: str) -> str:
        normalized = line.strip().strip("│┃║").strip()
        normalized = re.sub(r"^[>❯●○•*\-\d.)\s]+", "", normalized).strip()
        return normalized.strip("│┃║").strip()

    @classmethod
    def _is_leading_echo_line(cls, line: str) -> bool:
        for pattern in cls.LEADING_ECHO_PATTERNS:
            if pattern.search(line):
                return True
        return False

    @classmethod
    def _has_leading_echo(cls, lines: list[str], echo_indices: list[int]) -> bool:
        first_content_idx = cls._first_non_noise_line_index(lines)
        if first_content_idx is not None and first_content_idx in echo_indices:
            return True

        early_nonblank = [
            idx for idx, line in enumerate(lines) if line.strip()
        ][:12]
        early_echo_count = sum(1 for idx in early_nonblank if idx in echo_indices)
        return early_echo_count >= 2

    @classmethod
    def _first_non_noise_line_index(cls, lines: list[str]) -> int | None:
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if (
                not stripped
                or cls._is_splash_line(stripped)
                or cls._is_border_line(stripped)
            ):
                continue
            return idx
        return None

    @classmethod
    def _has_substantive_tail(cls, text: str) -> bool:
        tail = text.strip()
        if len(tail) < cls.MIN_SUBSTANTIVE_TAIL_CHARS:
            return False
        return any(
            len(line.strip()) >= cls.MIN_SUBSTANTIVE_TAIL_CHARS
            for line in tail.splitlines()
        )

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

    @classmethod
    def validate_opinion(cls, raw: str) -> ResponseValidationResult:
        """Validate whether captured output is safe to write as an opinion.

        This is a convenience wrapper around ResponseValidator so callers that
        already depend on ResponseCleaner do not need a second import.
        """
        return ResponseValidator.validate_opinion(raw)


class ResponseValidator:
    """Classifies cleaned agent output before shared.md opinion writes."""

    USABLE_OPINION = "usable_opinion"
    EMPTY = "empty"
    CLI_NOISE = "cli_noise"
    AUTH_WAIT = "auth_wait"
    MODEL_LOADING = "model_loading"
    THINKING_UI = "thinking_ui"
    PROMPT_ECHO = "prompt_echo"
    SHARED_CONTEXT_ECHO = "shared_context_echo"

    MIN_REMAINING_CHARS = 24
    MAX_EXCERPT_CHARS = 800

    AUTH_WAIT_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"\bauth(?:entication)?\s+required\b", re.IGNORECASE),
        re.compile(r"\bselect\s+auth\s+method\b", re.IGNORECASE),
        re.compile(r"\blogin\s+with\s+google\b", re.IGNORECASE),
        re.compile(r"\bsign\s+in\s+with\s+google\b", re.IGNORECASE),
        re.compile(r"\bwaiting\s+for\s+auth(?:entication)?\b", re.IGNORECASE),
        re.compile(r"\bopen\s+(?:the\s+)?(?:following\s+)?url\b", re.IGNORECASE),
        re.compile(r"\benter\s+(?:the\s+)?(?:auth(?:entication)?|oauth)\s+code\b", re.IGNORECASE),
    ]

    MODEL_LOADING_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"\bloading\s+(?:model|session)\b", re.IGNORECASE),
        re.compile(r"\bmodel\s+loading\b", re.IGNORECASE),
        re.compile(r"\bdownloading\s+model\b", re.IGNORECASE),
        re.compile(r"\binitializing\s+(?:model|session|codex)\b", re.IGNORECASE),
        re.compile(r"\bwarming\s+up\s+(?:model|session)\b", re.IGNORECASE),
        re.compile(r"\bpreparing\s+(?:model|session|workspace)\b", re.IGNORECASE),
    ]

    THINKING_UI_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"^\s*(?:[✦✧*•·⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]\s*)?thinking(?:[.\s…]|$)", re.IGNORECASE),
        re.compile(r"\bthinking\s+for\s+\d+\s*(?:s|sec|seconds)\b", re.IGNORECASE),
        re.compile(r"\bthought\s+for\s+\d+\s*(?:s|sec|seconds)\b", re.IGNORECASE),
        re.compile(r"\bprocessing(?:[.\s…]|$)", re.IGNORECASE),
        re.compile(r"\bpress\s+esc\s+to\s+(?:cancel|interrupt|stop)\b", re.IGNORECASE),
    ]

    PROMPT_ECHO_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"Read the shared context below", re.IGNORECASE),
        re.compile(r"User'?s request:", re.IGNORECASE),
        re.compile(r"Share your initial opinion", re.IGNORECASE),
        re.compile(r"State your recommendation and key reasoning", re.IGNORECASE),
        re.compile(r"Keep your response under \d+ words", re.IGNORECASE),
        re.compile(r"Previous round opinions:", re.IGNORECASE),
        re.compile(r"For each other agent'?s opinion above", re.IGNORECASE),
        re.compile(r"End your response with either", re.IGNORECASE),
        re.compile(r"I DISAGREE with all", re.IGNORECASE),
        re.compile(r"\[Caveman(?:\s+ULTRA)?:", re.IGNORECASE),
    ]

    SHARED_CONTEXT_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"^# Shared Context\s*$", re.IGNORECASE),
        re.compile(r"^## Current Goal\s*$", re.IGNORECASE),
        re.compile(r"^## Agents\s*$", re.IGNORECASE),
        re.compile(r"^## Round \d+ Opinions\s*$", re.IGNORECASE),
        re.compile(r"^## Round \d+ Summary\s*$", re.IGNORECASE),
        re.compile(r"^## Agreed Conclusion\s*$", re.IGNORECASE),
        re.compile(r"^## Task Assignment\s*$", re.IGNORECASE),
        re.compile(r"^## Session History\s*$", re.IGNORECASE),
        re.compile(r"^### (?:claude|codex|gemini)\b", re.IGNORECASE),
        re.compile(r"^\*\*(?:claude|codex|gemini)\*\*:", re.IGNORECASE),
    ]

    @classmethod
    def validate_opinion(cls, raw: str) -> ResponseValidationResult:
        """Classify raw agent output as usable opinion or likely CLI/prompt noise."""
        cleaned = ResponseCleaner.clean(raw)
        raw_excerpt = cls._excerpt(raw)

        if not raw or not raw.strip():
            return cls._invalid(
                cls.EMPTY,
                cleaned,
                ("empty response",),
                raw_excerpt,
            )

        if not cleaned or not cleaned.strip():
            return cls._invalid(
                cls.CLI_NOISE,
                cleaned,
                ("cleaner removed all captured text",),
                raw_excerpt,
            )

        counts = {
            cls.AUTH_WAIT: cls._count_matching_lines(cleaned, cls.AUTH_WAIT_PATTERNS),
            cls.MODEL_LOADING: cls._count_matching_lines(cleaned, cls.MODEL_LOADING_PATTERNS),
            cls.THINKING_UI: cls._count_matching_lines(cleaned, cls.THINKING_UI_PATTERNS),
            cls.PROMPT_ECHO: cls._count_matching_lines(cleaned, cls.PROMPT_ECHO_PATTERNS),
            cls.SHARED_CONTEXT_ECHO: cls._count_matching_lines(
                cleaned,
                cls.SHARED_CONTEXT_PATTERNS,
            ),
            cls.CLI_NOISE: cls._count_cli_noise_lines(cleaned),
        }
        nonblank_count = sum(1 for line in cleaned.splitlines() if line.strip())
        nonblank_lines = [line for line in cleaned.splitlines() if line.strip()]
        remaining_lines = [
            line for line in nonblank_lines if not cls._is_validation_noise_line(line.strip())
        ]
        remaining_chars = len("\n".join(remaining_lines).strip())

        state_category = cls._dominant_state_category(counts)
        if state_category and (
            remaining_chars < cls.MIN_REMAINING_CHARS
            or cls._state_markers_dominate(counts[state_category], nonblank_count)
        ):
            return cls._invalid(
                state_category,
                cleaned,
                (
                    f"matched {counts[state_category]} {state_category} marker(s)",
                    "no substantive response remains or markers dominate captured output",
                ),
                raw_excerpt,
            )

        prompt_markers = counts[cls.PROMPT_ECHO]
        shared_markers = counts[cls.SHARED_CONTEXT_ECHO]
        if cls._is_likely_prompt_echo(prompt_markers, shared_markers, nonblank_lines, remaining_chars):
            classification = (
                cls.SHARED_CONTEXT_ECHO
                if shared_markers >= prompt_markers
                else cls.PROMPT_ECHO
            )
            return cls._invalid(
                classification,
                cleaned,
                (
                    f"matched {prompt_markers} prompt marker(s)",
                    f"matched {shared_markers} shared-context marker(s)",
                ),
                raw_excerpt,
            )

        if cls._is_likely_cli_noise(counts[cls.CLI_NOISE], nonblank_lines, remaining_chars):
            return cls._invalid(
                cls.CLI_NOISE,
                cleaned,
                (f"matched {counts[cls.CLI_NOISE]} CLI noise marker(s)",),
                raw_excerpt,
            )

        return ResponseValidationResult(
            usable=True,
            classification=cls.USABLE_OPINION,
            cleaned_text=cleaned,
            reasons=(),
            raw_excerpt=raw_excerpt,
        )

    @classmethod
    def _invalid(
        cls,
        classification: str,
        cleaned_text: str,
        reasons: tuple[str, ...],
        raw_excerpt: str,
    ) -> ResponseValidationResult:
        return ResponseValidationResult(
            usable=False,
            classification=classification,
            cleaned_text=cleaned_text,
            reasons=reasons,
            raw_excerpt=raw_excerpt,
        )

    @classmethod
    def _dominant_state_category(cls, counts: dict[str, int]) -> str | None:
        for category in (cls.AUTH_WAIT, cls.MODEL_LOADING, cls.THINKING_UI):
            if counts[category] > 0:
                return category
        return None

    @staticmethod
    def _state_markers_dominate(marker_count: int, line_count: int) -> bool:
        return marker_count >= 2 and marker_count / max(1, line_count) >= 0.35

    @classmethod
    def _is_likely_prompt_echo(
        cls,
        prompt_markers: int,
        shared_markers: int,
        nonblank_lines: list[str],
        remaining_chars: int,
    ) -> bool:
        total_markers = prompt_markers + shared_markers
        if total_markers == 0:
            return False

        line_count = max(1, len(nonblank_lines))
        marker_ratio = total_markers / line_count

        if prompt_markers >= 2 and remaining_chars < 160:
            return True
        if shared_markers >= 2 and prompt_markers >= 1:
            return True
        if total_markers >= 3 and marker_ratio >= 0.35:
            return True
        return False

    @classmethod
    def _is_likely_cli_noise(
        cls,
        cli_noise_lines: int,
        nonblank_lines: list[str],
        remaining_chars: int,
    ) -> bool:
        if cli_noise_lines == 0:
            return False
        if remaining_chars < cls.MIN_REMAINING_CHARS:
            return True
        return cli_noise_lines / max(1, len(nonblank_lines)) >= 0.8

    @classmethod
    def _is_validation_noise_line(cls, line: str) -> bool:
        if ResponseCleaner._is_splash_line(line) or ResponseCleaner._is_border_line(line):
            return True
        for patterns in (
            cls.AUTH_WAIT_PATTERNS,
            cls.MODEL_LOADING_PATTERNS,
            cls.THINKING_UI_PATTERNS,
            cls.PROMPT_ECHO_PATTERNS,
            cls.SHARED_CONTEXT_PATTERNS,
        ):
            if cls._matches_any(line, patterns):
                return True
        return False

    @classmethod
    def _count_matching_lines(cls, text: str, patterns: list[re.Pattern[str]]) -> int:
        return sum(
            1
            for line in text.splitlines()
            if line.strip() and cls._matches_any(line.strip(), patterns)
        )

    @classmethod
    def _count_cli_noise_lines(cls, text: str) -> int:
        return sum(
            1
            for line in text.splitlines()
            if line.strip()
            and (
                ResponseCleaner._is_splash_line(line.strip())
                or ResponseCleaner._is_border_line(line.strip())
            )
        )

    @staticmethod
    def _matches_any(line: str, patterns: list[re.Pattern[str]]) -> bool:
        return any(pattern.search(line) for pattern in patterns)

    @classmethod
    def _excerpt(cls, text: str) -> str:
        stripped = text.strip()
        if len(stripped) <= cls.MAX_EXCERPT_CHARS:
            return stripped
        return stripped[: cls.MAX_EXCERPT_CHARS].rstrip() + "\n[truncated]"
