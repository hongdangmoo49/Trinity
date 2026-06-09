"""Modal for selecting work packages to retry during execution."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Static

from trinity.textual_app.snapshot import WorkPackageSnapshot, WorkflowNexusSnapshot


@dataclass(frozen=True)
class ExecutionRetrySelection:
    """User-selected execution retry scope."""

    selector: str
    package_ids: tuple[str, ...]


class ExecutionRetryModal(ModalScreen[ExecutionRetrySelection | None]):
    """Centered retry picker for failed, blocked, or interrupted work packages."""

    DEFAULT_CSS = """
    ExecutionRetryModal {
        align: center middle;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    FILTERS = ("all", "failed", "blocked", "interrupted", "custom")

    def __init__(
        self,
        snapshot: WorkflowNexusSnapshot,
        *,
        selector: str = "all",
        package_ids: tuple[str, ...] = (),
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.snapshot = snapshot
        self.selector = selector if selector in self.FILTERS else "custom"
        self.lang = lang
        initial_ids = set(package_ids)
        if self.selector == "custom" and initial_ids:
            self.selected_ids = {
                package.id
                for package in self.snapshot.work_package_details
                if package.id in initial_ids and package.retryable
            }
        else:
            base_selector = "all" if self.selector == "custom" else self.selector
            self.selected_ids = set(self._ids_for_selector(base_selector))

    def compose(self) -> ComposeResult:
        with Vertical(id="execution-retry-modal"):
            yield Static("Execute Retry", id="execution-retry-title")
            yield Static(self._summary_text(), id="execution-retry-summary")
            with Horizontal(id="execution-retry-filters"):
                for filter_name in self.FILTERS:
                    yield Button(
                        filter_name.title(),
                        id=f"retry-filter-{filter_name}",
                        variant="primary" if filter_name == self.selector else "default",
                    )
            with VerticalScroll(id="execution-retry-list"):
                yield Static(self._header_text(), id="execution-retry-header")
                packages = self._display_packages()
                if not packages:
                    yield Static("No work packages match this retry filter.", classes="retry-row")
                for package in packages:
                    with Horizontal(classes="retry-row"):
                        if self.selector == "custom":
                            yield Checkbox(
                                "",
                                value=package.id in self.selected_ids,
                                name=package.id,
                                disabled=not package.retryable,
                                compact=True,
                            )
                        yield Static(package.id, classes="retry-cell retry-id")
                        yield Static(package.status or "pending", classes="retry-cell retry-status")
                        yield Static(
                            package.topic or package.title or package.id,
                            classes="retry-cell retry-topic",
                        )
                        yield Static(package.owner_agent or "-", classes="retry-cell retry-owner")
                        yield Static(_executor_label(package), classes="retry-cell retry-executor")
                        yield Static(
                            _retry_note(package),
                            classes="retry-cell retry-note",
                        )
            yield Static(self._selected_text(), id="execution-retry-selected")
            with Horizontal(id="execution-retry-actions"):
                yield Button("Cancel", id="cancel-execute-retry")
                yield Button(
                    "Retry selected",
                    id="confirm-execute-retry",
                    variant="primary",
                    disabled=not self._selected_package_ids(),
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("retry-filter-"):
            event.stop()
            self.selector = button_id.removeprefix("retry-filter-")
            self.selected_ids = set(self._ids_for_selector(self.selector))
            self.refresh(recompose=True)
            return
        if button_id == "cancel-execute-retry":
            event.stop()
            self.dismiss(None)
            return
        if button_id == "confirm-execute-retry":
            event.stop()
            selected = self._selected_package_ids()
            if selected:
                self.dismiss(
                    ExecutionRetrySelection(
                        selector=self.selector,
                        package_ids=selected,
                    )
                )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        package_id = str(event.checkbox.name or "")
        if not package_id:
            return
        event.stop()
        if event.value:
            self.selected_ids.add(package_id)
        else:
            self.selected_ids.discard(package_id)
        self._refresh_selection_state()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _display_packages(self) -> list[WorkPackageSnapshot]:
        packages = list(self.snapshot.work_package_details)
        if self.selector in {"all", "custom"}:
            return packages
        if self.selector == "interrupted":
            interrupted_ids = set(self.snapshot.execution_recovery.running_packages) if (
                self.snapshot.execution_recovery
            ) else set()
            return [
                package
                for package in packages
                if package.id in interrupted_ids or (
                    not interrupted_ids and package.status == "running"
                )
            ]
        return [package for package in packages if package.status == self.selector]

    def _ids_for_selector(self, selector: str) -> tuple[str, ...]:
        selected: list[str] = []
        for package in self.snapshot.work_package_details:
            if not package.retryable:
                continue
            if selector in {"all", "custom"}:
                selected.append(package.id)
            elif selector == "interrupted":
                recovery = self.snapshot.execution_recovery
                interrupted_ids = set(recovery.running_packages) if recovery else set()
                if package.id in interrupted_ids or (
                    not interrupted_ids and package.status == "running"
                ):
                    selected.append(package.id)
            elif package.status == selector:
                selected.append(package.id)
        return tuple(selected)

    def _selected_package_ids(self) -> tuple[str, ...]:
        allowed = {package.id for package in self.snapshot.work_package_details if package.retryable}
        ordered = [
            package.id
            for package in self.snapshot.work_package_details
            if package.id in self.selected_ids and package.id in allowed
        ]
        return tuple(ordered)

    def _refresh_selection_state(self) -> None:
        selected = self.query_one("#execution-retry-selected", Static)
        selected.update(self._selected_text())
        button = self.query_one("#confirm-execute-retry", Button)
        button.disabled = not self._selected_package_ids()

    def _summary_text(self) -> str:
        target = ""
        if self.snapshot.execution_recovery and self.snapshot.execution_recovery.target_workspace:
            target = self.snapshot.execution_recovery.target_workspace
        if not target:
            target = self.snapshot.target_workspace
        recovery = (
            self.snapshot.execution_recovery.state
            if self.snapshot.execution_recovery
            else "none"
        )
        return f"Recovery: {recovery}  Target: {target or '(not selected)'}"

    def _header_text(self) -> str:
        prefix = "Use  " if self.selector == "custom" else ""
        return f"{prefix}WP      Status     Topic                         Owner      Executor    Note"

    def _selected_text(self) -> str:
        selected = self._selected_package_ids()
        if selected:
            return f"Selected: {', '.join(selected)}"
        return "Selected: (none)"


def _executor_label(package: WorkPackageSnapshot) -> str:
    executor = package.current_executor or package.last_executor or "-"
    if executor not in {"", "-"} and package.owner_agent and executor != package.owner_agent:
        return f"{executor} fallback"
    return executor


def _retry_note(package: WorkPackageSnapshot) -> str:
    if not package.retryable:
        return package.retry_disabled_reason
    if package.repair_blocked_reason:
        return (
            f"repair {package.repair_attempt_count}/{package.repair_max_attempts}: "
            f"{package.repair_blocked_reason}"
        )
    if package.repair_attempt_count:
        return f"repair {package.repair_attempt_count}/{package.repair_max_attempts}"
    return ""
