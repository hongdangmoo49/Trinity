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
    next_work_packages,
    progress_bar,
    progress_summary_line,
    work_package_counts,
    work_package_state,
)


class WorkflowInspector(Vertical):
    """Compact read-only workflow status side surface."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.snapshot = WorkflowNexusSnapshot()

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
        self.query_one("#inspector-progress", Static).update(
            self._progress_summary(snapshot)
        )
        self.query_one("#inspector-current", Static).update(
            self._list_or_empty(
                [
                    compact_wp_line(package)
                    for package in current_work_packages(snapshot.work_package_details)
                ]
            )
        )
        next_packages = next_work_packages(snapshot.work_package_details, limit=3)
        next_lines = [compact_wp_line(package) for package in next_packages]
        waiting_count = len(
            [
                package
                for package in snapshot.work_package_details
                if work_package_state(package) == "waiting"
            ]
        )
        if waiting_count > len(next_packages):
            next_lines.append(f"+{waiting_count - len(next_packages)} more")
        self.query_one("#inspector-next", Static).update(
            self._list_or_empty(next_lines)
        )
        self.query_one("#inspector-blocked", Static).update(
            self._list_or_empty(self._blocked_lines(snapshot))
        )
        self.query_one("#inspector-workflow", Static).update(
            "\n".join(
                [
                    f"ID: {snapshot.session_id or '(new)'}",
                    f"State: {snapshot.state}",
                    f"Round: {snapshot.round_num}",
                ]
            )
        )
        self.query_one("#inspector-providers", Static).update(
            self._list_or_empty(self._provider_lines(snapshot))
        )
        self.query_one("#inspector-questions", Static).update(
            self._list_or_empty([question.question for question in snapshot.questions])
        )
        self.query_one("#inspector-decisions", Static).update(
            self._list_or_empty(snapshot.decisions)
        )
        self.query_one("#inspector-post-review", Static).update(
            self._list_or_empty(
                [
                    f"{item.id} [{item.severity}/{item.status}] {item.title or item.summary}"
                    for item in snapshot.post_review_items
                ]
            )
        )
        self.query_one("#inspector-log", Static).update(
            self._list_or_empty(snapshot.execution_log[-5:])
        )

    @staticmethod
    def _list_or_empty(items: list[str]) -> str:
        if not items:
            return "(none)"
        return "\n".join(f"- {item}" for item in items[:5])

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
