"""Shared context engine — manages the shared.md 'shared brain' file."""

from __future__ import annotations

import logging
import re
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

    def write(self, content: str) -> None:
        """Overwrite the entire shared.md."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")

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
        entry = f"\n### {agent}\n{opinion}\n"
        self.append_to_section(section_name, entry)

    def update_consensus(self, consensus_text: str) -> None:
        """Write the agreed conclusion section."""
        self.write_section("Agreed Conclusion", consensus_text)

    def update_tasks(self, tasks: dict[str, str]) -> None:
        """Write task assignments."""
        lines = []
        for agent, task in tasks.items():
            lines.append(f"- **{agent}**: {task}")
        self.write_section("Task Assignment", "\n".join(lines))

    def append_session_summary(self, agent: str, summary: str) -> None:
        """Append a session rotation summary to session history."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n### {agent} — {timestamp}\n{summary}\n"
        self.append_to_section("Session History", entry)

    def get_context_for_rotation(self, recent_rounds: int = 3) -> str:
        """Get context for session handoff: pinned sections + recent rounds."""
        full = self.read()
        sections = self._parse_sections(full)

        result_parts: list[str] = []

        # Always include pinned sections
        for key, content in sections.items():
            if key in self.keep_sections:
                result_parts.append(content)

        # Include recent round sections
        round_sections = sorted(
            [(k, v) for k, v in sections.items() if k.startswith("round")],
            key=lambda x: x[0],
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
