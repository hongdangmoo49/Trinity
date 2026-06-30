"""Focused modal for recording project validation commands."""

from __future__ import annotations

from dataclasses import dataclass, replace

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Static

from trinity.project_intake import ProjectIntake
from trinity.textual_app.workspace_labels import format_project_validation_plan_label


PROJECT_VALIDATION_LABELS = {
    "en": {
        "body_existing": (
            "Record the command Trinity should treat as the required check before "
            "agents change this project."
        ),
        "body_new": (
            "Record the command Trinity should use to prove the first scaffold works."
        ),
        "build_commands": "Build commands",
        "build_commands_placeholder": "npm run build, uv build",
        "cancel": "Cancel",
        "mode": "Mode",
        "run_commands": "Run commands",
        "run_commands_placeholder": "npm run dev, uv run app",
        "save": "Save Validation",
        "target_workspace": "Target workspace",
        "test_commands": "Test commands",
        "test_commands_placeholder": "npm test, uv run pytest",
        "title": "Confirm Validation",
        "validation_commands": "Required validation",
        "validation_commands_placeholder": "npm test, uv run pytest",
        "validation_plan": "Validation plan",
    },
    "ko": {
        "body_existing": (
            "에이전트가 이 프로젝트를 변경하기 전에 필수 확인으로 볼 명령을 "
            "기록하세요."
        ),
        "body_new": "첫 스캐폴드가 동작하는지 증명할 검증 명령을 기록하세요.",
        "build_commands": "빌드 명령",
        "build_commands_placeholder": "npm run build, uv build",
        "cancel": "취소",
        "mode": "모드",
        "run_commands": "실행 명령",
        "run_commands_placeholder": "npm run dev, uv run app",
        "save": "검증 저장",
        "target_workspace": "대상 작업 경로",
        "test_commands": "테스트 명령",
        "test_commands_placeholder": "npm test, uv run pytest",
        "title": "검증 확인",
        "validation_commands": "필수 검증",
        "validation_commands_placeholder": "npm test, uv run pytest",
        "validation_plan": "검증 계획",
    },
}


@dataclass(frozen=True)
class ProjectValidationDraft:
    """Editable validation command values."""

    validation_commands: tuple[str, ...] = ()
    test_commands: tuple[str, ...] = ()
    build_commands: tuple[str, ...] = ()
    run_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectValidationModalResult:
    """Result of closing the validation modal."""

    saved: bool
    draft: ProjectValidationDraft


class ProjectValidationModal(ModalScreen[ProjectValidationModalResult]):
    """Let users confirm validation commands before planning or execution."""

    DEFAULT_CSS = """
    ProjectValidationModal {
        align: center middle;
    }

    #project-validation-modal {
        width: 86;
        max-width: 94%;
        height: 95%;
        max-height: 95%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #project-validation-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    #project-validation-body,
    #project-validation-target,
    #project-validation-plan {
        color: $text-muted;
        margin-bottom: 1;
    }

    #project-validation-content {
        height: 1fr;
        margin-bottom: 1;
    }

    .project-validation-row {
        height: 3;
        margin-bottom: 1;
    }

    .project-validation-row Static {
        width: 24;
        content-align: left middle;
        color: $text-muted;
    }

    .project-validation-row Input {
        width: 1fr;
    }

    #project-validation-actions {
        height: auto;
        align-horizontal: right;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        intake: ProjectIntake,
        *,
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.intake = intake
        self.lang = lang
        self.draft = ProjectValidationDraft(
            validation_commands=intake.validation_commands,
            test_commands=intake.test_commands,
            build_commands=intake.build_commands,
            run_commands=intake.run_commands,
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="project-validation-modal"):
            yield Static(self._label("title"), id="project-validation-title")
            with VerticalScroll(id="project-validation-content"):
                yield Static(self._body_text(), id="project-validation-body")
                yield Static(
                    (
                        f"{self._label('target_workspace')}: "
                        f"{self.intake.target_workspace}\n"
                        f"{self._label('mode')}: {self.intake.mode}"
                    ),
                    id="project-validation-target",
                )
                yield Static(
                    self._validation_plan_label(self.draft),
                    id="project-validation-plan",
                )
                yield from self._input_row(
                    "validation_commands",
                    "project-validation-required",
                    _join_values(self.draft.validation_commands),
                )
                if self.intake.mode == "new":
                    yield from self._input_row(
                        "run_commands",
                        "project-validation-run",
                        _join_values(self.draft.run_commands),
                    )
                else:
                    yield from self._input_row(
                        "test_commands",
                        "project-validation-tests",
                        _join_values(self.draft.test_commands),
                    )
                    yield from self._input_row(
                        "build_commands",
                        "project-validation-build",
                        _join_values(self.draft.build_commands),
                    )
            with Horizontal(id="project-validation-actions"):
                yield Button(self._label("cancel"), id="cancel-project-validation")
                yield Button(
                    self._label("save"),
                    id="save-project-validation",
                    variant="primary",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#project-validation-required", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "cancel-project-validation":
            event.stop()
            self.action_cancel()
        elif button_id == "save-project-validation":
            event.stop()
            self.action_save()

    def on_input_changed(self, event: Input.Changed) -> None:
        if not event.input.id or not event.input.id.startswith("project-validation-"):
            return
        event.stop()
        self._refresh_validation_plan()

    def action_cancel(self) -> None:
        self.dismiss(
            ProjectValidationModalResult(saved=False, draft=self._current_draft())
        )

    def action_save(self) -> None:
        self.dismiss(
            ProjectValidationModalResult(saved=True, draft=self._current_draft())
        )

    def _current_draft(self) -> ProjectValidationDraft:
        return ProjectValidationDraft(
            validation_commands=_split_values(
                self._input_value("#project-validation-required")
            ),
            test_commands=(
                _split_values(self._input_value("#project-validation-tests"))
                if self.intake.mode != "new"
                else self.draft.test_commands
            ),
            build_commands=(
                _split_values(self._input_value("#project-validation-build"))
                if self.intake.mode != "new"
                else self.draft.build_commands
            ),
            run_commands=(
                _split_values(self._input_value("#project-validation-run"))
                if self.intake.mode == "new"
                else self.draft.run_commands
            ),
        )

    def _input_row(
        self,
        label_key: str,
        input_id: str,
        value: str,
    ) -> ComposeResult:
        with Horizontal(classes="project-validation-row"):
            yield Static(self._label(label_key))
            yield Input(
                value=value,
                id=input_id,
                placeholder=self._label(f"{label_key}_placeholder"),
            )

    def _input_value(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def _label(self, key: str) -> str:
        labels = PROJECT_VALIDATION_LABELS.get(
            self.lang,
            PROJECT_VALIDATION_LABELS["en"],
        )
        return labels.get(key, PROJECT_VALIDATION_LABELS["en"][key])

    def _body_text(self) -> str:
        key = "body_new" if self.intake.mode == "new" else "body_existing"
        return self._label(key)

    def _refresh_validation_plan(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#project-validation-plan", Static).update(
            self._validation_plan_label(self._current_draft())
        )

    def _validation_plan_label(self, draft: ProjectValidationDraft) -> str:
        intake = replace(
            self.intake,
            validation_commands=draft.validation_commands,
            test_commands=draft.test_commands,
            build_commands=draft.build_commands,
            run_commands=draft.run_commands,
        )
        return format_project_validation_plan_label(
            intake,
            lang=self.lang,
            target_workspace=intake.target_workspace,
        )


def _split_values(value: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(part.strip() for part in value.split(",") if part.strip())
    )


def _join_values(values: tuple[str, ...]) -> str:
    return ", ".join(values)
