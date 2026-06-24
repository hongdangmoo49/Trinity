"""Work package design detail modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Markdown, Static

from trinity.textual_app.snapshot import WorkPackageSnapshot


class WorkPackageDetailModal(ModalScreen[None]):
    """Show the full design and latest execution state for one work package."""

    DEFAULT_CSS = """
    WorkPackageDetailModal {
        align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, package: WorkPackageSnapshot) -> None:
        super().__init__()
        self.package = package

    def compose(self) -> ComposeResult:
        with Vertical(id="work-package-detail-modal"):
            yield Static(
                f"{self.package.id}: {self.package.title or self.package.topic}",
                id="work-package-detail-title",
            )
            with VerticalScroll(id="work-package-detail-body"):
                yield Markdown(self._markdown())
            yield Button("Close", id="close-work-package-detail")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "close-work-package-detail":
            return
        event.stop()
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)

    def _markdown(self) -> str:
        package = self.package
        lines = [
            "## Summary",
            f"- Status: `{package.status or 'pending'}`",
            f"- Owner: `{package.owner_agent or '-'}`",
            f"- Executor: `{package.current_executor or package.last_executor or '-'}`",
            f"- Review: `{package.review_status or '-'}`",
            f"- Risk: `{package.risk or 'unknown'}`",
            f"- Execution lane: `{self._execution_lane_label(package)}`",
            f"- Requires execution: `{'yes' if package.requires_execution else 'no'}`",
            f"- Retry: `{('available' if package.retryable else package.retry_disabled_reason or 'not available')}`",
        ]
        if package.repair_attempt_count or package.repair_blocked_reason:
            attempts = (
                f"{package.repair_attempt_count}/{package.repair_max_attempts}"
                if package.repair_max_attempts
                else str(package.repair_attempt_count)
            )
            lines.append(f"- Repair attempts: `{attempts}`")
        if package.repair_blocked_reason:
            lines.append(f"- Blocked reason: `{package.repair_blocked_reason}`")
        if package.task_kind or package.routing_reason:
            lines.extend(
                [
                    f"- Task kind: `{package.task_kind or '-'}`",
                    f"- Routing score: `{package.routing_score:.1f}`",
                    f"- Routing reason: {package.routing_reason or '(none)'}",
                    f"- Profile revision: `{package.profile_revision or '-'}`",
                ]
            )

        lines.extend(["", "## Result"])
        if package.last_result_status or package.last_result_summary:
            lines.extend(
                [
                    f"- Agent: `{package.last_result_agent or '-'}`",
                    f"- Status: `{package.last_result_status or '-'}`",
                    f"- Summary: {package.last_result_summary or '(none)'}",
                ]
            )
            self._append_list(lines, "Files Changed", package.last_result_files_changed)
            self._append_list(lines, "Blockers", package.last_result_blockers)
            self._append_list(
                lines,
                "Fallback Attempts",
                package.last_result_attempt_chain,
            )
        else:
            lines.append("(no execution result yet)")

        lines.extend(["", "## Review"])
        if package.review_status or package.review_summary:
            lines.extend(
                [
                    f"- Reviewer: `{package.reviewer_agent or '-'}`",
                    f"- Status: `{package.review_status or '-'}`",
                    f"- Severity: `{package.review_severity or '-'}`",
                    f"- Summary: {package.review_summary or '(none)'}",
                ]
            )
            self._append_list(
                lines,
                "Required Changes",
                package.review_required_changes,
            )
        else:
            lines.append("(no review recorded)")

        lines.extend(["", "## Spec", "### Objective", package.objective or "(none)"])
        self._append_list(lines, "Scope", package.scope)
        self._append_list(lines, "Out of Scope", package.out_of_scope)
        self._append_list(lines, "Dependencies", package.dependencies)
        self._append_list(lines, "Expected Files", package.expected_files)
        self._append_list(lines, "Acceptance Criteria", package.acceptance_criteria)
        self._append_list(lines, "Repair Notes", package.repair_notes)
        return "\n".join(lines)

    @staticmethod
    def _append_list(lines: list[str], title: str, values: list[str]) -> None:
        if not values:
            return
        lines.extend(["", f"## {title}"])
        lines.extend(f"- {value}" for value in values)

    @staticmethod
    def _execution_lane_label(package: WorkPackageSnapshot) -> str:
        if not package.parallelizable:
            return "serial"
        if package.parallel_group is not None:
            return f"g{package.parallel_group}"
        return "unspecified"
