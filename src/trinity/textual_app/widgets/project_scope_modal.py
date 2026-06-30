"""Focused modal for choosing an existing-project work scope."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Static

from trinity.project_intake import ProjectIntake


PROJECT_SCOPE_LABELS = {
    "en": {
        "cancel": "Cancel",
        "candidates": "Detected scopes",
        "none": "(none)",
        "save": "Save Scope",
        "selected_scope": "Selected scope",
        "selected_scope_placeholder": "apps/web",
        "target_workspace": "Target workspace",
        "title": "Choose Project Scope",
    },
    "ko": {
        "cancel": "취소",
        "candidates": "감지된 범위",
        "none": "(없음)",
        "save": "범위 저장",
        "selected_scope": "선택 범위",
        "selected_scope_placeholder": "apps/web",
        "target_workspace": "대상 작업 폴더",
        "title": "프로젝트 범위 선택",
    },
}


@dataclass(frozen=True)
class ProjectScopeModalResult:
    """Result of closing the project scope modal."""

    saved: bool
    selected_scope: str = ""


class ProjectScopeModal(ModalScreen[ProjectScopeModalResult]):
    """Let users pick the intended scope when candidates were detected."""

    DEFAULT_CSS = """
    ProjectScopeModal {
        align: center middle;
    }

    #project-scope-modal {
        width: 82;
        max-width: 94%;
        height: 95%;
        max-height: 95%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #project-scope-title {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    #project-scope-target,
    #project-scope-candidates {
        color: $text-muted;
        margin-bottom: 1;
    }

    #project-scope-content {
        height: 1fr;
        margin-bottom: 1;
    }

    #project-scope-input-row {
        height: 3;
        margin-bottom: 1;
    }

    #project-scope-input-row Static {
        width: 20;
        content-align: left middle;
        color: $text-muted;
    }

    #project-scope-input {
        width: 1fr;
    }

    #project-scope-candidate-actions {
        height: auto;
        margin-bottom: 1;
    }

    #project-scope-actions {
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

    def compose(self) -> ComposeResult:
        with Vertical(id="project-scope-modal"):
            yield Static(self._label("title"), id="project-scope-title")
            with VerticalScroll(id="project-scope-content"):
                yield Static(
                    f"{self._label('target_workspace')}: {self.intake.target_workspace}",
                    id="project-scope-target",
                )
                yield Static(
                    (
                        f"{self._label('candidates')}: "
                        f"{_join_values(self.intake.scope_candidates, self._label('none'))}"
                    ),
                    id="project-scope-candidates",
                )
                with Horizontal(id="project-scope-input-row"):
                    yield Static(self._label("selected_scope"))
                    yield Input(
                        value=self.intake.selected_scope,
                        id="project-scope-input",
                        placeholder=self._label("selected_scope_placeholder"),
                    )
                with Horizontal(id="project-scope-candidate-actions"):
                    for index, candidate in enumerate(
                        self.intake.scope_candidates,
                        start=1,
                    ):
                        yield Button(
                            candidate,
                            id=f"project-scope-candidate-{index}",
                            variant=(
                                "primary"
                                if candidate == self.intake.selected_scope
                                else "default"
                            ),
                        )
            with Horizontal(id="project-scope-actions"):
                yield Button(self._label("cancel"), id="cancel-project-scope")
                yield Button(
                    self._label("save"),
                    id="save-project-scope",
                    variant="primary",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#project-scope-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "cancel-project-scope":
            event.stop()
            self.action_cancel()
            return
        if button_id == "save-project-scope":
            event.stop()
            self.action_save()
            return
        if button_id.startswith("project-scope-candidate-"):
            event.stop()
            self.query_one("#project-scope-input", Input).value = str(
                event.button.label
            )

    def action_cancel(self) -> None:
        self.dismiss(
            ProjectScopeModalResult(
                saved=False,
                selected_scope=self._selected_scope(),
            )
        )

    def action_save(self) -> None:
        self.dismiss(
            ProjectScopeModalResult(
                saved=True,
                selected_scope=self._selected_scope(),
            )
        )

    def _selected_scope(self) -> str:
        return self.query_one("#project-scope-input", Input).value.strip()

    def _label(self, key: str) -> str:
        labels = PROJECT_SCOPE_LABELS.get(self.lang, PROJECT_SCOPE_LABELS["en"])
        return labels.get(key, PROJECT_SCOPE_LABELS["en"][key])


def _join_values(values: tuple[str, ...], none_label: str) -> str:
    filtered = tuple(value for value in values if value.strip())
    if not filtered:
        return none_label
    return ", ".join(filtered)
