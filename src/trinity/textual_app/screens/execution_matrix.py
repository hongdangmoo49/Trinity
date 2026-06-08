"""Execution Matrix screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.work_package_detail_modal import WorkPackageDetailModal
from trinity.textual_app.widgets.workspace_picker import WorkspacePreflight


class ExecutionPackageRow(Horizontal):
    """One work package row with a detail button."""

    def __init__(
        self,
        *,
        package_id: str,
        task: str,
        assignee: str,
        executor: str,
        status: str,
        review_status: str,
        risk: str,
        button_id: str,
        task_width: int,
        detail_enabled: bool = True,
    ) -> None:
        super().__init__(classes="execution-package-row")
        self.package_id = package_id
        self.task_label = task
        self.assignee = assignee
        self.executor = executor
        self.status = status
        self.review_status = review_status
        self.risk = risk
        self.button_id = button_id
        self.task_width = task_width
        self.detail_enabled = detail_enabled

    def compose(self) -> ComposeResult:
        yield Static(
            _clip(self.task_label, self.task_width),
            classes="execution-package-task",
        )
        yield Static(_clip(self.assignee, 11), classes="execution-package-assignee")
        yield Static(_clip(self.executor, 18), classes="execution-package-executor")
        yield Static(_clip(self.status, 10), classes="execution-package-status")
        yield Static(_clip(self.review_status or "-", 9), classes="execution-package-review")
        yield Static(_clip(self.risk, 9), classes="execution-package-risk")
        yield Button(
            "Spec",
            id=self.button_id,
            name=self.package_id,
            disabled=not self.detail_enabled,
            compact=True,
            classes="execution-package-spec",
        )


class ExecutionPackageHeader(Horizontal):
    """Column header aligned to the same CSS grid as package rows."""

    def __init__(self) -> None:
        super().__init__(classes="execution-package-header")

    def compose(self) -> ComposeResult:
        yield Static("Task", classes="execution-package-task")
        yield Static("Assignee", classes="execution-package-assignee")
        yield Static("Executor", classes="execution-package-executor")
        yield Static("Status", classes="execution-package-status")
        yield Static("Review", classes="execution-package-review")
        yield Static("Risk", classes="execution-package-risk")
        yield Static("Spec", classes="execution-package-spec")


class ExecutionMatrixScreen(Screen[None]):
    """Monitor work package execution and logs."""

    BINDINGS = [
        Binding("f", "toggle_task_expanded", "Expand Tasks"),
    ]

    def __init__(self) -> None:
        super().__init__(name="execution")
        self.preflight: WorkspacePreflight | None = None
        self.snapshot = WorkflowNexusSnapshot()
        self.tasks_expanded = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="execution-screen"):
            with Horizontal(id="execution-header-row"):
                yield Static(self._header_text(), id="execution-header")
                yield Button(
                    self._task_toggle_label(),
                    id="toggle-task-expanded",
                    compact=True,
                )
            yield VerticalScroll(id="execution-package-list")
            yield RichLog(id="execution-log", wrap=True, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._sync_task_expanded_view()
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
        self.query_one("#toggle-task-expanded", Button).label = self._task_toggle_label()
        self._sync_task_expanded_view()
        self._render_package_list()
        self._render_log()

    def append_log(self, line: str) -> None:
        if not self.is_mounted:
            return
        self.query_one("#execution-log", RichLog).write(line)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "toggle-task-expanded":
            event.stop()
            self.action_toggle_task_expanded()
            return
        if not event.button.id or not event.button.id.startswith("wp-detail-"):
            return
        event.stop()
        package_id = str(event.button.name or "")
        package = next(
            (
                item
                for item in self.snapshot.work_package_details
                if item.id == package_id
            ),
            None,
        )
        if package is not None:
            self.app.push_screen(WorkPackageDetailModal(package))

    def action_toggle_task_expanded(self) -> None:
        """Toggle the package list between compact and expanded task view."""
        self.tasks_expanded = not self.tasks_expanded
        if not self.is_mounted:
            return
        self.query_one("#toggle-task-expanded", Button).label = self._task_toggle_label()
        self._sync_task_expanded_view()
        self._render_package_list()

    def _sync_task_expanded_view(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#execution-screen", Vertical).set_class(
            self.tasks_expanded,
            "execution-task-expanded",
        )

    def _render_package_list(self) -> None:
        package_list = self.query_one("#execution-package-list", VerticalScroll)
        package_list.remove_children()
        package_list.mount(ExecutionPackageHeader())
        if self.snapshot.work_package_details:
            for index, package in enumerate(self.snapshot.work_package_details):
                package_list.mount(
                    self._package_row(
                        package_id=package.id,
                        task=package.title or package.topic or package.id,
                        assignee=package.owner_agent or "-",
                        executor=_executor_label(
                            package.current_executor,
                            package.last_executor,
                            package.owner_agent,
                        ),
                        status=package.status or "pending",
                        review_status=package.review_status,
                        risk=package.risk or "unknown",
                        button_id=f"wp-detail-{index}",
                        task_width=self._task_clip_width(),
                    )
                )
            return
        if not self.snapshot.work_packages:
            package_list.mount(
                Static("(no work packages)", classes="execution-package-empty")
            )
            return
        for index, package in enumerate(self.snapshot.work_packages):
            task, assignee, status = _parse_package_line(package)
            package_list.mount(
                self._package_row(
                    package_id=task,
                    task=task,
                    assignee=assignee,
                    executor="-",
                    status=status,
                    review_status="-",
                    risk="unknown",
                    button_id=f"wp-detail-legacy-{index}",
                    task_width=self._task_clip_width(),
                    detail_enabled=False,
                )
            )

    @staticmethod
    def _package_row(
        *,
        package_id: str,
        task: str,
        assignee: str,
        executor: str,
        status: str,
        review_status: str,
        risk: str,
        button_id: str,
        task_width: int,
        detail_enabled: bool = True,
    ) -> ExecutionPackageRow:
        return ExecutionPackageRow(
            package_id=package_id,
            task=task,
            assignee=assignee,
            executor=executor,
            status=status,
            review_status=review_status,
            risk=risk,
            button_id=button_id,
            task_width=task_width,
            detail_enabled=detail_enabled,
        )

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

    def _task_toggle_label(self) -> str:
        return "Compact Tasks" if self.tasks_expanded else "Expand Tasks"

    def _task_clip_width(self) -> int:
        return 72 if self.tasks_expanded else 28


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


def _executor_label(current: str, last: str, owner: str) -> str:
    executor = current or last or "-"
    if executor not in {"", "-"} and owner and executor != owner:
        return f"{executor} fallback"
    return executor


def _clip(value: str, width: int) -> str:
    clean = " ".join(str(value).split())
    if len(clean) <= width:
        return clean
    if width <= 3:
        return clean[:width]
    return clean[: width - 3] + "..."
