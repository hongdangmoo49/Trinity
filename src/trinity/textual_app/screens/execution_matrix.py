"""Execution Matrix screen."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Static

from trinity.display_labels import display_risk_value
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.execution_log_modal import ExecutionLogModal
from trinity.textual_app.widgets.status_label import (
    compact_status_label,
    is_no_peer_review_skip,
)
from trinity.textual_app.widgets.work_package_detail_modal import WorkPackageDetailModal
from trinity.textual_app.widgets.workspace_picker import WorkspacePreflight

_EXECUTION_MATRIX_LABELS = {
    "ko": {
        "activity": "활동",
        "blocked": "차단됨",
        "compact_tasks": "작업 접기",
        "earlier_log_lines_hidden": "... 이전 로그 {count}줄 숨김",
        "execution_matrix": "실행 매트릭스",
        "execution_not_started": "실행이 시작되지 않았습니다.",
        "executor": "실행자",
        "expand_tasks": "작업 펼치기",
        "full_log": "전체 로그",
        "lane": "레인",
        "lanes": "레인",
        "no_work_packages": "(작업 패키지 없음)",
        "not_selected": "선택 안 됨",
        "owner": "소유자",
        "owner_prefix": "소유자",
        "package_task": "패키지 / 작업",
        "recent_log": "최근 로그",
        "retry": "재시도",
        "retry_action": "재시도",
        "retry_summary": "재시도",
        "run": "실행",
        "run_second_review_action": "2차실행",
        "review": "리뷰",
        "review_prefix": "리뷰",
        "risk_lane": "리스크/레인",
        "risk_prefix": "리스크",
        "serial_lane": "직렬",
        "serial_summary": "직렬",
        "second_review_action": "2차리뷰",
        "spec": "상세",
        "actions": "작업",
        "summary_done": "완료",
        "summary_issue": "문제",
        "summary_review": "리뷰",
        "summary_run": "실행중",
        "summary_wait": "대기",
        "status": "상태",
        "target": "대상",
        "unknown_risk": "알 수 없음",
        "workspace": "작업 폴더",
        "workflow": "워크플로우",
    },
    "en": {
        "activity": "Activity",
        "blocked": "Blocked",
        "compact_tasks": "Compact Tasks",
        "earlier_log_lines_hidden": "... {count} earlier log lines hidden",
        "execution_matrix": "Execution Matrix",
        "execution_not_started": "Execution not started.",
        "executor": "Executor",
        "expand_tasks": "Expand Tasks",
        "full_log": "Full Log",
        "lane": "Lane",
        "lanes": "lanes",
        "no_work_packages": "(no work packages)",
        "not_selected": "not selected",
        "owner": "Owner",
        "owner_prefix": "owner",
        "package_task": "Package / Task",
        "recent_log": "Recent Log",
        "retry": "Retry",
        "retry_action": "Retry",
        "retry_summary": "retry",
        "run": "run",
        "run_second_review_action": "Run 2nd",
        "review": "Review",
        "review_prefix": "review",
        "risk_lane": "Risk/Lane",
        "risk_prefix": "risk",
        "serial_lane": "Serial",
        "serial_summary": "serial",
        "second_review_action": "2nd Review",
        "spec": "Spec",
        "actions": "Actions",
        "summary_done": "DONE",
        "summary_issue": "ISSUE",
        "summary_review": "REVIEW",
        "summary_run": "RUN",
        "summary_wait": "WAIT",
        "status": "Status",
        "target": "target",
        "unknown_risk": "unknown",
        "workspace": "workspace",
        "workflow": "workflow",
    },
}


def _label(lang: str, key: str) -> str:
    labels = _EXECUTION_MATRIX_LABELS.get(lang, _EXECUTION_MATRIX_LABELS["en"])
    fallback = _EXECUTION_MATRIX_LABELS["en"]
    return labels.get(key, fallback.get(key, key))


@dataclass(frozen=True)
class _PackageRowProjection:
    """Rendered row values used to detect stable execution matrix updates."""

    identity: str
    package_id: str
    task: str
    assignee: str
    executor: str
    status: str
    review_status: str
    risk: str
    button_id: str
    button_label: str
    task_width: int
    lane_label: str = ""
    retry_button_id: str = ""
    retry_label: str = ""
    retry_enabled: bool = False
    review_button_id: str = ""
    review_label: str = ""
    review_enabled: bool = False
    detail_enabled: bool = True

    @property
    def render_key(self) -> tuple[object, ...]:
        return (
            self.package_id,
            self.task,
            self.assignee,
            self.executor,
            self.status,
            self.review_status,
            self.risk,
            self.button_id,
            self.button_label,
            self.task_width,
            self.lane_label,
            self.retry_button_id,
            self.retry_label,
            self.retry_enabled,
            self.review_button_id,
            self.review_label,
            self.review_enabled,
            self.detail_enabled,
        )


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
        button_label: str = "Spec",
        task_width: int,
        retry_button_id: str = "",
        retry_label: str = "Retry",
        retry_enabled: bool = False,
        review_button_id: str = "",
        review_label: str = "",
        review_enabled: bool = False,
        detail_enabled: bool = True,
        lang: str = "en",
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
        self.button_label = button_label
        self.task_width = task_width
        self.retry_button_id = retry_button_id
        self.retry_label = retry_label
        self.retry_enabled = retry_enabled
        self.review_button_id = review_button_id
        self.review_label = review_label
        self.review_enabled = review_enabled
        self.detail_enabled = detail_enabled
        self.lang = lang

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
                    _clip(f"{_label(self.lang, 'owner_prefix')}: {self.assignee}", 18),
                    classes="execution-package-assignee",
                )
                yield Static(
                    _clip(
                        f"{_label(self.lang, 'review_prefix')}: "
                        f"{self.review_status or '-'}",
                        18,
                    ),
                    classes="execution-package-review",
                )
                yield Static(
                    _clip(f"{_label(self.lang, 'risk_prefix')}: {self.risk}", 18),
                    classes="execution-package-risk",
                )
                with Horizontal(classes="execution-package-actions"):
                    yield Button(
                        self.button_label,
                        id=self.button_id,
                        name=self.package_id,
                        disabled=not self.detail_enabled,
                        compact=True,
                        classes="execution-package-spec",
                    )
                    if self.retry_enabled:
                        yield Button(
                            self.retry_label,
                            id=self.retry_button_id,
                            name=self.package_id,
                            compact=True,
                            classes="execution-package-retry",
                        )
                    if self.review_enabled:
                        yield Button(
                            self.review_label,
                            id=self.review_button_id,
                            name=self.package_id,
                            compact=True,
                            classes="execution-package-review-action",
                        )

    def update_projection(self, projection: _PackageRowProjection) -> None:
        """Update row labels without remounting the row widget."""
        self.package_id = projection.package_id
        self.task_label = projection.task
        self.assignee = projection.assignee
        self.executor = projection.executor
        self.status = projection.status
        self.review_status = projection.review_status
        self.risk = projection.risk
        self.button_id = projection.button_id
        self.button_label = projection.button_label
        self.task_width = projection.task_width
        self.retry_button_id = projection.retry_button_id
        self.retry_label = projection.retry_label
        self.retry_enabled = projection.retry_enabled
        self.review_button_id = projection.review_button_id
        self.review_label = projection.review_label
        self.review_enabled = projection.review_enabled
        self.detail_enabled = projection.detail_enabled

        self.query_one(".execution-package-task", Static).update(
            _clip(f"{self.package_id} {self.task_label}", self.task_width)
        )
        self.query_one(".execution-package-executor", Static).update(
            _clip(self.executor, 18)
        )
        self.query_one(".execution-package-status", Static).update(
            _clip(self.status, 10)
        )
        self.query_one(".execution-package-assignee", Static).update(
            _clip(f"{_label(self.lang, 'owner_prefix')}: {self.assignee}", 18)
        )
        self.query_one(".execution-package-review", Static).update(
            _clip(
                f"{_label(self.lang, 'review_prefix')}: "
                f"{self.review_status or '-'}",
                18,
            )
        )
        self.query_one(".execution-package-risk", Static).update(
            _clip(f"{_label(self.lang, 'risk_prefix')}: {self.risk}", 18)
        )
        detail_button = self.query_one(".execution-package-spec", Button)
        detail_button.label = self.button_label
        detail_button.disabled = not self.detail_enabled
        retry_buttons = list(self.query(".execution-package-retry"))
        if retry_buttons:
            retry_button = retry_buttons[0]
            if isinstance(retry_button, Button):
                retry_button.label = self.retry_label
        review_buttons = list(self.query(".execution-package-review-action"))
        if review_buttons:
            review_button = review_buttons[0]
            if isinstance(review_button, Button):
                review_button.label = self.review_label


class ExecutionPackageHeader(Vertical):
    """Column header aligned to the same CSS grid as package rows."""

    def __init__(self, *, lang: str = "en") -> None:
        super().__init__(classes="execution-package-header")
        self.lang = lang

    def compose(self) -> ComposeResult:
        with Horizontal(classes="execution-package-primary"):
            yield Static(self._label("package_task"), classes="execution-package-task")
            yield Static(self._label("executor"), classes="execution-package-executor")
            yield Static(self._label("status"), classes="execution-package-status")
        with Horizontal(classes="execution-package-secondary"):
            yield Static(self._label("owner"), classes="execution-package-assignee")
            yield Static(self._label("review"), classes="execution-package-review")
            yield Static(self._label("risk_lane"), classes="execution-package-risk")
            yield Static(self._label("actions"), classes="execution-package-actions")

    def _label(self, key: str) -> str:
        return _label(self.lang, key)


class ExecutionMatrixScreen(Screen[None]):
    """Monitor work package execution and logs."""

    class RetryRequested(Message):
        """Posted when the user wants to retry failed or blocked work packages."""

        def __init__(
            self,
            snapshot: WorkflowNexusSnapshot,
            *,
            selector: str = "all",
            package_ids: tuple[str, ...] = (),
        ) -> None:
            super().__init__()
            self.snapshot = snapshot
            self.selector = selector
            self.package_ids = tuple(package_ids)

    class ReviewRequested(Message):
        """Posted when the user wants to run pending WP review packages."""

        def __init__(
            self,
            snapshot: WorkflowNexusSnapshot,
            *,
            package_ids: tuple[str, ...] = (),
        ) -> None:
            super().__init__()
            self.snapshot = snapshot
            self.package_ids = tuple(package_ids)

    BINDINGS = [
        Binding("f", "toggle_task_expanded", "Expand Tasks"),
        Binding("l", "open_full_log", "Full Log"),
        Binding("r", "request_retry", "Retry"),
    ]

    LOCALIZED_BINDINGS = {
        ("f", "toggle_task_expanded"): ("binding_expand_tasks", None),
        ("l", "open_full_log"): ("binding_full_log", None),
        ("r", "request_retry"): ("binding_retry", None),
    }

    def __init__(self, *, lang: str = "en") -> None:
        super().__init__(name="execution")
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)
        self.preflight: WorkspacePreflight | None = None
        self.snapshot = WorkflowNexusSnapshot()
        self.tasks_expanded = False
        self._package_list_identity: tuple[str, ...] | None = None
        self._package_row_keys: dict[str, tuple[object, ...]] = {}
        self._package_rows: dict[str, ExecutionPackageRow] = {}
        self._activity_lines_key: tuple[str, ...] = ()

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
                yield Button(
                    self._activity_toggle_label(),
                    id="toggle-activity-expanded",
                    compact=True,
                )
                yield Button(
                    self._retry_button_label(),
                    id="execution-retry",
                    compact=True,
                    disabled=not self._has_retry_candidates(),
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
        self.query_one("#toggle-activity-expanded", Button).label = (
            self._activity_toggle_label()
        )
        retry_button = self.query_one("#execution-retry", Button)
        retry_button.label = self._retry_button_label()
        retry_button.disabled = not self._has_retry_candidates()
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
        if event.button.id == "toggle-activity-expanded":
            event.stop()
            self.action_open_full_log()
            return
        if event.button.id == "execution-retry":
            event.stop()
            self.action_request_retry()
            return
        if event.button.id and event.button.id.startswith("wp-retry-"):
            event.stop()
            package_id = str(event.button.name or "")
            if package_id:
                self.action_request_retry(
                    selector="custom",
                    package_ids=(package_id,),
                )
            return
        if event.button.id and event.button.id.startswith("wp-review-"):
            event.stop()
            package_id = str(event.button.name or "")
            if package_id:
                self.action_request_review(package_ids=(package_id,))
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
            self.app.push_screen(WorkPackageDetailModal(package, lang=self.lang))

    def action_toggle_task_expanded(self) -> None:
        """Toggle the package list between compact and expanded task view."""
        self.tasks_expanded = not self.tasks_expanded
        if not self.is_mounted:
            return
        self.query_one("#toggle-task-expanded", Button).label = self._task_toggle_label()
        self._sync_task_expanded_view()
        self._render_package_list()

    def action_open_full_log(self) -> None:
        """Open the full activity log while keeping the page feed compact."""
        if not self.is_mounted:
            return
        self.app.push_screen(
            ExecutionLogModal(self._full_activity_lines(), lang=self.lang)
        )

    def action_request_retry(
        self,
        *,
        selector: str = "all",
        package_ids: tuple[str, ...] = (),
    ) -> None:
        """Ask the app shell to open the execution retry modal."""
        if not self._has_retry_candidates():
            return
        self.post_message(
            self.RetryRequested(
                self.snapshot,
                selector=selector,
                package_ids=package_ids,
            )
        )

    def action_request_review(
        self,
        *,
        package_ids: tuple[str, ...] = (),
    ) -> None:
        """Ask the app shell to start pending review packages."""
        self.post_message(
            self.ReviewRequested(
                self.snapshot,
                package_ids=package_ids,
            )
        )

    def _sync_task_expanded_view(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#execution-screen", Vertical).set_class(
            self.tasks_expanded,
            "execution-task-expanded",
        )

    def _render_package_list(self) -> None:
        projections = self._package_row_projections()
        identity = tuple(
            (
                f"{projection.lane_label}|{projection.identity}|"
                f"retry:{projection.retry_enabled}|review:{projection.review_enabled}"
            )
            for projection in projections
        )
        if identity == self._package_list_identity:
            if not projections:
                return
            for projection in projections:
                if self._package_row_keys.get(projection.identity) == projection.render_key:
                    continue
                row = self._package_rows.get(projection.identity)
                if row is not None:
                    row.update_projection(projection)
                    self._package_row_keys[projection.identity] = projection.render_key
            return

        package_list = self.query_one("#execution-package-list", VerticalScroll)
        package_list.remove_children()
        self._package_rows = {}
        self._package_row_keys = {}
        package_list.mount(ExecutionPackageHeader(lang=self.lang))
        if not projections:
            package_list.mount(
                Static(
                    self._label("no_work_packages"),
                    classes="execution-package-empty",
                )
            )
            self._package_list_identity = ()
            return
        last_lane_label = ""
        for projection in projections:
            if projection.lane_label and projection.lane_label != last_lane_label:
                package_list.mount(
                    Static(projection.lane_label, classes="execution-lane-header")
                )
                last_lane_label = projection.lane_label
            elif not projection.lane_label:
                last_lane_label = ""
            row = self._package_row(projection)
            package_list.mount(row)
            self._package_rows[projection.identity] = row
            self._package_row_keys[projection.identity] = projection.render_key
        self._package_list_identity = identity

    def _package_row_projections(self) -> list[_PackageRowProjection]:
        task_width = self._task_clip_width()
        if self.snapshot.work_package_details:
            return [
                _PackageRowProjection(
                    identity=f"detail:{index}:{package.id}",
                    package_id=package.id,
                    task=package.title or package.topic or package.id,
                    assignee=package.owner_agent or "-",
                    executor=_executor_label(
                        package.current_executor,
                        package.last_executor,
                        package.owner_agent,
                        lang=self.lang,
                    ),
                    status=compact_status_label(package.status or "pending"),
                    review_status=_review_label(package, self.lang),
                    risk=_risk_lane_label(package, self.lang),
                    button_id=f"wp-detail-{index}",
                    button_label=_detail_button_label(package, self.lang),
                    task_width=task_width,
                    lane_label=_execution_lane_label(package, self.lang),
                    retry_button_id=f"wp-retry-{index}",
                    retry_label=self._label("retry_action"),
                    retry_enabled=bool(package.retryable),
                    review_button_id=f"wp-review-{index}",
                    review_label=self._label("run_second_review_action"),
                    review_enabled=_has_pending_second_review(package),
                )
                for index, package in enumerate(self.snapshot.work_package_details)
            ]

        projections: list[_PackageRowProjection] = []
        for index, package in enumerate(self.snapshot.work_packages):
            task, assignee, status = _parse_package_line(package)
            projections.append(
                _PackageRowProjection(
                    identity=f"legacy:{index}:{task}",
                    package_id=task,
                    task=task,
                    assignee=assignee,
                    executor="-",
                    status=compact_status_label(status),
                    review_status="-",
                    risk=_label(self.lang, "unknown_risk"),
                    button_id=f"wp-detail-legacy-{index}",
                    button_label=self._label("spec"),
                    task_width=task_width,
                    detail_enabled=False,
                )
            )
        return projections

    def _package_row(self, projection: _PackageRowProjection) -> ExecutionPackageRow:
        return ExecutionPackageRow(
            package_id=projection.package_id,
            task=projection.task,
            assignee=projection.assignee,
            executor=projection.executor,
            status=projection.status,
            review_status=projection.review_status,
            risk=projection.risk,
            button_id=projection.button_id,
            button_label=projection.button_label,
            task_width=projection.task_width,
            retry_button_id=projection.retry_button_id,
            retry_label=projection.retry_label,
            retry_enabled=projection.retry_enabled,
            review_button_id=projection.review_button_id,
            review_label=projection.review_label,
            review_enabled=projection.review_enabled,
            detail_enabled=projection.detail_enabled,
            lang=self.lang,
        )

    def _render_log(self) -> None:
        lines = self._activity_lines()
        lines_key = tuple(lines)
        if lines_key == self._activity_lines_key:
            return
        log = self.query_one("#execution-log", RichLog)
        log.clear()
        for line in lines:
            log.write(line)
        self._activity_lines_key = lines_key

    def _header_text(self) -> str:
        target = self._target_workspace_text()
        if not target:
            return (
                f"{self._label('execution_matrix')} · "
                f"{self._label('workspace')}: {self._label('not_selected')}"
            )
        return (
            f"{self._label('execution_matrix')} · "
            f"{self._label('workspace')}: {target}"
        )

    def _target_workspace_text(self) -> str:
        if self.preflight is not None:
            return str(self.preflight.path)
        if self.snapshot.target_workspace:
            return self.snapshot.target_workspace
        recovery = self.snapshot.execution_recovery
        if recovery is not None and recovery.target_workspace:
            return recovery.target_workspace
        return ""

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

        retry_count = self._retry_count()
        recovery = self.snapshot.execution_recovery
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
            f"{self._label('summary_run')} {counts['RUN']}",
            f"{self._label('summary_review')} {counts['REVIEW']}",
            f"{self._label('summary_wait')} {counts['WAIT']}",
            f"{self._label('summary_done')} {counts['DONE']}",
            f"{self._label('summary_issue')} {counts['ISSUE']}",
            *self._parallel_summary_parts(),
            f"{self._label('retry_summary')} {retry_count}",
            f"{self._label('workflow')} {state}",
            f"{self._label('run')} {run}",
        ]
        if target:
            parts.append(f"{self._label('target')}: {_clip(target, 28)}")
        return " · ".join(parts)

    def _activity_lines(self) -> list[str]:
        source = self._activity_source_lines()
        if not source:
            return [self._label("activity"), self._label("execution_not_started")]
        lines = [self._label("activity")]
        recent = source[-7:]
        if len(source) > len(recent):
            lines.append(
                self._label("earlier_log_lines_hidden").format(
                    count=len(source) - len(recent)
                )
            )
        lines.extend(recent)
        return lines

    def _activity_source_lines(self) -> list[str]:
        source = list(self.snapshot.execution_log)
        if not source and self.snapshot.workflow_events:
            source = list(self.snapshot.workflow_events)
        return source

    def _full_activity_lines(self) -> list[str]:
        return self._activity_source_lines()

    def _task_toggle_label(self) -> str:
        return (
            self._label("compact_tasks")
            if self.tasks_expanded
            else self._label("expand_tasks")
        )

    def _activity_toggle_label(self) -> str:
        return self._label("full_log")

    def _retry_button_label(self) -> str:
        retry_count = self._retry_count()
        label = self._label("retry")
        return f"{label} {retry_count}" if retry_count else label

    def _has_retry_candidates(self) -> bool:
        return self._retry_count() > 0

    def _retry_count(self) -> int:
        packages = self.snapshot.work_package_details
        retry_count = sum(1 for package in packages if package.retryable)
        recovery = self.snapshot.execution_recovery
        if recovery is not None:
            retry_count = max(retry_count, len(recovery.retry_candidates))
        return retry_count

    def _parallel_summary_parts(self) -> list[str]:
        packages = self.snapshot.work_package_details
        groups = {
            package.parallel_group
            for package in packages
            if package.parallelizable and package.parallel_group is not None
        }
        serial_count = sum(1 for package in packages if not package.parallelizable)
        parts: list[str] = []
        if groups:
            parts.append(f"{self._label('lanes')} {len(groups)}")
        if serial_count:
            parts.append(f"{self._label('serial_summary')} {serial_count}")
        return parts

    def _task_clip_width(self) -> int:
        return 72 if self.tasks_expanded else 28

    def _label(self, key: str) -> str:
        return _label(self.lang, key)


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


def _executor_label(current: str, last: str, owner: str, *, lang: str = "en") -> str:
    executor = current or last or "-"
    if executor not in {"", "-"} and owner and executor != owner:
        suffix = "폴백" if lang == "ko" else "fallback"
        return f"{executor} {suffix}"
    return executor


def _review_label(package: object, lang: str = "en") -> str:
    status = str(getattr(package, "review_status", "") or "").strip()
    reviewer = str(getattr(package, "reviewer_agent", "") or "").strip()
    if not status:
        return "-"
    normalized = status.lower().replace("_", " ")
    labels = _review_status_labels(lang)
    skipped_reason = (
        str(getattr(package, "review_skipped_reason", "") or "")
        or str(getattr(package, "skipped_reason", "") or "")
    )
    if normalized == "skipped" and is_no_peer_review_skip(
        reviewer_agent=reviewer,
        summary=str(getattr(package, "review_summary", "") or ""),
        skipped_reason=skipped_reason,
    ):
        return labels["no peer"]
    label = labels.get(normalized, normalized)
    standalone_labels = {
        labels["changes requested"],
        labels["approved"],
        labels["blocked"],
        labels["skipped"],
        labels["needs second review"],
    }
    if reviewer and label not in standalone_labels:
        return _reviewer_status_label(reviewer, label, lang=lang)
    return label


def _review_status_labels(lang: str) -> dict[str, str]:
    if lang == "ko":
        return {
            "queued": "대기",
            "reviewing": "검토",
            "pending": "대기",
            "changes requested": "변경요청",
            "approved": "승인",
            "blocked": "문제",
            "failed": "문제",
            "skipped": "생략",
            "needs second review": "2차필요",
            "no peer": "peer 없음",
        }
    return {
        "queued": "queued",
        "reviewing": "reviewing",
        "pending": "queued",
        "changes requested": "changes",
        "approved": "approved",
        "blocked": "issue",
        "failed": "issue",
        "skipped": "skip",
        "needs second review": "needs 2nd",
        "no peer": "no peer",
    }


def _reviewer_status_label(reviewer: str, label: str, *, lang: str = "en") -> str:
    reviewers = _reviewer_names(reviewer)
    if len(reviewers) > 1:
        if lang == "ko":
            return f"{len(reviewers)}명 {label}"
        if label == "reviewing":
            return f"{len(reviewers)}p review"
        return f"{len(reviewers)}p {label}"

    short = _agent_short_label(reviewers[0] if reviewers else reviewer)
    preferred = f"{short} {label}"
    if len(preferred) <= 10:
        return preferred
    if label in {"reviewing", "검토"}:
        compact = f"{short} rev"
        if len(compact) <= 10:
            return compact
    if label in {"queued", "대기"}:
        compact = f"{short} q"
        if len(compact) <= 10:
            return compact
    return _clip(preferred, 10)


def _risk_lane_label(package: object, lang: str = "en") -> str:
    risk = str(getattr(package, "risk", "") or "").strip()
    if not risk:
        risk = _label(lang, "unknown_risk")
    else:
        risk = display_risk_value(risk, lang=lang)
    if not bool(getattr(package, "parallelizable", True)):
        return f"{risk} {_label(lang, 'serial_summary')}"
    group = getattr(package, "parallel_group", None)
    if group is None:
        return risk
    return f"{risk} g{group}"


def _execution_lane_label(package: object, lang: str = "en") -> str:
    if not bool(getattr(package, "parallelizable", True)):
        return _label(lang, "serial_lane")
    group = getattr(package, "parallel_group", None)
    if group is None:
        return ""
    return f"{_label(lang, 'lane')} g{group}"


def _detail_button_label(package: object, lang: str = "en") -> str:
    status = str(getattr(package, "status", "") or "").strip().lower()
    review_status = str(getattr(package, "review_status", "") or "").strip().lower()
    blocked_reason = str(
        getattr(package, "repair_blocked_reason", "") or ""
    ).strip()
    if status == "blocked" or blocked_reason:
        return _label(lang, "blocked")
    if review_status == "needs_second_review":
        return _label(lang, "second_review_action")
    return _label(lang, "spec")


def _has_pending_second_review(package: object) -> bool:
    review_status = str(getattr(package, "review_status", "") or "").strip().lower()
    return review_status == "needs_second_review"


def _reviewer_names(reviewer: str) -> list[str]:
    names: list[str] = []
    for part in reviewer.split(","):
        name = part.strip()
        if name:
            names.append(name)
    return names or [reviewer.strip()]


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
