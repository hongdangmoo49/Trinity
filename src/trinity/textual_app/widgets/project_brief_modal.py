"""Modal for editing project intake brief fields."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Static


PROJECT_BRIEF_LABELS = {
    "en": {
        "cancel": "Cancel",
        "constraints": "Constraints",
        "constraints_placeholder": "offline-first, no paid APIs",
        "goal": "Product goal",
        "goal_placeholder": "e.g. Build a local habit tracker",
        "milestone": "First milestone",
        "milestone_placeholder": "First shippable prototype",
        "notes": "Notes",
        "notes_placeholder": "Any context agents should consider",
        "project_type": "Project type",
        "project_type_placeholder": "SaaS dashboard, CLI tool, mobile app",
        "save": "Save Brief",
        "stack": "Stack preferences",
        "stack_placeholder": "python, textual, sqlite",
        "success": "Success criteria",
        "success_placeholder": "Users can finish the first workflow",
        "target_users": "Target users",
        "target_users_placeholder": "support operators, students, developers",
        "title": "Project Brief",
    },
    "ko": {
        "cancel": "취소",
        "constraints": "제약",
        "constraints_placeholder": "오프라인 우선, 유료 API 없음",
        "goal": "제품 목표",
        "goal_placeholder": "예: 로컬 습관 추적 앱 만들기",
        "milestone": "첫 마일스톤",
        "milestone_placeholder": "처음 배포 가능한 프로토타입",
        "notes": "메모",
        "notes_placeholder": "에이전트가 고려할 추가 맥락",
        "project_type": "프로젝트 유형",
        "project_type_placeholder": "SaaS 대시보드, CLI 도구, 모바일 앱",
        "save": "브리프 저장",
        "stack": "선호 스택",
        "stack_placeholder": "python, textual, sqlite",
        "success": "성공 기준",
        "success_placeholder": "사용자가 첫 workflow를 끝낼 수 있음",
        "target_users": "대상 사용자",
        "target_users_placeholder": "지원 담당자, 학생, 개발자",
        "title": "프로젝트 브리프",
    },
}


@dataclass(frozen=True)
class ProjectBriefDraft:
    """Editable user-provided project brief values."""

    product_goal: str = ""
    project_type: str = ""
    target_users: str = ""
    success_criteria: str = ""
    stack_preferences: tuple[str, ...] = ()
    first_milestone: str = ""
    constraints: tuple[str, ...] = ()
    notes: str = ""


class ProjectBriefModal(ModalScreen[ProjectBriefDraft | None]):
    """Edit user-provided project intake brief fields."""

    DEFAULT_CSS = """
    ProjectBriefModal {
        align: center middle;
    }

    #project-brief-modal {
        width: 88;
        max-width: 94%;
        height: auto;
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
    ) -> None:
        super().__init__()
        self.draft = draft or ProjectBriefDraft()
        self.lang = lang

    def compose(self) -> ComposeResult:
        with Vertical(id="project-brief-modal"):
            yield Static(self._label("title"), id="project-brief-title")
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
            yield from self._input_row(
                "constraints",
                "project-brief-constraints",
                _join_values(self.draft.constraints),
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

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        self.dismiss(
            ProjectBriefDraft(
                product_goal=self._input_value("#project-brief-goal"),
                project_type=self._input_value("#project-brief-project-type"),
                target_users=self._input_value("#project-brief-target-users"),
                success_criteria=self._input_value("#project-brief-success"),
                stack_preferences=_split_values(
                    self._input_value("#project-brief-stack")
                ),
                first_milestone=self._input_value("#project-brief-milestone"),
                constraints=_split_values(
                    self._input_value("#project-brief-constraints")
                ),
                notes=self._input_value("#project-brief-notes"),
            )
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


def _split_values(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def _join_values(values: tuple[str, ...]) -> str:
    return ", ".join(values)
