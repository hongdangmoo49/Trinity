"""Workflow side inspector widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot


class WorkflowInspector(Vertical):
    """Compact read-only workflow status side surface."""

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.snapshot = WorkflowNexusSnapshot()

    def compose(self) -> ComposeResult:
        yield Static("Workflow", classes="inspector-title")
        yield Static("", id="inspector-workflow")
        yield Static("Questions", classes="inspector-title")
        yield Static("", id="inspector-questions")
        yield Static("Decisions", classes="inspector-title")
        yield Static("", id="inspector-decisions")
        yield Static("Packages", classes="inspector-title")
        yield Static("", id="inspector-packages")
        yield Static("Execution Log", classes="inspector-title")
        yield Static("", id="inspector-log")

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self.query_one("#inspector-workflow", Static).update(
            "\n".join(
                [
                    f"ID: {snapshot.session_id or '(new)'}",
                    f"State: {snapshot.state}",
                    f"Round: {snapshot.round_num}",
                ]
            )
        )
        self.query_one("#inspector-questions", Static).update(
            self._list_or_empty([question.question for question in snapshot.questions])
        )
        self.query_one("#inspector-decisions", Static).update(
            self._list_or_empty(snapshot.decisions)
        )
        self.query_one("#inspector-packages", Static).update(
            self._list_or_empty(snapshot.work_packages)
        )
        self.query_one("#inspector-log", Static).update(
            self._list_or_empty(snapshot.execution_log[-5:])
        )

    @staticmethod
    def _list_or_empty(items: list[str]) -> str:
        if not items:
            return "(none)"
        return "\n".join(f"- {item}" for item in items[:5])
