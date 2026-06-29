"""Modal for reviewing existing-project analysis anchors."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Static

from trinity.project_intake import ProjectIntake


PROJECT_ANCHORS_LABELS = {
    "en": {
        "build": "Build commands",
        "build_placeholder": "npm run build, uv build",
        "cancel": "Cancel",
        "dev": "Dev commands",
        "dev_placeholder": "npm run dev, uv run app",
        "docs": "Docs",
        "docs_placeholder": "README.md, docs",
        "save": "Save Anchors",
        "source_roots": "Source roots",
        "source_roots_placeholder": "src, tests",
        "target_workspace": "Target workspace",
        "tests": "Test commands",
        "tests_placeholder": "npm test, uv run pytest",
        "title": "Review Analysis Anchors",
    },
    "ko": {
        "build": "빌드 명령",
        "build_placeholder": "npm run build, uv build",
        "cancel": "취소",
        "dev": "개발 명령",
        "dev_placeholder": "npm run dev, uv run app",
        "docs": "문서",
        "docs_placeholder": "README.md, docs",
        "save": "앵커 저장",
        "source_roots": "소스 루트",
        "source_roots_placeholder": "src, tests",
        "target_workspace": "대상 작업 경로",
        "tests": "테스트 명령",
        "tests_placeholder": "npm test, uv run pytest",
        "title": "분석 앵커 확인",
    },
}


@dataclass(frozen=True)
class ProjectAnchorsDraft:
    """Editable existing-project anchor values."""

    docs_found: tuple[str, ...] = ()
    source_roots: tuple[str, ...] = ()
    test_commands: tuple[str, ...] = ()
    dev_commands: tuple[str, ...] = ()
    build_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectAnchorsModalResult:
    """Result of closing the project anchors modal."""

    saved: bool
    draft: ProjectAnchorsDraft


class ProjectAnchorsModal(ModalScreen[ProjectAnchorsModalResult]):
    """Review and adjust detected existing-project analysis anchors."""

    DEFAULT_CSS = """
    ProjectAnchorsModal {
        align: center middle;
    }

    #project-anchors-modal {
        width: 88;
        max-width: 94%;
        height: auto;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #project-anchors-title {
        height: 1;
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    #project-anchors-target {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    .project-anchors-row {
        height: 3;
        margin-bottom: 1;
    }

    .project-anchors-row Static {
        width: 22;
        content-align: left middle;
        color: $text-muted;
    }

    .project-anchors-row Input {
        width: 1fr;
    }

    #project-anchors-actions {
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
        intake: ProjectIntake,
        *,
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.intake = intake
        self.lang = lang
        self.draft = ProjectAnchorsDraft(
            docs_found=intake.docs_found,
            source_roots=intake.source_roots,
            test_commands=intake.test_commands,
            dev_commands=intake.dev_commands,
            build_commands=intake.build_commands,
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="project-anchors-modal"):
            yield Static(self._label("title"), id="project-anchors-title")
            yield Static(
                f"{self._label('target_workspace')}: {self.intake.target_workspace}",
                id="project-anchors-target",
            )
            yield from self._input_row(
                "docs",
                "project-anchors-docs",
                _join_values(self.draft.docs_found),
            )
            yield from self._input_row(
                "source_roots",
                "project-anchors-source-roots",
                _join_values(self.draft.source_roots),
            )
            yield from self._input_row(
                "tests",
                "project-anchors-tests",
                _join_values(self.draft.test_commands),
            )
            yield from self._input_row(
                "dev",
                "project-anchors-dev",
                _join_values(self.draft.dev_commands),
            )
            yield from self._input_row(
                "build",
                "project-anchors-build",
                _join_values(self.draft.build_commands),
            )
            with Horizontal(id="project-anchors-actions"):
                yield Button(self._label("cancel"), id="cancel-project-anchors")
                yield Button(
                    self._label("save"),
                    id="save-project-anchors",
                    variant="primary",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#project-anchors-docs", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "cancel-project-anchors":
            event.stop()
            self.action_cancel()
        elif button_id == "save-project-anchors":
            event.stop()
            self.action_save()

    def action_cancel(self) -> None:
        self.dismiss(ProjectAnchorsModalResult(saved=False, draft=self._current_draft()))

    def action_save(self) -> None:
        self.dismiss(ProjectAnchorsModalResult(saved=True, draft=self._current_draft()))

    def _current_draft(self) -> ProjectAnchorsDraft:
        return ProjectAnchorsDraft(
            docs_found=_split_values(self._input_value("#project-anchors-docs")),
            source_roots=_split_values(
                self._input_value("#project-anchors-source-roots")
            ),
            test_commands=_split_values(self._input_value("#project-anchors-tests")),
            dev_commands=_split_values(self._input_value("#project-anchors-dev")),
            build_commands=_split_values(self._input_value("#project-anchors-build")),
        )

    def _input_row(
        self,
        label_key: str,
        input_id: str,
        value: str,
    ) -> ComposeResult:
        with Horizontal(classes="project-anchors-row"):
            yield Static(self._label(label_key))
            yield Input(
                value=value,
                id=input_id,
                placeholder=self._label(f"{label_key}_placeholder"),
            )

    def _input_value(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def _label(self, key: str) -> str:
        labels = PROJECT_ANCHORS_LABELS.get(self.lang, PROJECT_ANCHORS_LABELS["en"])
        return labels.get(key, PROJECT_ANCHORS_LABELS["en"][key])


def _split_values(value: str) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(part.strip() for part in value.split(",") if part.strip())
    )


def _join_values(values: tuple[str, ...]) -> str:
    return ", ".join(values)
