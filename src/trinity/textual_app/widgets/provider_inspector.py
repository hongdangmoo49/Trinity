"""Provider output inspector modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Markdown, Static, TabbedContent, TabPane

from trinity.textual_app.snapshot import ProviderSnapshot


class ProviderInspector(ModalScreen[None]):
    """Tabbed modal for provider raw output inspection."""

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def __init__(self, providers: list[ProviderSnapshot]) -> None:
        super().__init__()
        self.providers = providers

    def compose(self) -> ComposeResult:
        with Vertical(id="provider-inspector"):
            yield Static("Provider Inspector", id="provider-inspector-title")
            with TabbedContent(id="provider-inspector-tabs"):
                for provider in self.providers:
                    with TabPane(provider.name.title(), id=f"inspect-{provider.name}"):
                        yield Markdown(self._provider_markdown(provider))
                with TabPane("All", id="inspect-all"):
                    yield Markdown(self._all_markdown())
            yield Button("Close", id="close-provider-inspector", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-provider-inspector":
            event.stop()
            self.dismiss()

    def action_close(self) -> None:
        self.dismiss()

    def _provider_markdown(self, provider: ProviderSnapshot) -> str:
        output = provider.raw_output or provider.summary or "No raw output captured yet."
        return "\n".join(
            [
                f"## {provider.name.title()}",
                "",
                f"- Provider: `{provider.provider}`",
                f"- Status: `{provider.status}`",
                f"- Readiness: `{provider.readiness}`",
                "",
                "```text",
                output.replace("```", "'''"),
                "```",
            ]
        )

    def _all_markdown(self) -> str:
        sections = [self._provider_markdown(provider) for provider in self.providers]
        return "\n\n---\n\n".join(sections)
