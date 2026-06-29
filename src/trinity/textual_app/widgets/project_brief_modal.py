"""Modal for editing project intake brief fields."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Static

from trinity.project_intake import ProjectIntake
from trinity.textual_app.workspace_labels import format_project_generation_preview_label


PROJECT_BRIEF_LABELS = {
    "en": {
        "cancel": "Cancel",
        "constraints": "Constraints",
        "constraints_placeholder": "offline-first, no paid APIs",
        "goal": "Product goal",
        "goal_placeholder": "e.g. Build a local habit tracker",
        "artifact_targets": "Artifact targets",
        "artifact_targets_placeholder": "apps/web, src/app, README.md",
        "milestone": "First milestone",
        "milestone_placeholder": "First shippable prototype",
        "notes": "Notes",
        "notes_placeholder": "Any context agents should consider",
        "project_type": "Project type",
        "project_type_placeholder": "SaaS dashboard, CLI tool, mobile app",
        "readiness_complete": "Minimum brief: complete",
        "readiness_missing": "Minimum brief: missing {fields}",
        "run_commands": "Run commands",
        "run_commands_placeholder": "npm run dev, uv run app",
        "save": "Save Brief",
        "selected_scope": "Selected scope",
        "selected_scope_placeholder": "apps/web, packages/core",
        "stack": "Stack preferences",
        "stack_placeholder": "python, textual, sqlite",
        "starter_profile": "Starter profile",
        "starter_profile_placeholder": "Textual TUI, Python CLI package, FastAPI service",
        "success": "Success criteria",
        "success_placeholder": "Users can finish the first workflow",
        "target_users": "Target users",
        "target_users_placeholder": "support operators, students, developers",
        "target_workspace": "Target workspace",
        "title": "Project Brief",
        "validation_commands": "Validation commands",
        "validation_commands_placeholder": "npm test, uv run pytest",
    },
    "ko": {
        "cancel": "취소",
        "constraints": "제약",
        "constraints_placeholder": "오프라인 우선, 유료 API 없음",
        "goal": "제품 목표",
        "goal_placeholder": "예: 로컬 습관 추적 앱 만들기",
        "artifact_targets": "산출물 위치",
        "artifact_targets_placeholder": "apps/web, src/app, README.md",
        "milestone": "첫 마일스톤",
        "milestone_placeholder": "처음 배포 가능한 프로토타입",
        "notes": "메모",
        "notes_placeholder": "에이전트가 고려할 추가 맥락",
        "project_type": "프로젝트 유형",
        "project_type_placeholder": "SaaS 대시보드, CLI 도구, 모바일 앱",
        "readiness_complete": "최소 브리프: 완료",
        "readiness_missing": "최소 브리프: 누락 {fields}",
        "run_commands": "실행 명령",
        "run_commands_placeholder": "npm run dev, uv run app",
        "save": "브리프 저장",
        "selected_scope": "선택 범위",
        "selected_scope_placeholder": "apps/web, packages/core",
        "stack": "선호 스택",
        "stack_placeholder": "python, textual, sqlite",
        "starter_profile": "스타터 프로필",
        "starter_profile_placeholder": "Textual TUI, Python CLI 패키지, FastAPI 서비스",
        "success": "성공 기준",
        "success_placeholder": "사용자가 첫 workflow를 끝낼 수 있음",
        "target_users": "대상 사용자",
        "target_users_placeholder": "지원 담당자, 학생, 개발자",
        "target_workspace": "대상 작업 경로",
        "title": "프로젝트 브리프",
        "validation_commands": "검증 명령",
        "validation_commands_placeholder": "npm test, uv run pytest",
    },
}


@dataclass(frozen=True)
class ProjectBriefDraft:
    """Editable user-provided project brief values."""

    product_goal: str = ""
    project_type: str = ""
    starter_profile: str = ""
    target_users: str = ""
    success_criteria: str = ""
    stack_preferences: tuple[str, ...] = ()
    first_milestone: str = ""
    run_commands: tuple[str, ...] = ()
    validation_commands: tuple[str, ...] = ()
    artifact_targets: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    selected_scope: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ProjectBriefModalResult:
    """Result of closing the project brief modal."""

    saved: bool
    draft: ProjectBriefDraft


class ProjectBriefModal(ModalScreen[ProjectBriefModalResult]):
    """Edit user-provided project intake brief fields."""

    DEFAULT_CSS = """
    ProjectBriefModal {
        align: center middle;
    }

    #project-brief-modal {
        width: 88;
        max-width: 94%;
        height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #project-brief-title {
        height: 1;
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    #project-brief-target {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    #project-brief-readiness {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    #project-brief-generation-preview {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    #project-brief-fields {
        height: 1fr;
    }

    .project-brief-row {
        height: 3;
        margin-bottom: 1;
    }

    .project-brief-row Static {
        width: 22;
        content-align: left middle;
        color: $text-muted;
    }

    .project-brief-row Input {
        width: 1fr;
    }

    #project-brief-actions {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        draft: ProjectBriefDraft | None = None,
        *,
        lang: str = "en",
        target_workspace: str = "",
        mode: str = "existing",
    ) -> None:
        super().__init__()
        self.draft = draft or ProjectBriefDraft()
        self.lang = lang
        self.target_workspace = target_workspace.strip()
        self.mode = mode

    def compose(self) -> ComposeResult:
        with Vertical(id="project-brief-modal"):
            yield Static(self._label("title"), id="project-brief-title")
            if self.target_workspace:
                yield Static(
                    f"{self._label('target_workspace')}: {self.target_workspace}",
                    id="project-brief-target",
                )
            if self.mode == "new":
                yield Static(
                    self._brief_readiness_label(self.draft),
                    id="project-brief-readiness",
                )
                yield Static(
                    self._generation_preview_label(self.draft),
                    id="project-brief-generation-preview",
                )
            with VerticalScroll(id="project-brief-fields"):
                yield from self._input_row(
                    "goal",
                    "project-brief-goal",
                    self.draft.product_goal,
                )
                yield from self._input_row(
                    "project_type",
                    "project-brief-project-type",
                    self.draft.project_type,
                )
                if self.mode == "new":
                    yield from self._input_row(
                        "starter_profile",
                        "project-brief-starter-profile",
                        self.draft.starter_profile,
                    )
                yield from self._input_row(
                    "target_users",
                    "project-brief-target-users",
                    self.draft.target_users,
                )
                yield from self._input_row(
                    "success",
                    "project-brief-success",
                    self.draft.success_criteria,
                )
                yield from self._input_row(
                    "stack",
                    "project-brief-stack",
                    _join_values(self.draft.stack_preferences),
                )
                yield from self._input_row(
                    "milestone",
                    "project-brief-milestone",
                    self.draft.first_milestone,
                )
                if self.mode == "new":
                    yield from self._input_row(
                        "run_commands",
                        "project-brief-run-commands",
                        _join_values(self.draft.run_commands),
                    )
                    yield from self._input_row(
                        "validation_commands",
                        "project-brief-validation-commands",
                        _join_values(self.draft.validation_commands),
                    )
                    yield from self._input_row(
                        "artifact_targets",
                        "project-brief-artifact-targets",
                        _join_values(self.draft.artifact_targets),
                    )
                yield from self._input_row(
                    "constraints",
                    "project-brief-constraints",
                    _join_values(self.draft.constraints),
                )
                if self.mode == "existing":
                    yield from self._input_row(
                        "selected_scope",
                        "project-brief-selected-scope",
                        self.draft.selected_scope,
                    )
                yield from self._input_row(
                    "notes",
                    "project-brief-notes",
                    self.draft.notes,
                )
            with Horizontal(id="project-brief-actions"):
                yield Button(self._label("cancel"), id="cancel-project-brief")
                yield Button(
                    self._label("save"),
                    id="save-project-brief",
                    variant="primary",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#project-brief-goal", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "cancel-project-brief":
            event.stop()
            self.action_cancel()
        elif button_id == "save-project-brief":
            event.stop()
            self.action_save()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.mode != "new":
            return
        if not event.input.id or not event.input.id.startswith("project-brief-"):
            return
        event.stop()
        self._refresh_brief_readiness()
        self._refresh_generation_preview()

    def action_cancel(self) -> None:
        self.dismiss(ProjectBriefModalResult(saved=False, draft=self._current_draft()))

    def action_save(self) -> None:
        self.dismiss(ProjectBriefModalResult(saved=True, draft=self._current_draft()))

    def _current_draft(self) -> ProjectBriefDraft:
        return ProjectBriefDraft(
            product_goal=self._input_value("#project-brief-goal"),
            project_type=self._input_value("#project-brief-project-type"),
            starter_profile=(
                self._input_value("#project-brief-starter-profile")
                if self.mode == "new"
                else self.draft.starter_profile
            ),
            target_users=self._input_value("#project-brief-target-users"),
            success_criteria=self._input_value("#project-brief-success"),
            stack_preferences=_split_values(self._input_value("#project-brief-stack")),
            first_milestone=self._input_value("#project-brief-milestone"),
            run_commands=(
                _split_values(self._input_value("#project-brief-run-commands"))
                if self.mode == "new"
                else self.draft.run_commands
            ),
            validation_commands=(
                _split_values(self._input_value("#project-brief-validation-commands"))
                if self.mode == "new"
                else self.draft.validation_commands
            ),
            artifact_targets=(
                _split_values(self._input_value("#project-brief-artifact-targets"))
                if self.mode == "new"
                else self.draft.artifact_targets
            ),
            constraints=_split_values(self._input_value("#project-brief-constraints")),
            selected_scope=(
                self._input_value("#project-brief-selected-scope")
                if self.mode == "existing"
                else self.draft.selected_scope
            ),
            notes=self._input_value("#project-brief-notes"),
        )

    def _input_row(
        self,
        label_key: str,
        input_id: str,
        value: str,
    ) -> ComposeResult:
        with Horizontal(classes="project-brief-row"):
            yield Static(self._label(label_key))
            yield Input(
                value=value,
                id=input_id,
                placeholder=self._label(f"{label_key}_placeholder"),
            )

    def _input_value(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def _label(self, key: str) -> str:
        labels = PROJECT_BRIEF_LABELS.get(self.lang, PROJECT_BRIEF_LABELS["en"])
        return labels.get(key, PROJECT_BRIEF_LABELS["en"][key])

    def _format(self, key: str, **values: object) -> str:
        return self._label(key).format(**values)

    def _refresh_brief_readiness(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#project-brief-readiness", Static).update(
            self._brief_readiness_label(self._current_draft())
        )

    def _refresh_generation_preview(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#project-brief-generation-preview", Static).update(
            self._generation_preview_label(self._current_draft())
        )

    def _brief_readiness_label(self, draft: ProjectBriefDraft) -> str:
        missing = [
            self._label(label_key)
            for label_key, value in (
                ("goal", draft.product_goal),
                ("project_type", draft.project_type),
                ("target_users", draft.target_users),
                ("success", draft.success_criteria),
                ("milestone", draft.first_milestone),
            )
            if not value.strip()
        ]
        if missing:
            return self._format("readiness_missing", fields=", ".join(missing))
        return self._label("readiness_complete")

    def _generation_preview_label(self, draft: ProjectBriefDraft) -> str:
        target = Path(self.target_workspace) if self.target_workspace else Path(".")
        intake = ProjectIntake(
            mode="new",
            target_workspace=target,
            created_at="",
            git_repo=False,
            branch="(none)",
            dirty_count=None,
            untracked_count=None,
            product_goal=draft.product_goal,
            project_type=draft.project_type,
            starter_profile=draft.starter_profile,
            target_users=draft.target_users,
            success_criteria=draft.success_criteria,
            stack_preferences=draft.stack_preferences,
            first_milestone=draft.first_milestone,
            run_commands=draft.run_commands,
            validation_commands=draft.validation_commands,
            artifact_targets=draft.artifact_targets,
            constraints=draft.constraints,
            notes=draft.notes,
        )
        return format_project_generation_preview_label(
            intake,
            lang=self.lang,
            target_workspace=target,
        )


def _split_values(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def _join_values(values: tuple[str, ...]) -> str:
    return ", ".join(values)
