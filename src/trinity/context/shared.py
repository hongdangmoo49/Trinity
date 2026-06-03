"""Shared context engine — manages the shared.md 'shared brain' file."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SharedContextEngine:
    """Section-based CRUD on shared.md.

    The shared.md file is the central 'brain' that all agents read from
    and write to. Sections are delimited by ## headings.

    Layout:
        # Shared Context

        ## Current Goal
        (user's original request)

        ## Round 1 Opinions
        ### claude
        ...
        ### codex
        ...

        ## Agreed Conclusion
        ...

        ## Task Assignment
        ...

        ## Session History
        ...
    """

    def __init__(
        self,
        path: Path,
        keep_sections: list[str] | None = None,
    ):
        self.path = path
        self.keep_sections: set[str] = {
            self._normalize_heading(h) for h in (keep_sections or [])
        }

    def _normalize_heading(self, heading: str) -> str:
        """Normalize a heading for comparison (strip ## prefix and whitespace)."""
        return heading.lstrip("#").strip().lower()

    def read(self) -> str:
        """Read the entire shared.md content."""
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")

    @staticmethod
    def _sanitize_md_heading(text: str) -> str:
        """Escape heading markers to prevent markdown section injection."""
        return re.sub(r'^#{1,3}\s+', r'\\# ', text, flags=re.MULTILINE)

    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove surrogate characters that can arise from tmux/terminal input.

        When Python reads bytes with the 'surrogateescape' error handler
        (the default for os.fsdecode and some terminal I/O), invalid UTF-8
        bytes become surrogate code points (U+D800–U+DFFF). These cannot be
        re-encoded as UTF-8, causing UnicodeEncodeError on write.

        Round-tripping through encode/decode with 'replace' swaps each
        unencodable character for '?' (encode) then cleanly decodes back.
        """
        return text.encode("utf-8", errors="replace").decode("utf-8")

    @staticmethod
    def _format_diagnostic_excerpt(excerpt: str, max_chars: int) -> str:
        """Bound and fence-safe diagnostic text for shared.md."""
        text = excerpt.strip()
        if not text:
            return ""
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n[truncated]"
        return text.replace("```", "'''")

    def write(self, content: str) -> None:
        """Overwrite the entire shared.md."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        sanitized = self._sanitize(content)
        self.path.write_text(sanitized, encoding="utf-8")

    def read_section(self, section_name: str) -> str | None:
        """Read a specific ## section by name. Returns None if not found."""
        content = self.read()
        sections = self._parse_sections(content)
        key = self._normalize_heading(section_name)
        return sections.get(key)

    def write_section(self, heading: str, content: str) -> None:
        """Replace or append a ## section."""
        full = self.read()
        sections = self._parse_sections(full)
        key = self._normalize_heading(heading)

        if key in sections:
            # Replace existing section
            full = self._replace_section(full, heading, content)
        else:
            # Append new section
            if full and not full.endswith("\n"):
                full += "\n"
            full += f"\n## {heading}\n{content}\n"

        self.write(full)

    def append_to_section(self, heading: str, content: str) -> None:
        """Append content to an existing section (or create it)."""
        existing = self.read_section(heading)
        if existing is not None:
            self.write_section(heading, existing.rstrip("\n") + "\n" + content)
        else:
            self.write_section(heading, content)

    def append_opinion(self, agent: str, round_num: int, opinion: str) -> None:
        """Append an agent's opinion to the round section."""
        section_name = f"Round {round_num} Opinions"
        safe_agent = self._sanitize_md_heading(agent)
        safe_opinion = self._sanitize_md_heading(opinion)
        entry = f"\n### {safe_agent}\n{safe_opinion}\n"
        self.append_to_section(section_name, entry)

    def append_invalid_response_diagnostic(
        self,
        agent: str,
        round_num: int,
        classification: str,
        reasons: Iterable[str] = (),
        excerpt: str = "",
        max_excerpt_chars: int = 1200,
    ) -> None:
        """Record a rejected response outside Round N Opinions."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"\n### Round {round_num} / {agent} — {timestamp}",
            f"- classification: {classification}",
        ]

        reason_list = [reason for reason in reasons if reason]
        if reason_list:
            lines.append("- reasons:")
            lines.extend(f"  - {reason}" for reason in reason_list)

        safe_excerpt = self._format_diagnostic_excerpt(excerpt, max_excerpt_chars)
        if safe_excerpt:
            lines.extend(["", "```text", safe_excerpt, "```"])

        self.append_to_section("Response Diagnostics", "\n".join(lines))

    def update_consensus(self, consensus_text: str) -> None:
        """Write the agreed conclusion section."""
        self.write_section("Agreed Conclusion", consensus_text)

    def update_tasks(self, tasks: dict[str, str]) -> None:
        """Write task assignments."""
        lines = []
        for agent, task in tasks.items():
            safe_agent = self._sanitize_md_heading(agent)
            safe_task = self._sanitize_md_heading(task)
            lines.append(f"- **{safe_agent}**: {safe_task}")
        self.write_section("Task Assignment", "\n".join(lines))

    def append_task_result(
        self,
        *,
        package_id: str,
        agent: str,
        status: str,
        summary: str,
        files_changed: Iterable[str] = (),
        decisions_made: Iterable[str] = (),
        blockers: Iterable[str] = (),
        follow_up: Iterable[str] = (),
        raw_response_path: Path | None = None,
    ) -> None:
        """Append a work package execution result to shared.md."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_package = self._sanitize_md_heading(package_id)
        safe_agent = self._sanitize_md_heading(agent)
        safe_summary = self._sanitize_md_heading(summary)

        lines = [
            f"\n### {safe_package} / {safe_agent} — {timestamp}",
            f"- status: {status}",
        ]
        if raw_response_path is not None:
            lines.append(f"- raw_response_path: `{raw_response_path}`")
        if safe_summary:
            lines.extend(["", "#### Summary", safe_summary])

        def _append_list(title: str, items: Iterable[str]) -> None:
            values = [
                self._sanitize_md_heading(str(item).strip())
                for item in items
                if str(item).strip()
            ]
            if not values:
                return
            lines.extend(["", f"#### {title}"])
            lines.extend(f"- {item}" for item in values)

        _append_list("Files Changed", files_changed)
        _append_list("Decisions Made", decisions_made)
        _append_list("Blockers", blockers)
        _append_list("Follow-up", follow_up)
        self.append_to_section("Task Results", "\n".join(lines))

    def append_session_summary(self, agent: str, summary: str) -> None:
        """Append a session rotation summary to session history."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        safe_agent = self._sanitize_md_heading(agent)
        safe_summary = self._sanitize_md_heading(summary)
        entry = f"\n### {safe_agent} — {timestamp}\n{safe_summary}\n"
        self.append_to_section("Session History", entry)

    def write_compressed_summary(self, round_num: int, summary: str) -> None:
        """Store a compressed summary for a completed round."""
        self.write_section(f"Round {round_num} Summary", summary)

    def remove_section(self, heading: str) -> None:
        """Remove a ## section entirely from shared.md."""
        full = self.read()
        sections = self._parse_sections(full)
        key = self._normalize_heading(heading)
        if key not in sections:
            return
        lines = full.splitlines()
        result = []
        in_target = False
        heading_prefix = f"## {heading}"
        for line in lines:
            if line.strip() == heading_prefix:
                in_target = True
                continue
            if in_target and line.startswith("## ") and not line.startswith("### "):
                in_target = False
            if not in_target:
                result.append(line)
        self.write("\n".join(result))

    def get_rounds_for_prompt(
        self, current_round: int, verbatim_rounds: int = 1
    ) -> str:
        """Build context for a round prompt with compression.

        Returns formatted text with:
        - Compressed summaries for old rounds
        - Full verbatim text for the latest rounds

        Args:
            current_round: The round about to start (1-based).
            verbatim_rounds: How many recent rounds to include verbatim.
        """
        full = self.read()
        sections = self._parse_sections(full)

        parts: list[str] = []

        prev_round = current_round - 1
        verbatim_start = max(1, prev_round - verbatim_rounds + 1)
        compress_end = verbatim_start - 1

        # Compressed summaries for old rounds
        if compress_end >= 1:
            compressed_parts: list[str] = []
            for r in range(1, compress_end + 1):
                summary_key = self._normalize_heading(f"Round {r} Summary")
                if summary_key in sections:
                    compressed_parts.append(sections[summary_key])
                else:
                    compressed_parts.append(f"(Round {r}: see shared context for details)")

            if compressed_parts:
                parts.append("## Earlier Rounds (summarized)\n" + "\n".join(compressed_parts))

        # Verbatim rounds
        for r in range(verbatim_start, prev_round + 1):
            section_key = self._normalize_heading(f"Round {r} Opinions")
            if section_key in sections:
                parts.append(sections[section_key])

        return "\n\n".join(parts)

    def get_context_for_rotation(self, recent_rounds: int = 3) -> str:
        """Get context for session handoff: pinned sections + recent rounds."""
        full = self.read()
        sections = self._parse_sections(full)

        result_parts: list[str] = []

        # Always include pinned sections
        for key, content in sections.items():
            if key in self.keep_sections:
                result_parts.append(content)

        # Include recent round sections (sorted numerically, not lexicographically)
        def _round_sort_key(item):
            """Extract numeric part from round section key for proper ordering."""
            key, _ = item
            match = re.search(r'round\s+(\d+)', key)
            return int(match.group(1)) if match else 0

        round_sections = sorted(
            [(k, v) for k, v in sections.items() if k.startswith("round")],
            key=_round_sort_key,
        )
        for key, content in round_sections[-recent_rounds:]:
            result_parts.append(content)

        # Include session history summaries
        if "session history" in sections:
            result_parts.append(sections["session history"])

        return "\n\n".join(result_parts)

    def initialize(self, goal: str, agent_names: list[str]) -> None:
        """Create a fresh shared.md with initial structure."""
        agents_list = "\n".join(f"- {name}" for name in agent_names)
        content = (
            f"# Shared Context\n"
            f"\n"
            f"## Current Goal\n"
            f"{goal}\n"
            f"\n"
            f"## Agents\n"
            f"{agents_list}\n"
        )
        self.write(content)

    # --- Private helpers ---

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Parse markdown into {normalized_heading: full_section_text}."""
        if not content.strip():
            return {}

        sections: dict[str, str] = {}
        current_heading: str | None = None
        current_lines: list[str] = []

        for line in content.splitlines():
            if line.startswith("## ") and not line.startswith("### "):
                # Save previous section
                if current_heading is not None:
                    key = self._normalize_heading(current_heading)
                    sections[key] = "\n".join(current_lines)

                current_heading = line[3:].strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        # Save last section
        if current_heading is not None:
            key = self._normalize_heading(current_heading)
            sections[key] = "\n".join(current_lines)

        return sections

    def _replace_section(self, content: str, heading: str, new_body: str) -> str:
        """Replace a section's content while preserving the heading."""
        lines = content.splitlines()
        result: list[str] = []
        in_target = False
        heading_prefix = f"## {heading}"

        for line in lines:
            if line.strip() == heading_prefix:
                in_target = True
                result.append(line)
                result.append(new_body)
                continue

            if in_target and line.startswith("## ") and not line.startswith("### "):
                in_target = False

            if not in_target:
                result.append(line)

        return "\n".join(result)
