"""Confirmation modal shown before starting Nexus execution."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import WorkflowNexusSnapshot, WorkPackageSnapshot


EXECUTION_CONFIRM_LABELS = {
    "en": {
        "body": "Review the target and work packages before agents write files.",
        "cancel": "Cancel",
        "confirm": "Confirm Execute",
        "executable": "executable",
        "instruction": "Instruction",
        "none": "(none)",
        "package_preview": "Preview",
        "project_context": "Project context",
        "project_mode": "Project mode",
        "providers": "Providers",
        "risk_none": "none",
        "risks": "Risks",
        "target_workspace": "Target workspace",
        "title": "Confirm Execution",
        "work_packages": "Work packages",
    },
    "ko": {
        "body": "에이전트가 파일을 쓰기 전에 대상과 작업 패키지를 확인하세요.",
        "cancel": "취소",
        "confirm": "실행 확인",
        "executable": "실행 가능",
        "instruction": "실행 지시",
        "none": "(없음)",
        "package_preview": "미리보기",
        "project_context": "프로젝트 컨텍스트",
        "project_mode": "프로젝트 모드",
        "providers": "프로바이더",
        "risk_none": "없음",
        "risks": "위험",
        "target_workspace": "대상 작업 폴더",
        "title": "실행 확인",
        "work_packages": "작업 패키지",
    },
}


@dataclass(frozen=True)
class ExecutionConfirmationSummary:
    """Compact execution context shown before starting agents."""

    target_workspace: str
    project_mode: str
    context_items: tuple[str, ...]
    providers: tuple[str, ...]
    total_packages: int
    executable_packages: int
    package_preview: tuple[str, ...]
    risk_items: tuple[str, ...] = ()
    instruction: str = ""

    @property
    def has_work_packages(self) -> bool:
        return self.total_packages > 0

    @property
    def has_executable_packages(self) -> bool:
        return self.executable_packages > 0


class ExecutionConfirmModal(ModalScreen[bool]):
    """Ask for explicit confirmation before starting workflow execution."""

    DEFAULT_CSS = """
    ExecutionConfirmModal {
        align: center middle;
    }

    #execution-confirm-modal {
        width: 86;
        max-width: 94%;
        height: auto;
        max-height: 86%;
        border: round $primary;
        padding: 1 2;
        background: $surface;
    }

    #execution-confirm-title {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    #execution-confirm-body {
        margin-bottom: 1;
    }

    #execution-confirm-summary {
        color: $text-muted;
        margin-bottom: 1;
    }

    #execution-confirm-preview {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
    }

    #execution-confirm-actions {
        align-horizontal: right;
        height: auto;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "confirm", "Confirm"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "cancel"): ("binding_cancel", None),
        ("ctrl+enter", "confirm"): ("binding_execute", None),
    }

    def __init__(
        self,
        summary: ExecutionConfirmationSummary,
        *,
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.summary = summary
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="execution-confirm-modal"):
            yield Static(self._label("title"), id="execution-confirm-title")
            yield Static(self._label("body"), id="execution-confirm-body")
            yield Static(self._summary_text(), id="execution-confirm-summary")
            with VerticalScroll(id="execution-confirm-preview"):
                yield Static(self._preview_text(), id="execution-confirm-preview-text")
            with Horizontal(id="execution-confirm-actions"):
                yield Button(self._label("cancel"), id="cancel-execution-confirm")
                yield Button(
                    self._label("confirm"),
                    id="confirm-execution",
                    variant="primary",
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-execution":
            event.stop()
            self.dismiss(True)
        elif event.button.id == "cancel-execution-confirm":
            event.stop()
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def _summary_text(self) -> str:
        summary = self.summary
        lines = [
            f"{self._label('target_workspace')}: {summary.target_workspace or self._label('none')}",
            f"{self._label('project_mode')}: {summary.project_mode or self._label('none')}",
            (
                f"{self._label('project_context')}: "
                f"{_join_or_none(summary.context_items, self._label('none'))}"
            ),
            f"{self._label('providers')}: {_join_or_none(summary.providers, self._label('none'))}",
            (
                f"{self._label('work_packages')}: {summary.total_packages} total, "
                f"{summary.executable_packages} {self._label('executable')}"
            ),
            (
                f"{self._label('risks')}: "
                f"{_join_or_none(summary.risk_items, self._label('risk_none'))}"
            ),
        ]
        if summary.instruction.strip():
            lines.append(
                f"{self._label('instruction')}: {summary.instruction.strip()}"
            )
        return "\n".join(lines)

    def _preview_text(self) -> str:
        preview = self.summary.package_preview
        if not preview:
            return f"{self._label('package_preview')}: {self._label('none')}"
        lines = [f"{self._label('package_preview')}:"]
        lines.extend(f"- {line}" for line in preview)
        return "\n".join(lines)

    def _label(self, key: str) -> str:
        labels = EXECUTION_CONFIRM_LABELS.get(
            self.lang,
            EXECUTION_CONFIRM_LABELS["en"],
        )
        return labels.get(key, EXECUTION_CONFIRM_LABELS["en"][key])


def execution_confirmation_summary(
    snapshot: WorkflowNexusSnapshot,
    *,
    project_mode: str = "",
    context_items: tuple[str, ...] | list[str] = (),
    selected_agents: tuple[str, ...] | list[str] = (),
    instruction: str = "",
    risk_items: tuple[str, ...] | list[str] = (),
    preview_limit: int = 4,
) -> ExecutionConfirmationSummary:
    """Build a display-only summary for the execution confirmation modal."""
    providers = _summary_providers(snapshot, tuple(selected_agents))
    package_preview = _package_preview(snapshot, preview_limit=preview_limit)
    total_packages = _total_package_count(snapshot)
    executable_packages = _executable_package_count(snapshot)
    return ExecutionConfirmationSummary(
        target_workspace=str(snapshot.target_workspace or "").strip(),
        project_mode=project_mode.strip(),
        context_items=tuple(item.strip() for item in context_items if item.strip()),
        providers=providers,
        total_packages=total_packages,
        executable_packages=executable_packages,
        package_preview=package_preview,
        risk_items=tuple(item.strip() for item in risk_items if item.strip()),
        instruction=instruction.strip(),
    )


def _summary_providers(
    snapshot: WorkflowNexusSnapshot,
    selected_agents: tuple[str, ...],
) -> tuple[str, ...]:
    selected = tuple(agent for agent in selected_agents if agent.strip())
    if selected:
        return selected
    enabled = tuple(provider.name for provider in snapshot.providers if provider.enabled)
    if enabled:
        return enabled
    return tuple(provider.name for provider in snapshot.providers if provider.name)


def _total_package_count(snapshot: WorkflowNexusSnapshot) -> int:
    if snapshot.work_package_details:
        return len(snapshot.work_package_details)
    return len(snapshot.work_packages)


def _executable_package_count(snapshot: WorkflowNexusSnapshot) -> int:
    if snapshot.work_package_details:
        return sum(
            1 for package in snapshot.work_package_details if package.requires_execution
        )
    return len(snapshot.work_packages)


def _package_preview(
    snapshot: WorkflowNexusSnapshot,
    *,
    preview_limit: int,
) -> tuple[str, ...]:
    if snapshot.work_package_details:
        return tuple(
            _package_detail_line(package)
            for package in snapshot.work_package_details[:preview_limit]
        )
    return tuple(
        str(line).strip()
        for line in snapshot.work_packages[:preview_limit]
        if str(line).strip()
    )


def _package_detail_line(package: WorkPackageSnapshot) -> str:
    title = (
        package.title.strip()
        or package.topic.strip()
        or package.objective.strip()
        or package.id
    )
    owner = package.owner_agent.strip() or "-"
    return f"{package.id} {owner}: {title}"


def _join_or_none(values: tuple[str, ...], none_label: str) -> str:
    filtered = tuple(value for value in values if value.strip())
    if not filtered:
        return none_label
    return ", ".join(filtered)
