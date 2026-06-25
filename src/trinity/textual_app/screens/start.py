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
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.tui.sacred_geometry import SacredGeometryAnimator


START_LABELS = {
    "en": {
        "plan_first": "Plan first",
        "placeholder": "What should Trinity work on?",
        "select_agent_warning": "Select at least one agent.",
        "select_workspace": "Select Workspace",
        "subtitle": "Three minds, one context",
        "workspace_not_selected": "Target workspace: Not selected",
        "workspace_selected": "Target workspace: {target}",
    },
    "ko": {
        "plan_first": "먼저 계획",
        "placeholder": "Trinity가 무엇을 진행하면 될까요?",
        "select_agent_warning": "에이전트를 하나 이상 선택하세요.",
        "select_workspace": "작업 폴더 선택",
        "subtitle": "세 개의 관점, 하나의 컨텍스트",
        "workspace_not_selected": "작업 폴더: 선택 안 됨",
        "workspace_selected": "작업 폴더: {target}",
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
        lang: str = "en",
    ) -> None:
        super().__init__(name="start")
        self.config = config
        self.workspace_candidate = workspace_candidate
        self.lang = lang
        self._agent_model_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        self._workspace_label_key = self._workspace_label()
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="start-screen"):
            with Vertical(id="start-shell"):
                yield SacredGeometryAnimation()
                yield Static("TRINITY", id="start-title")
                yield Static(self._label("subtitle"), id="start-subtitle")
                yield PromptComposer(
                    placeholder=self._label("placeholder"),
                    id="start-composer",
                    lang=self.lang,
                )
                yield AgentRecipientModelSelector(
                    self.config.agents,
                    id="start-recipient-selector",
                    lang=self.lang,
                )
                with Horizontal(id="start-actions"):
                    yield Static(self._workspace_label(), id="workspace-candidate")
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
        yield Footer()

    def on_mount(self) -> None:
        self._apply_model_choices()
        self.query_one("#start-composer", PromptComposer).focus_text_area()

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
        selector = self.query_one(AgentRecipientModelSelector)
        for name, choices in (choices_by_agent or self._agent_model_choices).items():
            selector.set_model_choices(name, choices)

    def on_prompt_composer_submitted(self, event: PromptComposer.Submitted) -> None:
        event.stop()
        self._submit(event.text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "plan-first":
            event.stop()
            composer = self.query_one("#start-composer", PromptComposer)
            self._submit(composer.submission_text)
        elif button_id == "choose-workspace":
            event.stop()
            self.post_message(self.WorkspaceRequested())

    def action_submit(self) -> None:
        composer = self.query_one("#start-composer", PromptComposer)
        self._submit(composer.submission_text)

    def set_workspace_candidate(self, path: Path | None) -> None:
        if path == self.workspace_candidate:
            return
        self.workspace_candidate = path
        workspace_label = self._workspace_label()
        if workspace_label == self._workspace_label_key:
            return
        label = self.query_one("#workspace-candidate", Static)
        label.update(workspace_label)
        self._workspace_label_key = workspace_label

    def _submit(self, prompt: str) -> None:
        text = prompt.strip()
        if not text:
            composer = self.query_one("#start-composer", PromptComposer)
            composer.focus_text_area()
            return
        if is_slash_command_text(text):
            self.query_one("#start-composer", PromptComposer).clear()
            self.post_message(self.SlashCommandSubmitted(text))
            return
        selector = self.query_one(AgentRecipientModelSelector)
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

    def _workspace_label(self) -> str:
        if self.workspace_candidate is None:
            return self._label("workspace_not_selected")
        return self._label("workspace_selected").format(target=self.workspace_candidate)

    def _label(self, key: str) -> str:
        labels = START_LABELS.get(self.lang, START_LABELS["en"])
        return labels.get(key, START_LABELS["en"][key])
