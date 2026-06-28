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
        "goal": "Product goal",
        "milestone": "First milestone",
        "notes": "Notes",
        "save": "Save Brief",
        "stack": "Stack preferences",
        "title": "Project Brief",
    },
    "ko": {
        "cancel": "취소",
        "constraints": "제약",
        "goal": "제품 목표",
        "milestone": "첫 마일스톤",
        "notes": "메모",
        "save": "브리프 저장",
        "stack": "선호 스택",
        "title": "프로젝트 브리프",
    },
}


@dataclass(frozen=True)
class ProjectBriefDraft:
    """Editable user-provided project brief values."""

    product_goal: str = ""
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
            yield Input(value=value, id=input_id)

    def _input_value(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def _label(self, key: str) -> str:
        labels = PROJECT_BRIEF_LABELS.get(self.lang, PROJECT_BRIEF_LABELS["en"])
        return labels.get(key, PROJECT_BRIEF_LABELS["en"][key])


def _split_values(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))


def _join_values(values: tuple[str, ...]) -> str:
    return ", ".join(values)
