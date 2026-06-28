"""Start screen for the Textual workbench."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from trinity.config import TrinityConfig
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import is_slash_command_text
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.workspace_labels import (
    project_intake_state_label,
    target_workspace_state_label,
)
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.tui.sacred_geometry import SacredGeometryAnimator


START_LABELS = {
    "en": {
        "analyze_workspace": "Analyze Workspace",
        "create_project": "Create Project",
        "plan_first": "Plan first",
        "placeholder": "What should Trinity work on?",
        "select_agent_warning": "Select at least one agent.",
        "select_workspace": "Select Workspace",
        "subtitle": "Three minds, one context",
    },
    "ko": {
        "analyze_workspace": "작업 폴더 분석",
        "create_project": "새 프로젝트",
        "plan_first": "먼저 계획",
        "placeholder": "Trinity가 무엇을 진행하면 될까요?",
        "select_agent_warning": "에이전트를 하나 이상 선택하세요.",
        "select_workspace": "작업 폴더 선택",
        "subtitle": "세 개의 관점, 하나의 컨텍스트",
    },
}


class SacredGeometryAnimation(Static):
    """Textual wrapper for the Trinity ASCII geometry animation."""

    def __init__(self) -> None:
        super().__init__("", id="start-geometry")
        self._angle = 0.0
        self._animator = SacredGeometryAnimator(width=56, height=14, mode="ascii")

    def on_mount(self) -> None:
        self._render_frame()
        self.set_interval(0.12, self._tick)

    def _tick(self) -> None:
        self._angle = (self._angle + 8.0) % 360.0
        self._render_frame()

    def _render_frame(self) -> None:
        self.update(self._animator.render(angle=self._angle))


class StartScreen(Screen[None]):
    """Initial prompt and optional workspace candidate screen."""

    class Submitted(Message):
        """Posted when the user starts planning from the first prompt."""

        def __init__(
            self,
            prompt: str,
            workspace_candidate: Path | None,
            target_agents: tuple[str, ...],
            agent_model_overrides: dict[str, str],
        ) -> None:
            super().__init__()
            self.prompt = prompt
            self.workspace_candidate = workspace_candidate
            self.target_agents = target_agents
            self.agent_model_overrides = agent_model_overrides

    class SlashCommandSubmitted(Message):
        """Posted when the first prompt is a Trinity slash command."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class WorkspaceRequested(Message):
        """Posted when the user wants to choose a workspace candidate early."""

    class ProjectIntakeRequested(Message):
        """Posted when the user wants to analyze the current workspace candidate."""

    class NewProjectRequested(Message):
        """Posted when the user wants to create a new project workspace."""

    BINDINGS = [
        ("ctrl+enter", "submit", "Plan"),
    ]

    LOCALIZED_BINDINGS = {
        ("ctrl+enter", "submit"): ("binding_plan", None),
    }

    def __init__(
        self,
        config: TrinityConfig,
        workspace_candidate: Path | None = None,
        *,
        initial_prompt: str = "",
        lang: str = "en",
    ) -> None:
        super().__init__(name="start")
        self.config = config
        self.workspace_candidate = workspace_candidate
        self.initial_prompt = initial_prompt
        self.lang = lang
        self._agent_model_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        self._workspace_label_key = self._workspace_label()
        self._composer: PromptComposer | None = None
        self._recipient_selector: AgentRecipientModelSelector | None = None
        self._workspace_label_widget: Static | None = None
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        self._reset_widget_cache()
        yield Header(show_clock=False)
        with Vertical(id="start-screen"):
            with Vertical(id="start-shell"):
                yield SacredGeometryAnimation()
                yield Static("TRINITY", id="start-title")
                yield Static(self._label("subtitle"), id="start-subtitle")
                composer = PromptComposer(
                    placeholder=self._label("placeholder"),
                    initial_text=self.initial_prompt,
                    id="start-composer",
                    lang=self.lang,
                )
                self._composer = composer
                yield composer
                selector = AgentRecipientModelSelector(
                    self.config.agents,
                    id="start-recipient-selector",
                    lang=self.lang,
                )
                self._recipient_selector = selector
                yield selector
                with Horizontal(id="start-actions"):
                    workspace_label = Static(
                        self._workspace_label(),
                        id="workspace-candidate",
                    )
                    self._workspace_label_widget = workspace_label
                    yield workspace_label
                    yield Button(
                        self._label("select_workspace"),
                        id="choose-workspace",
                        variant="default",
                    )
                    yield Button(
                        self._label("plan_first"),
                        id="plan-first",
                        variant="primary",
                    )
                yield Static(
                    self._project_intake_label(),
                    id="project-intake-summary",
                )
                with Horizontal(id="project-intake-actions"):
                    yield Button(
                        self._label("analyze_workspace"),
                        id="analyze-workspace",
                        variant="default",
                    )
                    yield Button(
                        self._label("create_project"),
                        id="create-project",
                        variant="default",
                    )
        yield Footer()

    def on_mount(self) -> None:
        self._apply_model_choices()
        self._prompt_composer().focus_text_area()

    def set_agent_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        """Apply live model choices discovered from provider CLIs."""
        changed_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        for name, choices in choices_by_agent.items():
            next_choices = tuple(choices)
            if tuple(self._agent_model_choices.get(name, ())) == next_choices:
                continue
            self._agent_model_choices[name] = next_choices
            changed_choices[name] = next_choices
        if changed_choices and self.is_mounted:
            self._apply_model_choices(changed_choices)

    def _apply_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]] | None = None,
    ) -> None:
        if not self._agent_model_choices:
            return
        selector = self._agent_selector()
        for name, choices in (choices_by_agent or self._agent_model_choices).items():
            selector.set_model_choices(name, choices)

    def on_prompt_composer_submitted(self, event: PromptComposer.Submitted) -> None:
        event.stop()
        self._submit(event.text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "plan-first":
            event.stop()
            composer = self._prompt_composer()
            self._submit(composer.submission_text)
        elif button_id == "choose-workspace":
            event.stop()
            self.post_message(self.WorkspaceRequested())
        elif button_id == "analyze-workspace":
            event.stop()
            self.post_message(self.ProjectIntakeRequested())
        elif button_id == "create-project":
            event.stop()
            self.post_message(self.NewProjectRequested())

    def action_submit(self) -> None:
        composer = self._prompt_composer()
        self._submit(composer.submission_text)

    def set_workspace_candidate(self, path: Path | None) -> None:
        if path == self.workspace_candidate:
            return
        self.workspace_candidate = path
        workspace_label = self._workspace_label()
        if workspace_label == self._workspace_label_key:
            return
        label = self._workspace_label_static()
        label.update(workspace_label)
        self._workspace_label_key = workspace_label

    def _submit(self, prompt: str) -> None:
        text = prompt.strip()
        if not text:
            composer = self._prompt_composer()
            composer.focus_text_area()
            return
        if is_slash_command_text(text):
            self._prompt_composer().clear()
            self.post_message(self.SlashCommandSubmitted(text))
            return
        selector = self._agent_selector()
        target_agents = selector.selected_agents()
        if not target_agents:
            self.app.notify(self._label("select_agent_warning"), severity="warning")
            return
        self.post_message(
            self.Submitted(
                text,
                self.workspace_candidate,
                target_agents,
                selector.model_overrides(),
            )
        )

    def _reset_widget_cache(self) -> None:
        self._composer = None
        self._recipient_selector = None
        self._workspace_label_widget = None

    def _prompt_composer(self) -> PromptComposer:
        if self._composer is None:
            self._composer = self.query_one("#start-composer", PromptComposer)
        return self._composer

    def _agent_selector(self) -> AgentRecipientModelSelector:
        if self._recipient_selector is None:
            self._recipient_selector = self.query_one(AgentRecipientModelSelector)
        return self._recipient_selector

    def _workspace_label_static(self) -> Static:
        if self._workspace_label_widget is None:
            self._workspace_label_widget = self.query_one("#workspace-candidate", Static)
        return self._workspace_label_widget

    def _workspace_label(self) -> str:
        return target_workspace_state_label(
            self.workspace_candidate,
            control_repo=self.config.project_dir,
            lang=self.lang,
        )

    def _project_intake_label(self) -> str:
        return project_intake_state_label(
            self.config.effective_state_dir,
            lang=self.lang,
        )

    def refresh_project_intake_summary(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#project-intake-summary", Static).update(
            self._project_intake_label()
        )

    def _label(self, key: str) -> str:
        labels = START_LABELS.get(self.lang, START_LABELS["en"])
        return labels.get(key, START_LABELS["en"][key])
