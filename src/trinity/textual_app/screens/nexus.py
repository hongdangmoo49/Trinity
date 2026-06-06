"""Nexus brainstorming screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header

from trinity.config import TrinityConfig
from trinity.models import AgentSpec
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.central_agent import CentralAgentView, QuestionAnswer
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel, ProviderPanelState


class NexusScreen(Screen[None]):
    """Provider dashboard and central synthesis conversation."""

    class FollowUpSubmitted(Message):
        """Posted when the user sends a follow-up in the active workflow."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class QuestionAnswered(Message):
        """Posted when the user selects a synthesized question answer."""

        def __init__(self, answer: QuestionAnswer) -> None:
            super().__init__()
            self.answer = answer

    class InspectorRequested(Message):
        """Posted when the user wants to inspect provider raw output."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    class ExecuteRequested(Message):
        """Posted when the user wants to move from planning to execution."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    BINDINGS = [
        ("ctrl+enter", "submit_follow_up", "Send"),
        ("ctrl+e", "request_execute", "Execute"),
        ("i", "open_inspector", "Inspector"),
    ]

    LOCALIZED_BINDINGS = {
        ("ctrl+enter", "submit_follow_up"): ("binding_send", None),
        ("ctrl+e", "request_execute"): ("binding_execute", None),
        ("i", "open_inspector"): ("binding_inspector", None),
    }

    def __init__(self, config: TrinityConfig) -> None:
        super().__init__(name="nexus")
        self.config = config
        self.initial_prompt: str = ""
        localize_bindings(
            self._bindings, self.config.lang, self.LOCALIZED_BINDINGS
        )
        self.follow_ups: list[str] = []
        self.snapshot: WorkflowNexusSnapshot | None = None
        self._activity_frame = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="nexus-screen"):
            with Horizontal(id="provider-strip"):
                for state in self._initial_provider_states():
                    yield ProviderPanel(state, id=f"provider-{state.name}")
            with Horizontal(id="nexus-action-bar"):
                yield Button("Open Provider Inspector", id="open-provider-inspector")
                yield Button("Execute", id="request-execute", variant="primary")
            with Horizontal(id="nexus-main"):
                yield CentralAgentView(id="central-agent")
                yield WorkflowInspector(id="workflow-inspector")
            yield PromptComposer(
                placeholder="Reply, refine direction, or type / for commands",
                id="nexus-composer",
                lang=self.config.lang,
            )
        yield Footer()

    def on_mount(self) -> None:
        if self.snapshot is not None:
            self.apply_snapshot(self.snapshot)
        else:
            self._refresh_central()
            self._refresh_inspector()
        self.query_one("#nexus-composer", PromptComposer).focus_text_area()

    def set_initial_prompt(self, prompt: str) -> None:
        self.initial_prompt = prompt.strip()
        if self.is_mounted:
            self._refresh_central()

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        for provider in snapshot.providers:
            panel_id = f"#provider-{provider.name}"
            matches = self.query(panel_id)
            if not matches:
                continue
            panel = matches.first(ProviderPanel)
            panel.update_state(
                ProviderPanelState(
                    name=provider.name,
                    provider=provider.provider,
                    enabled=provider.enabled,
                    status=provider.status,
                    summary=provider.summary,
                    details=provider.raw_output,
                )
            )
        self._refresh_central()
        self._refresh_inspector()
        self._apply_activity_frame()

    def on_central_agent_view_question_answered(
        self,
        event: CentralAgentView.QuestionAnswered,
    ) -> None:
        event.stop()
        self.post_message(self.QuestionAnswered(event.answer))

    def update_provider(
        self,
        name: str,
        *,
        status: str,
        summary: str = "",
    ) -> None:
        spec = self.config.agents.get(name)
        if spec is None:
            return
        panel = self.query_one(f"#provider-{name}", ProviderPanel)
        panel.update_state(
            self._state_from_spec(name, spec, status=status, summary=summary)
        )
        panel.set_activity_frame(self._activity_frame)

    def on_prompt_composer_submitted(self, event: PromptComposer.Submitted) -> None:
        event.stop()
        self._submit_follow_up(event.text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-provider-inspector":
            event.stop()
            self.action_open_inspector()
        elif event.button.id == "request-execute":
            event.stop()
            self.action_request_execute()

    def action_submit_follow_up(self) -> None:
        composer = self.query_one("#nexus-composer", PromptComposer)
        self._submit_follow_up(composer.submission_text)

    def action_open_inspector(self) -> None:
        self.post_message(self.InspectorRequested(self.snapshot))

    def action_request_execute(self) -> None:
        self.post_message(self.ExecuteRequested(self.snapshot))

    def _submit_follow_up(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        self.follow_ups.append(cleaned)
        self.query_one("#nexus-composer", PromptComposer).clear()
        self._refresh_central()
        self.post_message(self.FollowUpSubmitted(cleaned))

    def advance_activity_frame(self) -> None:
        """Advance running indicators for provider and central-agent surfaces."""
        self._activity_frame = (self._activity_frame + 1) % 4
        self._apply_activity_frame()

    def _initial_provider_states(self) -> list[ProviderPanelState]:
        return [
            self._state_from_spec(name, spec)
            for name, spec in self.config.agents.items()
        ]

    def _state_from_spec(
        self,
        name: str,
        spec: AgentSpec,
        *,
        status: str | None = None,
        summary: str = "",
    ) -> ProviderPanelState:
        default_status = "Queued" if spec.enabled else "Disabled"
        return ProviderPanelState(
            name=name,
            provider=spec.provider.value,
            enabled=spec.enabled,
            status=status or default_status,
            summary=summary,
        )

    def _refresh_central(self) -> None:
        central = self.query_one(CentralAgentView)
        if self.snapshot is not None:
            central.apply_snapshot(self.snapshot)
            return
        central.apply_snapshot(self._fallback_snapshot())

    def _refresh_inspector(self) -> None:
        inspector = self.query_one(WorkflowInspector)
        inspector.apply_snapshot(self.snapshot or self._fallback_snapshot())

    def _fallback_snapshot(self) -> WorkflowNexusSnapshot:
        return WorkflowNexusSnapshot(
            goal=self.initial_prompt,
            questions=[],
            work_packages=[
                f"follow-up: {item}" for item in self.follow_ups[-3:]
            ],
        )

    def _apply_activity_frame(self) -> None:
        if not self.is_mounted:
            return
        for panel in self.query(ProviderPanel):
            panel.set_activity_frame(self._activity_frame)
        self.query_one(CentralAgentView).set_activity_frame(self._activity_frame)
