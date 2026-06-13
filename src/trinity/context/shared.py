"""Shared context engine — manages the shared.md 'shared brain' file."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from trinity.context.memory import ContentRouter, MemoryRecord, MemoryStats, MemoryStore
from trinity.context.packing import ContextPacker, PackedContext

logger = logging.getLogger(__name__)

DEFAULT_MAX_READ_BYTES = 1_048_576
DEFAULT_SECTION_ENTRY_MAX_CHARS = 12_000
DEFAULT_LIST_ITEM_MAX_CHARS = 500
DEFAULT_LIST_MAX_ITEMS = 30


class SharedContextEngine:
    """Section-based CRUD on shared.md.

    The shared.md file is the central 'brain' that all agents read from
    and write to. Sections are delimited by ## headings.

    Layout:
        # Shared Context

        ## Current Goal
        (user's original request)

        ## Round 1 Synthesis
        (central summary and next-round prompt)

        ## Round 1 Responses
        (artifact paths for raw/clean provider outputs)

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
        max_read_bytes: int = DEFAULT_MAX_READ_BYTES,
        section_entry_max_chars: int = DEFAULT_SECTION_ENTRY_MAX_CHARS,
        memory_index_enabled: bool = True,
        memory_store: MemoryStore | None = None,
    ):
        self.path = path
        self.max_read_bytes = max_read_bytes
        self.section_entry_max_chars = section_entry_max_chars
        self.memory_store = (
            memory_store
            if memory_store is not None
            else (
                MemoryStore(path.parent / "memory" / "index.sqlite")
                if memory_index_enabled
                else None
            )
        )
        self.keep_sections: set[str] = {
            self._normalize_heading(h) for h in (keep_sections or [])
        }
        self._pack_cache_key: tuple[object, ...] | None = None
        self._pack_cache_value: PackedContext | None = None

    def _normalize_heading(self, heading: str) -> str:
        """Normalize a heading for comparison (strip ## prefix and whitespace)."""
        return heading.lstrip("#").strip().lower()

    def read(self) -> str:
        """Read the entire shared.md content."""
        if not self.path.exists():
            return ""
        if self._is_oversized():
            return self._oversized_read_notice()
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
        self.ensure_mutable_projection()
        full = self.read()
        sections = self._parse_sections(full)
        key = self._normalize_heading(heading)
        safe_content = self._strip_section_heading(content, heading)

        if key in sections:
            # Replace existing section
            full = self._replace_section(full, heading, safe_content)
        else:
            # Append new section
            if full and not full.endswith("\n"):
                full += "\n"
            full += f"\n## {heading}\n{safe_content}\n"

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

    def append_response_reference(
        self,
        *,
        agent: str,
        round_num: int,
        request_id: str,
        status: str,
        clean_output_path: Path | str | None = None,
        raw_output_path: Path | str | None = None,
        confidence: float | None = None,
        token_count: int | None = None,
    ) -> None:
        """Append provider response artifact references without response body text."""
        safe_agent = self._sanitize_md_heading(agent)
        safe_request = self._sanitize_md_heading(request_id)
        safe_status = self._sanitize_md_heading(status)
        lines = [
            f"\n### {safe_agent}",
            f"- request_id: `{safe_request}`",
            f"- status: {safe_status}",
        ]
        if confidence is not None:
            lines.append(f"- confidence: {confidence:.2f}")
        if token_count is not None:
            lines.append(f"- tokens: {token_count}")
        if clean_output_path is not None:
            lines.append(f"- clean_output_path: `{clean_output_path}`")
        if raw_output_path is not None:
            lines.append(f"- raw_output_path: `{raw_output_path}`")
        self.append_to_section(f"Round {round_num} Responses", "\n".join(lines))

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
        safe_summary = self._bounded_block(self._sanitize_md_heading(summary))

        lines = [
            f"\n### {safe_package} / {safe_agent} — {timestamp}",
            f"- status: {status}",
        ]
        if raw_response_path is not None:
            lines.append(f"- raw_response_path: `{raw_response_path}`")
        if safe_summary:
            lines.extend(["", "#### Summary", safe_summary])

        def _append_list(title: str, items: Iterable[str]) -> None:
            values = self._bounded_items(items)
            if not values:
                return
            lines.extend(["", f"#### {title}"])
            lines.extend(f"- {item}" for item in values)

        _append_list("Files Changed", files_changed)
        _append_list("Decisions Made", decisions_made)
        _append_list("Blockers", blockers)
        _append_list("Follow-up", follow_up)
        content = "\n".join(lines)
        self._record_memory(
            kind="execution_result",
            source="shared.append_task_result",
            title=f"{safe_package} / {safe_agent}",
            summary=ContentRouter.summarize(content),
            agent=safe_agent,
            work_package_id=safe_package,
            artifact_path=str(raw_response_path or ""),
            tags=["execution", status],
        )
        self.append_to_section("Task Results", content)

    def append_subtask_result(
        self,
        *,
        subtask_id: str,
        parent_package_id: str,
        parent_agent: str,
        delegated_to: str,
        objective: str,
        result_summary: str,
        status: str,
        decisions_made: Iterable[str] = (),
        files_changed: Iterable[str] = (),
        unresolved_issues: Iterable[str] = (),
    ) -> None:
        """Append a provider-internal delegation report to shared.md."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_subtask = self._sanitize_md_heading(subtask_id)
        safe_package = self._sanitize_md_heading(parent_package_id)
        safe_agent = self._sanitize_md_heading(parent_agent)
        safe_delegate = self._sanitize_md_heading(delegated_to)
        safe_objective = self._bounded_block(self._sanitize_md_heading(objective))
        safe_summary = self._bounded_block(self._sanitize_md_heading(result_summary))

        lines = [
            f"\n### {safe_subtask} / {safe_package} — {timestamp}",
            f"- parent_agent: {safe_agent}",
            f"- delegated_to: {safe_delegate}",
            f"- status: {status}",
        ]
        if safe_objective:
            lines.extend(["", "#### Objective", safe_objective])
        if safe_summary:
            lines.extend(["", "#### Result Summary", safe_summary])

        def _append_list(title: str, items: Iterable[str]) -> None:
            values = self._bounded_items(items)
            if not values:
                return
            lines.extend(["", f"#### {title}"])
            lines.extend(f"- {item}" for item in values)

        _append_list("Decisions Made", decisions_made)
        _append_list("Files Changed", files_changed)
        _append_list("Unresolved Issues", unresolved_issues)
        content = "\n".join(lines)
        self._record_memory(
            kind="subtask_result",
            source="shared.append_subtask_result",
            title=f"{safe_subtask} / {safe_package}",
            summary=ContentRouter.summarize(content),
            agent=safe_agent,
            work_package_id=safe_package,
            artifact_path="",
            tags=["subtask", status],
        )
        self.append_to_section("Subtasks", content)

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

    def write_synthesis_summary(
        self,
        round_num: int,
        summary: str,
        *,
        source: str = "",
        provider: str = "",
        model: str = "",
        fallback_used: object | None = None,
        fallback_reason: str = "",
        next_round_prompt: str = "",
    ) -> None:
        """Store the central synthesis result for a completed round."""
        lines: list[str] = []
        if source:
            lines.append(f"- source: {self._sanitize_md_heading(source)}")
        if provider:
            lines.append(f"- provider: {self._sanitize_md_heading(provider)}")
        if model:
            lines.append(f"- model: {self._sanitize_md_heading(model)}")
        if fallback_used is not None:
            fallback_text = "true" if bool(fallback_used) else "false"
            lines.append(f"- fallback_used: {fallback_text}")
        if fallback_reason:
            reason = self._sanitize_md_heading(fallback_reason)
            lines.append(f"- fallback_reason: {reason}")
        safe_summary = self._sanitize_md_heading(summary)
        if safe_summary:
            lines.extend(["", "### Summary", safe_summary])
        safe_next = self._sanitize_md_heading(next_round_prompt)
        if safe_next:
            lines.extend(["", "### Next Round Prompt", safe_next])
        self.write_section(f"Round {round_num} Synthesis", "\n".join(lines).strip())

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
        self,
        current_round: int,
        verbatim_rounds: int = 1,
        include_compressed_summaries: bool = True,
    ) -> str:
        """Build context for a round prompt with compression.

        Returns formatted text with:
        - Compressed summaries for old rounds
        - Full verbatim text for the latest rounds

        Args:
            current_round: The round about to start (1-based).
            verbatim_rounds: How many recent rounds to include verbatim.
            include_compressed_summaries: Whether Round N Summary sections may
                replace legacy opinion sections.
        """
        full = self.read()
        sections = self._parse_sections(full)

        parts: list[str] = []

        prev_round = current_round - 1
        verbatim_start = max(1, prev_round - verbatim_rounds + 1)
        compress_end = verbatim_start - 1

        # Compressed summaries for old rounds. Synthesis sections are already
        # compact canonical summaries, so prefer them over compression output.
        if compress_end >= 1:
            compressed_parts: list[str] = []
            for r in range(1, compress_end + 1):
                round_context = self._round_context_for_prompt(
                    sections,
                    r,
                    include_compressed_summary=include_compressed_summaries,
                )
                if round_context:
                    compressed_parts.append(round_context)
                else:
                    compressed_parts.append(f"(Round {r}: see shared context for details)")

            if compressed_parts:
                parts.append("## Earlier Rounds (summarized)\n" + "\n".join(compressed_parts))

        # Recent rounds. Prefer synthesis summaries over full opinions to keep
        # prompts stable and bounded; legacy opinions remain a fallback.
        for r in range(verbatim_start, prev_round + 1):
            round_context = self._round_context_for_prompt(
                sections,
                r,
                include_compressed_summary=include_compressed_summaries,
            )
            if round_context:
                parts.append(round_context)

        return "\n\n".join(parts)

    def _round_context_for_prompt(
        self,
        sections: dict[str, str],
        round_num: int,
        *,
        include_compressed_summary: bool = True,
    ) -> str:
        """Return the best shared.md section for prompting about a prior round."""
        headings = [f"Round {round_num} Synthesis"]
        if include_compressed_summary:
            headings.append(f"Round {round_num} Summary")
        headings.extend(
            [
                f"Round {round_num} Opinions",
                f"Round {round_num} Responses",
            ]
        )
        for heading in headings:
            key = self._normalize_heading(heading)
            if key in sections and sections[key].strip():
                return sections[key]
        return ""

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

    def ensure_mutable_projection(self) -> Path | None:
        """Move an oversized shared.md aside before write-based mutations.

        Startup, resume, and retry paths can mutate shared.md while the file is
        already too large to read safely. Preserve the original file and create
        a small recovery projection so future section writes stay bounded.
        """
        if not self._is_oversized():
            return None

        backup_path = self._next_oversized_backup_path()
        self.path.rename(backup_path)
        size = backup_path.stat().st_size
        logger.warning(
            "Moved oversized shared context to %s (%s bytes)",
            backup_path,
            size,
        )
        self.write(self._recovery_projection(backup_path, size))
        return backup_path

    def memory_stats(self) -> MemoryStats | None:
        """Return memory index statistics if the memory index is enabled."""
        if self.memory_store is None:
            return None
        return self.memory_store.stats()

    def pack_context_for_prompt(
        self,
        *,
        workflow_id: str = "",
        prompt_budget_tokens: int = 24_000,
        recent_records: int = 30,
    ) -> PackedContext:
        """Build a token-bounded context bundle for provider prompts."""
        cache_key = self._pack_context_cache_key(
            workflow_id=workflow_id,
            prompt_budget_tokens=prompt_budget_tokens,
            recent_records=recent_records,
        )
        if self._pack_cache_key == cache_key and self._pack_cache_value is not None:
            return self._pack_cache_value

        sections = self._parse_sections(self.read())
        pinned = {
            "Current Goal": sections.get("current goal", ""),
            "Agreed Conclusion": sections.get("agreed conclusion", ""),
            "Task Assignment": sections.get("task assignment", ""),
        }
        packer = ContextPacker(
            self.memory_store,
            prompt_budget_tokens=prompt_budget_tokens,
            recent_records=recent_records,
        )
        packed = packer.pack(pinned_sections=pinned, workflow_id=workflow_id)
        self._pack_cache_key = cache_key
        self._pack_cache_value = packed
        return packed

    def compact_projection_from_memory(
        self,
        *,
        target_bytes: int | None = None,
        recent_records: int = 20,
    ) -> Path | None:
        """Rebuild shared.md as a bounded projection over pinned sections + memory."""
        backup_path = self.ensure_mutable_projection()
        sections = self._parse_sections(self.read())
        target = target_bytes or self.max_read_bytes
        parts = ["# Shared Context"]

        for heading in (
            "Current Goal",
            "Agents",
            "Agreed Conclusion",
            "Task Assignment",
            "Recovery Notice",
        ):
            body = sections.get(self._normalize_heading(heading), "").strip()
            if body:
                parts.append(self._format_section(heading, body))

        if self.memory_store is not None:
            stats = self.memory_store.stats()
            memory_lines = [
                f"- records: {stats.record_count}",
                f"- artifacts: {stats.artifact_count}",
                f"- estimated_tokens: {stats.total_token_estimate}",
            ]
            recent = self.memory_store.recent(limit=recent_records)
            if recent:
                memory_lines.extend(["", "### Recent Records"])
                for record in recent:
                    line = (
                        f"- `{record.id}` {record.kind}: {record.title}"
                        f" ({record.agent or 'unknown'})"
                    )
                    if record.artifact_path:
                        line += f" artifact=`{record.artifact_path}`"
                    memory_lines.append(line)
                    if record.summary:
                        memory_lines.append(
                            "  "
                            + record.summary.replace("\n", "\n  ")[:800].rstrip()
                        )
            parts.append(self._format_section("Memory Projection", "\n".join(memory_lines)))

        projection = "\n\n".join(parts).rstrip() + "\n"
        encoded = projection.encode("utf-8", errors="replace")
        if target > 0 and len(encoded) > target:
            marker = "\n\n## Projection Truncated\nMemory projection exceeded target size.\n"
            keep = max(0, target - len(marker.encode("utf-8")) - 256)
            projection = projection.encode("utf-8", errors="replace")[:keep].decode(
                "utf-8",
                errors="ignore",
            ).rstrip() + marker
        self.write(projection)
        return backup_path

    # --- Private helpers ---

    def _pack_context_cache_key(
        self,
        *,
        workflow_id: str,
        prompt_budget_tokens: int,
        recent_records: int,
    ) -> tuple[object, ...]:
        return (
            workflow_id,
            prompt_budget_tokens,
            recent_records,
            self._path_stat_key(self.path),
            self._memory_store_cache_key(),
        )

    def _memory_store_cache_key(self) -> tuple[object, ...]:
        if self.memory_store is None:
            return ("disabled",)
        try:
            stats = self.memory_store.stats()
        except Exception:
            logger.exception("Failed to build memory store cache key")
            return ("error",)
        return (
            "enabled",
            str(self.memory_store.path),
            stats.record_count,
            stats.artifact_count,
            stats.total_token_estimate,
            stats.latest_updated_at,
        )

    @staticmethod
    def _path_stat_key(path: Path) -> tuple[str, int, int]:
        try:
            stat = path.stat()
        except OSError:
            return ("missing", 0, 0)
        return ("file", stat.st_mtime_ns, stat.st_size)

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Parse markdown into {normalized_heading: section_body}."""
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
                current_lines = []
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

    def _format_section(self, heading: str, body: str) -> str:
        return f"## {heading}\n{body.strip()}"

    def _record_memory(
        self,
        *,
        kind: str,
        source: str,
        title: str,
        summary: str,
        agent: str = "",
        work_package_id: str = "",
        artifact_path: str = "",
        tags: list[str] | None = None,
    ) -> None:
        if self.memory_store is None:
            return
        content_hash = MemoryStore.hash_text(
            "\n".join((kind, source, title, summary, artifact_path))
        )
        record = MemoryRecord(
            id=f"{kind}-{work_package_id or 'global'}-{content_hash[:12]}",
            kind=kind,
            source=source,
            title=title,
            summary=summary,
            agent=agent,
            work_package_id=work_package_id,
            artifact_path=artifact_path,
            content_hash=content_hash,
            tags=tags or [],
        )
        self.memory_store.upsert(record)

    def _is_oversized(self) -> bool:
        if self.max_read_bytes <= 0 or not self.path.exists():
            return False
        try:
            return self.path.stat().st_size > self.max_read_bytes
        except OSError:
            logger.exception("Failed to stat shared context: %s", self.path)
            return False

    def _oversized_read_notice(self) -> str:
        try:
            size = self.path.stat().st_size
        except OSError:
            size = -1
        return self._recovery_projection(self.path, size, moved=False)

    def _recovery_projection(
        self,
        original_path: Path,
        size: int,
        *,
        moved: bool = True,
    ) -> str:
        state = "moved aside" if moved else "not loaded"
        return (
            "# Shared Context\n\n"
            "## Recovery Notice\n"
            f"`shared.md` was {state} because it exceeded the safe read limit.\n\n"
            f"- original_path: `{original_path}`\n"
            f"- original_size_bytes: {size}\n"
            f"- max_read_bytes: {self.max_read_bytes}\n"
            "- next_step: run `/memory compact` or inspect the preserved file.\n"
        )

    def _next_oversized_backup_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        candidate = self.path.with_name(f"{self.path.name}.oversized-{timestamp}")
        suffix = 1
        while candidate.exists():
            candidate = self.path.with_name(
                f"{self.path.name}.oversized-{timestamp}-{suffix}"
            )
            suffix += 1
        return candidate

    def _strip_section_heading(self, content: str, heading: str) -> str:
        """Remove an accidental leading target heading from section body text."""
        lines = content.splitlines()
        if lines and lines[0].strip() == f"## {heading}":
            return "\n".join(lines[1:]).lstrip("\n")
        return content

    def _bounded_block(self, text: str) -> str:
        if self.section_entry_max_chars <= 0:
            return text
        if len(text) <= self.section_entry_max_chars:
            return text
        return text[: self.section_entry_max_chars].rstrip() + "\n[truncated]"

    def _bounded_items(self, items: Iterable[str]) -> list[str]:
        values: list[str] = []
        omitted = 0
        for raw in items:
            value = self._sanitize_md_heading(str(raw).strip())
            if not value:
                continue
            if len(value) > DEFAULT_LIST_ITEM_MAX_CHARS:
                value = value[:DEFAULT_LIST_ITEM_MAX_CHARS].rstrip() + " [truncated]"
            if len(values) < DEFAULT_LIST_MAX_ITEMS:
                values.append(value)
            else:
                omitted += 1
        if omitted:
            values.append(f"... {omitted} more omitted")
        return values
