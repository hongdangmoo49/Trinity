"""Execution Matrix screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, RichLog, Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.workspace_picker import WorkspacePreflight


class ExecutionMatrixScreen(Screen[None]):
    """Monitor work package execution and logs."""

    def __init__(self) -> None:
        super().__init__(name="execution")
        self.preflight: WorkspacePreflight | None = None
        self.snapshot = WorkflowNexusSnapshot()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="execution-screen"):
            yield Static(self._header_text(), id="execution-header")
            yield DataTable(id="execution-table", zebra_stripes=True)
            yield RichLog(id="execution-log", wrap=True, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._setup_table()
        self.apply_execution_state(self.preflight, self.snapshot)

    def apply_execution_state(
        self,
        preflight: WorkspacePreflight | None,
        snapshot: WorkflowNexusSnapshot,
    ) -> None:
        self.preflight = preflight
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self.query_one("#execution-header", Static).update(self._header_text())
        self._render_table()
        self._render_log()

    def append_log(self, line: str) -> None:
        if not self.is_mounted:
            return
        self.query_one("#execution-log", RichLog).write(line)

    def _setup_table(self) -> None:
        table = self.query_one("#execution-table", DataTable)
        if table.columns:
            return
        table.add_columns("Task", "Assignee", "Executor", "Status", "Risk")

    def _render_table(self) -> None:
        table = self.query_one("#execution-table", DataTable)
        table.clear()
        if self.snapshot.work_package_details:
            for package in self.snapshot.work_package_details:
                executor = package.current_executor or package.last_executor or "-"
                if (
                    executor not in {"", "-"}
                    and package.owner_agent
                    and executor != package.owner_agent
                ):
                    executor = f"{executor} (fallback)"
                table.add_row(
                    package.title or package.id,
                    package.owner_agent or "-",
                    executor,
                    package.status or "pending",
                    package.risk or "unknown",
                )
            return
        if not self.snapshot.work_packages:
            table.add_row("(no work packages)", "-", "-", "pending", "unknown")
            return
        for package in self.snapshot.work_packages:
            task, assignee, status = _parse_package_line(package)
            table.add_row(task, assignee, "-", status, "unknown")

    def _render_log(self) -> None:
        log = self.query_one("#execution-log", RichLog)
        log.clear()
        lines = self.snapshot.execution_log or ["Execution not started."]
        for line in lines:
            log.write(line)

    def _header_text(self) -> str:
        if self.preflight is None:
            return "Execution Matrix · workspace: not selected"
        return f"Execution Matrix · workspace: {self.preflight.path}"


def _parse_package_line(line: str) -> tuple[str, str, str]:
    """Parse the compact snapshot work package display line."""
    status = "pending"
    task = line
    if line.endswith(")") and "(" in line:
        task, raw_status = line.rsplit("(", 1)
        status = raw_status[:-1].strip() or status
        task = task.strip()
    assignee = "-"
    if ":" in task:
        owner, title = task.split(":", 1)
        assignee = owner.split()[-1] if owner.split() else "-"
        task = title.strip() or task
    return task, assignee, status
