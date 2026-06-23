"""Workflow side inspector widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.progress_summary import (
    blocked_detail_line,
    blocked_work_packages,
    compact_wp_line,
    current_work_packages,
    next_work_package_entries,
    next_work_package_line,
    progress_bar,
    progress_summary_line,
    waiting_on_detail_line,
    work_package_counts,
    work_package_state,
)


class WorkflowInspector(Vertical):
    """Compact read-only workflow status side surface."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.snapshot = WorkflowNexusSnapshot()
        self._section_text: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Static("Progress", classes="inspector-title")
        yield Static("", id="inspector-progress")
        yield Static("Current", classes="inspector-title")
        yield Static("", id="inspector-current")
        yield Static("Next", classes="inspector-title")
        yield Static("", id="inspector-next")
        yield Static("Blocked", classes="inspector-title")
        yield Static("", id="inspector-blocked")
        yield Static("Workflow", classes="inspector-title")
        yield Static("", id="inspector-workflow")
        yield Static("Providers", classes="inspector-title")
        yield Static("", id="inspector-providers")
        yield Static("Questions", classes="inspector-title")
        yield Static("", id="inspector-questions")
        yield Static("Decisions", classes="inspector-title")
        yield Static("", id="inspector-decisions")
        yield Static("Post Review", classes="inspector-title")
        yield Static("", id="inspector-post-review")
        yield Static("Execution Log", classes="inspector-title")
        yield Static("", id="inspector-log")

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self._update_section("#inspector-progress", self._progress_summary(snapshot))
        self._update_section(
            "#inspector-current",
            self._list_or_empty(
                [
                    compact_wp_line(package)
                    for package in current_work_packages(snapshot.work_package_details)
                ]
            ),
        )
        self._update_section(
            "#inspector-next",
            self._list_or_empty(self._next_lines(snapshot), limit=8),
        )
        self._update_section(
            "#inspector-blocked",
            self._list_or_empty(self._blocked_lines(snapshot)),
        )
        self._update_section(
            "#inspector-workflow",
            "\n".join(
                [
                    f"ID: {snapshot.session_id or '(new)'}",
                    f"State: {snapshot.state}",
                    f"Round: {snapshot.round_num}",
                ]
            ),
        )
        self._update_section(
            "#inspector-providers",
            self._list_or_empty(self._provider_lines(snapshot)),
        )
        self._update_section(
            "#inspector-questions",
            self._list_or_empty([question.question for question in snapshot.questions]),
        )
        self._update_section(
            "#inspector-decisions",
            self._list_or_empty(snapshot.decisions),
        )
        self._update_section(
            "#inspector-post-review",
            self._list_or_empty(
                [
                    f"{item.id} [{item.severity}/{item.status}] {item.title or item.summary}"
                    for item in snapshot.post_review_items
                ]
            ),
        )
        self._update_section(
            "#inspector-log",
            self._list_or_empty(snapshot.execution_log[-5:]),
        )

    def _update_section(self, selector: str, text: str) -> None:
        if self._section_text.get(selector) == text:
            return
        self.query_one(selector, Static).update(text)
        self._section_text[selector] = text

    @staticmethod
    def _list_or_empty(items: list[str], *, limit: int = 5) -> str:
        if not items:
            return "(none)"
        lines: list[str] = []
        for item in items[:limit]:
            if item.startswith("  "):
                lines.append(item)
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)

    @staticmethod
    def _progress_summary(snapshot: WorkflowNexusSnapshot) -> str:
        if not snapshot.work_package_details:
            return "(none)"
        return "\n".join(
            [
                progress_summary_line(snapshot.work_package_details),
                progress_bar(work_package_counts(snapshot.work_package_details), width=12),
            ]
        )

    @staticmethod
    def _blocked_lines(snapshot: WorkflowNexusSnapshot) -> list[str]:
        lines: list[str] = []
        for package in blocked_work_packages(snapshot.work_package_details, limit=3):
            lines.append(compact_wp_line(package))
            detail = blocked_detail_line(package)
            if detail:
                lines.append(f"  {detail}")
        blocked_count = len(
            [
                package
                for package in snapshot.work_package_details
                if work_package_state(package) == "blocked"
            ]
        )
        if blocked_count > 3:
            lines.append(f"+{blocked_count - 3} more")
        return lines

    @staticmethod
    def _next_lines(snapshot: WorkflowNexusSnapshot) -> list[str]:
        all_entries = next_work_package_entries(snapshot.work_package_details, limit=None)
        entries = all_entries[:3]
        lines: list[str] = []
        for entry in entries:
            lines.append(next_work_package_line(entry))
            detail = waiting_on_detail_line(entry)
            if detail:
                lines.append(f"  {detail}")
        next_count = len(all_entries)
        if next_count > len(entries):
            lines.append(f"+{next_count - len(entries)} more")
        return lines

    @staticmethod
    def _provider_lines(snapshot: WorkflowNexusSnapshot) -> list[str]:
        lines: list[str] = []
        for provider in snapshot.providers:
            if not provider.enabled:
                continue
            model = provider.actual_model or provider.model_label or provider.configured_model
            context = (
                f"{provider.context_window:,}"
                if provider.context_window > 0
                else "unknown"
            )
            session = (
                provider.session_id[:12]
                if provider.session_id
                else "none"
            )
            source = provider.budget_source or "unknown"
            lines.append(
                f"{provider.name}: {model or 'default'}; context {context} "
                f"({source}); session {session}"
            )
        return lines
