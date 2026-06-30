"""Modal for selecting work packages to retry during execution."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Static

from trinity.textual_app.snapshot import WorkPackageSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.widgets.status_label import (
    display_retry_disabled_reason,
    display_status_value,
)


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
            self.selected_ids = set(self.ids_for_selector(base_selector))
        self._selected_text_key = self.selected_text()
        self._confirm_disabled_key = not self.selected_package_ids()
        self._selected_widget: Static | None = None
        self._confirm_button: Button | None = None

    def compose(self) -> ComposeResult:
        self._reset_widget_cache()
        self._selected_text_key = self.selected_text()
        self._confirm_disabled_key = not self.selected_package_ids()
        with Vertical(id="execution-retry-modal"):
            yield Static(self._label("title"), id="execution-retry-title")
            yield Static(self.summary_text(), id="execution-retry-summary")
            with Horizontal(id="execution-retry-filters"):
                for filter_name in self.FILTERS:
                    yield Button(
                        self.filter_label(filter_name),
                        id=f"retry-filter-{filter_name}",
                        variant="primary" if filter_name == self.selector else "default",
                    )
            with VerticalScroll(id="execution-retry-list"):
                yield Static(self.header_text(), id="execution-retry-header")
                packages = self.display_packages()
                if not packages:
                    yield Static(self._label("empty"), classes="retry-row")
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
                        yield Static(
                            display_status_value(
                                package.status or "pending",
                                lang=self.lang,
                            ),
                            classes="retry-cell retry-status",
                        )
                        yield Static(
                            package.topic or package.title or package.id,
                            classes="retry-cell retry-topic",
                        )
                        yield Static(package.owner_agent or "-", classes="retry-cell retry-owner")
                        yield Static(
                            _executor_label(package, lang=self.lang),
                            classes="retry-cell retry-executor",
                        )
                        yield Static(
                            _retry_note(package, lang=self.lang),
                            classes="retry-cell retry-note",
                        )
            yield Static(self._selected_text_key, id="execution-retry-selected")
            with Horizontal(id="execution-retry-actions"):
                yield Button(self._label("cancel"), id="cancel-execute-retry")
                yield Button(
                    self._label("confirm"),
                    id="confirm-execute-retry",
                    variant="primary",
                    disabled=self._confirm_disabled_key,
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("retry-filter-"):
            event.stop()
            next_selector = button_id.removeprefix("retry-filter-")
            if next_selector == self.selector:
                return
            self.selector = next_selector
            self.selected_ids = set(self.ids_for_selector(self.selector))
            self.refresh(recompose=True)
            return
        if button_id == "cancel-execute-retry":
            event.stop()
            self.dismiss(None)
            return
        if button_id == "confirm-execute-retry":
            event.stop()
            selected = self.selected_package_ids()
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

    def display_packages(self) -> list[WorkPackageSnapshot]:
        packages = self._retry_candidate_packages()
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

    def _retry_candidate_packages(self) -> list[WorkPackageSnapshot]:
        return [
            package
            for package in self.snapshot.work_package_details
            if package.retryable
        ]

    def ids_for_selector(self, selector: str) -> tuple[str, ...]:
        selected: list[str] = []
        for package in self._retry_candidate_packages():
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

    def selected_package_ids(self) -> tuple[str, ...]:
        allowed = {package.id for package in self._retry_candidate_packages()}
        ordered = [
            package.id
            for package in self.snapshot.work_package_details
            if package.id in self.selected_ids and package.id in allowed
        ]
        return tuple(ordered)

    def _refresh_selection_state(self) -> None:
        selected_text = self.selected_text()
        if selected_text != self._selected_text_key:
            self._selected_summary_widget().update(selected_text)
            self._selected_text_key = selected_text
        disabled = not self.selected_package_ids()
        if disabled != self._confirm_disabled_key:
            self._confirm_retry_button().disabled = disabled
            self._confirm_disabled_key = disabled

    def _reset_widget_cache(self) -> None:
        self._selected_widget = None
        self._confirm_button = None

    def _selected_summary_widget(self) -> Static:
        if self._selected_widget is None:
            self._selected_widget = self.query_one("#execution-retry-selected", Static)
        return self._selected_widget

    def _confirm_retry_button(self) -> Button:
        if self._confirm_button is None:
            self._confirm_button = self.query_one("#confirm-execute-retry", Button)
        return self._confirm_button

    def summary_text(self) -> str:
        target = ""
        if self.snapshot.execution_recovery and self.snapshot.execution_recovery.target_workspace:
            target = self.snapshot.execution_recovery.target_workspace
        if not target:
            target = self.snapshot.target_workspace
        recovery_state = (
            self.snapshot.execution_recovery.state
            if self.snapshot.execution_recovery
            else ""
        )
        recovery = display_status_value(
            recovery_state,
            lang=self.lang,
            empty=self._label("none") if self.lang == "ko" else "none",
        )
        return (
            f"{self._label('recovery')}: {recovery}  "
            f"{self._label('target')}: {target or self._label('not_selected')}"
        )

    def header_text(self) -> str:
        if self.lang == "ko":
            prefix = "선택  " if self.selector == "custom" else ""
            return f"{prefix}작업 ID 상태       주제                          소유자       실행자       메모"
        prefix = "Use  " if self.selector == "custom" else ""
        return f"{prefix}WP      Status     Topic                         Owner      Executor    Note"

    def selected_text(self) -> str:
        selected = self.selected_package_ids()
        if selected:
            return f"{self._label('selected')}: {', '.join(selected)}"
        return f"{self._label('selected')}: {self._label('none')}"

    def filter_label(self, selector: str) -> str:
        labels = {
            "ko": {
                "all": "전체",
                "failed": "실패",
                "blocked": "막힘",
                "interrupted": "중단",
                "custom": "선택",
            },
            "en": {
                "all": "All",
                "failed": "Failed",
                "blocked": "Blocked",
                "interrupted": "Interrupted",
                "custom": "Custom",
            },
        }
        return labels.get(self.lang, labels["en"]).get(selector, selector.title())

    def _label(self, key: str) -> str:
        labels = {
            "ko": {
                "cancel": "취소",
                "confirm": "선택 항목 재시도",
                "empty": "이 재시도 필터에 맞는 작업 패키지가 없습니다.",
                "none": "(없음)",
                "not_selected": "(선택 안 됨)",
                "recovery": "복구",
                "selected": "선택됨",
                "target": "대상",
                "title": "실행 재시도",
            },
            "en": {
                "cancel": "Cancel",
                "confirm": "Retry selected",
                "empty": "No work packages match this retry filter.",
                "none": "(none)",
                "not_selected": "(not selected)",
                "recovery": "Recovery",
                "selected": "Selected",
                "target": "Target",
                "title": "Execute Retry",
            },
        }
        return labels.get(self.lang, labels["en"]).get(key, key)


def _executor_label(package: WorkPackageSnapshot, *, lang: str = "en") -> str:
    executor = package.current_executor or package.last_executor or "-"
    if executor not in {"", "-"} and package.owner_agent and executor != package.owner_agent:
        suffix = "대체" if lang == "ko" else "fallback"
        return f"{executor} {suffix}"
    return executor


def _retry_note(package: WorkPackageSnapshot, *, lang: str = "en") -> str:
    if not package.retryable:
        return display_retry_disabled_reason(package.retry_disabled_reason, lang=lang)
    repair = "복구" if lang == "ko" else "repair"
    if package.repair_blocked_reason:
        return (
            f"{repair} {package.repair_attempt_count}/{package.repair_max_attempts}: "
            f"{package.repair_blocked_reason}"
        )
    if package.repair_attempt_count:
        return f"{repair} {package.repair_attempt_count}/{package.repair_max_attempts}"
    return ""
