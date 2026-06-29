"""Confirmation modal for starting a new-project generation plan."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from trinity.project_intake import ProjectIntake
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.workspace_labels import (
    format_project_generation_preview_label,
    format_project_validation_plan_label,
)


PROJECT_GENERATION_CONFIRM_LABELS = {
    "en": {
        "body": "Review the first generated shape before Trinity starts planning.",
        "cancel": "Cancel",
        "confirm": "Confirm Plan",
        "generation_preview": "Generation preview",
        "none": "(none)",
        "target_workspace": "Target workspace",
        "title": "Confirm New Project",
        "validation_plan": "Validation plan",
    },
    "ko": {
        "body": "Trinity가 계획을 시작하기 전에 첫 생성 형태를 확인하세요.",
        "cancel": "취소",
        "confirm": "계획 확인",
        "generation_preview": "생성 미리보기",
        "none": "(없음)",
        "target_workspace": "대상 작업 폴더",
        "title": "새 프로젝트 확인",
        "validation_plan": "검증 계획",
    },
}


@dataclass(frozen=True)
class ProjectGenerationConfirmationSummary:
    """Display values for a new-project generation confirmation."""

    target_workspace: str
    generation_preview: str
    validation_plan: str

    @property
    def available(self) -> bool:
        return bool(self.target_workspace and self.generation_preview)


class ProjectGenerationConfirmModal(ModalScreen[bool]):
    """Ask before starting a workflow from a complete new-project brief."""

    DEFAULT_CSS = """
    ProjectGenerationConfirmModal {
        align: center middle;
    }

    #project-generation-confirm-modal {
        width: 88;
        max-width: 94%;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #project-generation-confirm-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    #project-generation-confirm-body {
        margin-bottom: 1;
    }

    #project-generation-confirm-summary {
        color: $text-muted;
        margin-bottom: 1;
    }

    #project-generation-confirm-actions {
        height: auto;
        align-horizontal: right;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+enter", "confirm", "Confirm"),
    ]

    LOCALIZED_BINDINGS = {
        ("escape", "cancel"): ("binding_cancel", None),
        ("ctrl+enter", "confirm"): ("binding_plan", None),
    }

    def __init__(
        self,
        summary: ProjectGenerationConfirmationSummary,
        *,
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.summary = summary
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        with Vertical(id="project-generation-confirm-modal"):
            yield Static(
                self._label("title"),
                id="project-generation-confirm-title",
            )
            yield Static(
                self._label("body"),
                id="project-generation-confirm-body",
            )
            yield Static(
                self._summary_text(),
                id="project-generation-confirm-summary",
            )
            with Horizontal(id="project-generation-confirm-actions"):
                yield Button(
                    self._label("cancel"),
                    id="cancel-project-generation-confirm",
                )
                yield Button(
                    self._label("confirm"),
                    id="confirm-project-generation",
                    variant="primary",
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-project-generation":
            event.stop()
            self.dismiss(True)
        elif event.button.id == "cancel-project-generation-confirm":
            event.stop()
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def _summary_text(self) -> str:
        summary = self.summary
        lines = [
            (
                f"{self._label('target_workspace')}: "
                f"{summary.target_workspace or self._label('none')}"
            ),
            summary.generation_preview
            or f"{self._label('generation_preview')}: {self._label('none')}",
            summary.validation_plan
            or f"{self._label('validation_plan')}: {self._label('none')}",
        ]
        return "\n".join(line for line in lines if line.strip())

    def _label(self, key: str) -> str:
        labels = PROJECT_GENERATION_CONFIRM_LABELS.get(
            self.lang,
            PROJECT_GENERATION_CONFIRM_LABELS["en"],
        )
        return labels.get(key, PROJECT_GENERATION_CONFIRM_LABELS["en"][key])


def project_generation_confirmation_summary(
    intake: ProjectIntake,
    *,
    lang: str = "en",
) -> ProjectGenerationConfirmationSummary:
    """Build a confirmation summary from saved new-project intake."""
    target = str(intake.target_workspace)
    return ProjectGenerationConfirmationSummary(
        target_workspace=target,
        generation_preview=format_project_generation_preview_label(
            intake,
            lang=lang,
            target_workspace=intake.target_workspace,
        ),
        validation_plan=format_project_validation_plan_label(
            intake,
            lang=lang,
            target_workspace=intake.target_workspace,
        ),
    )
