"""Execution Matrix screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Static

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.status_label import compact_status_label
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
        with Vertical(classes="execution-package-lines"):
            with Horizontal(classes="execution-package-primary"):
                yield Static(
                    _clip(f"{self.package_id} {self.task_label}", self.task_width),
                    classes="execution-package-task",
                )
                yield Static(_clip(self.executor, 18), classes="execution-package-executor")
                yield Static(_clip(self.status, 10), classes="execution-package-status")
            with Horizontal(classes="execution-package-secondary"):
                yield Static(
                    _clip(f"owner: {self.assignee}", 18),
                    classes="execution-package-assignee",
                )
                yield Static(
                    _clip(f"review: {self.review_status or '-'}", 18),
                    classes="execution-package-review",
                )
                yield Static(
                    _clip(f"risk: {self.risk}", 14),
                    classes="execution-package-risk",
                )
                yield Button(
                    "Spec",
                    id=self.button_id,
                    name=self.package_id,
                    disabled=not self.detail_enabled,
                    compact=True,
                    classes="execution-package-spec",
                )


class ExecutionPackageHeader(Vertical):
    """Column header aligned to the same CSS grid as package rows."""

    def __init__(self) -> None:
        super().__init__(classes="execution-package-header")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="execution-package-primary"):
            yield Static("Package / Task", classes="execution-package-task")
            yield Static("Executor", classes="execution-package-executor")
            yield Static("Status", classes="execution-package-status")
        with Horizontal(classes="execution-package-secondary"):
            yield Static("Owner", classes="execution-package-assignee")
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
            yield Static("", id="execution-summary")
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
        self.query_one("#execution-summary", Static).update(self._summary_text())
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
                        status=compact_status_label(package.status or "pending"),
                        review_status=_review_label(package),
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
                    status=compact_status_label(status),
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
        lines = self._activity_lines()
        for line in lines:
            log.write(line)

    def _header_text(self) -> str:
        if self.preflight is None:
            return "Execution Matrix · workspace: not selected"
        return f"Execution Matrix · workspace: {self.preflight.path}"

    def _summary_text(self) -> str:
        packages = self.snapshot.work_package_details
        counts = {"RUN": 0, "WAIT": 0, "DONE": 0, "ISSUE": 0, "REVIEW": 0}
        for package in packages:
            label = compact_status_label(package.status or "pending")
            if label == "RUN":
                counts["RUN"] += 1
            elif label == "DONE":
                counts["DONE"] += 1
            elif label == "ISSUE":
                counts["ISSUE"] += 1
            elif (package.status or "") == "needs_review" or package.review_status:
                counts["REVIEW"] += 1
            else:
                counts["WAIT"] += 1

        retry_count = sum(1 for package in packages if package.retryable)
        recovery = self.snapshot.execution_recovery
        if recovery is not None:
            retry_count = max(retry_count, len(recovery.retry_candidates))
        target = (
            str(self.preflight.path)
            if self.preflight is not None
            else self.snapshot.target_workspace
            or (recovery.target_workspace if recovery is not None else "")
        )
        run = (
            recovery.run_id
            if recovery is not None and recovery.run_id
            else self.snapshot.session_id
            or "-"
        )
        state = (
            recovery.state
            if recovery is not None and recovery.state
            else self.snapshot.state
            or "idle"
        )
        parts = [
            f"RUN {counts['RUN']}",
            f"REVIEW {counts['REVIEW']}",
            f"WAIT {counts['WAIT']}",
            f"DONE {counts['DONE']}",
            f"ISSUE {counts['ISSUE']}",
            f"retry {retry_count}",
            f"workflow {state}",
            f"run {run}",
        ]
        if target:
            parts.append(f"target: {_clip(target, 28)}")
        return " · ".join(parts)

    def _activity_lines(self) -> list[str]:
        source = list(self.snapshot.execution_log)
        if not source and self.snapshot.workflow_events:
            source = list(self.snapshot.workflow_events)
        if not source:
            return ["Activity", "Execution not started."]
        recent = source[-7:]
        lines = ["Activity"]
        if len(source) > len(recent):
            lines.append(f"... {len(source) - len(recent)} earlier log lines hidden")
        lines.extend(recent)
        return lines

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


def _review_label(package: object) -> str:
    status = str(getattr(package, "review_status", "") or "").strip()
    reviewer = str(getattr(package, "reviewer_agent", "") or "").strip()
    if not status:
        return "-"
    normalized = status.lower().replace("_", " ")
    labels = {
        "queued": "queued",
        "reviewing": "reviewing",
        "pending": "queued",
        "changes requested": "changes",
        "approved": "approved",
        "blocked": "issue",
        "failed": "issue",
        "skipped": "skip",
    }
    label = labels.get(normalized, normalized)
    if reviewer and label not in {"changes", "approved", "issue", "skip"}:
        return f"{_agent_short_label(reviewer)} {label}"
    return label


def _agent_short_label(agent: str) -> str:
    normalized = agent.strip().lower()
    aliases = {
        "antigravity": "agy",
        "claude": "claude",
        "codex": "codex",
    }
    return aliases.get(normalized, _clip(agent, 8))


def _clip(value: str, width: int) -> str:
    clean = " ".join(str(value).split())
    if len(clean) <= width:
        return clean
    if width <= 3:
        return clean[:width]
    return clean[: width - 3] + "..."
