"""Nexus brainstorming screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from trinity.config import TrinityConfig
from trinity.models import AgentSpec
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.provider_panel import ProviderPanel, ProviderPanelState


class NexusScreen(Screen[None]):
    """Provider dashboard and central synthesis conversation."""

    class FollowUpSubmitted(Message):
        """Posted when the user sends a follow-up in the active workflow."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    BINDINGS = [
        ("ctrl+enter", "submit_follow_up", "Send"),
    ]

    def __init__(self, config: TrinityConfig) -> None:
        super().__init__(name="nexus")
        self.config = config
        self.initial_prompt: str = ""
        self.follow_ups: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="nexus-screen"):
            with Horizontal(id="provider-strip"):
                for state in self._initial_provider_states():
                    yield ProviderPanel(state, id=f"provider-{state.name}")
            with Vertical(id="central-agent"):
                yield Static("Central Agent", id="central-title")
                yield Static(self._central_body(), id="central-body")
            yield PromptComposer(
                placeholder="Reply, refine direction, or type / for commands",
                id="nexus-composer",
            )
        yield Footer()

    def set_initial_prompt(self, prompt: str) -> None:
        self.initial_prompt = prompt.strip()
        if self.is_mounted:
            self.query_one("#central-body", Static).update(self._central_body())

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
        panel.update_state(self._state_from_spec(name, spec, status=status, summary=summary))

    def on_prompt_composer_submitted(self, event: PromptComposer.Submitted) -> None:
        event.stop()
        self._submit_follow_up(event.text)

    def action_submit_follow_up(self) -> None:
        composer = self.query_one("#nexus-composer", PromptComposer)
        self._submit_follow_up(composer.text)

    def _submit_follow_up(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        self.follow_ups.append(cleaned)
        self.query_one("#nexus-composer", PromptComposer).clear()
        self.query_one("#central-body", Static).update(self._central_body())
        self.post_message(self.FollowUpSubmitted(cleaned))

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

    def _central_body(self) -> str:
        lines = [
            "Waiting for synthesis.",
            "Planning does not require a workspace. Execute will ask for one.",
        ]
        if self.initial_prompt:
            lines.extend(["", "Current prompt:", self.initial_prompt])
        if self.follow_ups:
            lines.extend(["", "Follow-ups:"])
            lines.extend(f"- {item}" for item in self.follow_ups[-3:])
        return "\n".join(lines)
