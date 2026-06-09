"""Start screen for the Textual workbench."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from trinity.config import TrinityConfig
from trinity.slash_commands import is_slash_command_text
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.tui.sacred_geometry import SacredGeometryAnimator


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
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="start-screen"):
            with Vertical(id="start-shell"):
                yield SacredGeometryAnimation()
                yield Static("TRINITY", id="start-title")
                yield Static("Three minds, one context", id="start-subtitle")
                yield PromptComposer(
                    placeholder="What should Trinity work on?",
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
                    yield Button("Choose now", id="choose-workspace", variant="default")
                    yield Button("Plan first", id="plan-first", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#start-composer", PromptComposer).focus_text_area()

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
        self.workspace_candidate = path
        label = self.query_one("#workspace-candidate", Static)
        label.update(self._workspace_label())

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
            self.app.notify("Select at least one agent.", severity="warning")
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
            return "Target workspace: Not selected"
        return f"Target workspace: {self.workspace_candidate}"
