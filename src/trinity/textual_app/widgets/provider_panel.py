"""Provider status panel widgets."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static


@dataclass(frozen=True)
class ProviderPanelState:
    """Display state for a provider panel."""

    name: str
    provider: str
    enabled: bool
    status: str
    summary: str = ""
    details: str = ""


ACTIVITY_FRAMES = ("|", "/", "-", "\\")


class ProviderPanel(VerticalScroll):
    """Compact status surface for a provider."""

    def __init__(self, state: ProviderPanelState, *, id: str | None = None) -> None:
        super().__init__(id=id, classes=self._classes_for(state))
        self.state = state
        self._activity_frame = 0

    def compose(self) -> ComposeResult:
        yield Static(self.state.name.title(), classes="provider-name")
        yield Static(self._provider_line(), classes="provider-meta")
        yield Static(self._status_line(), classes="provider-status")
        yield Static(self._summary_line(), classes="provider-summary")

    def update_state(self, state: ProviderPanelState) -> None:
        self.state = state
        self.set_classes(self._classes_for(state))
        self.query_one(".provider-name", Static).update(state.name.title())
        self.query_one(".provider-meta", Static).update(self._provider_line())
        self.query_one(".provider-status", Static).update(self._status_line())
        self.query_one(".provider-summary", Static).update(self._summary_line())

    def set_activity_frame(self, frame: int) -> None:
        self._activity_frame = frame % len(ACTIVITY_FRAMES)
        if self.is_mounted:
            self.query_one(".provider-status", Static).update(self._status_line())

    def _provider_line(self) -> str:
        return self.state.provider

    def _status_line(self) -> str:
        state = "Enabled" if self.state.enabled else "Disabled"
        prefix = ""
        if self.state.status.lower() == "running":
            prefix = f"{ACTIVITY_FRAMES[self._activity_frame]} "
        return f"{prefix}{self.state.status} · {state}"

    def _summary_line(self) -> str:
        return self.state.details or self.state.summary or "No response yet"

    @staticmethod
    def _classes_for(state: ProviderPanelState) -> str:
        classes = ["provider-panel", f"provider-{state.name.lower()}"]
        if state.status.lower() == "running":
            classes.append("provider-running")
        if not state.enabled:
            classes.append("provider-disabled")
        return " ".join(classes)
