"""Provider status panel widgets."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
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
RUNNING_STATUSES = {"deliberating", "executing", "reviewing", "running"}
WAITING_STATUSES = {"pending", "queued", "waiting"}
IDLE_STATUSES = {"idle"}
DONE_STATUSES = {"completed", "done", "ready", "success"}
ISSUE_STATUSES = {"blocked", "error", "failed", "timeout"}


class ProviderPanel(Vertical):
    """Compact status surface for a provider."""

    def __init__(
        self,
        state: ProviderPanelState,
        *,
        id: str | None = None,
        lang: str = "en",
    ) -> None:
        super().__init__(id=id, classes=self._classes_for(state))
        self.state = state
        self.lang = lang
        self._activity_frame = 0

    def compose(self) -> ComposeResult:
        with Horizontal(classes="provider-heading"):
            yield Static(self.state.name.title(), classes="provider-name")
            yield Static(self._status_label(), classes="provider-status")
        yield Static(self._provider_line(), classes="provider-meta")
        yield Static(self._summary_line(), classes="provider-summary")

    def update_state(self, state: ProviderPanelState) -> None:
        self.state = state
        self.set_classes(self._classes_for(state))
        self.query_one(".provider-name", Static).update(state.name.title())
        self.query_one(".provider-meta", Static).update(self._provider_line())
        self.query_one(".provider-status", Static).update(self._status_label())
        self.query_one(".provider-summary", Static).update(self._summary_line())

    def set_activity_frame(self, frame: int) -> None:
        self._activity_frame = frame % len(ACTIVITY_FRAMES)
        if self.is_mounted:
            self.query_one(".provider-status", Static).update(self._status_label())

    def _provider_line(self) -> str:
        return self.state.provider

    def _status_label(self) -> str:
        prefix = ""
        state = self._state_group(self.state)
        if state == "running":
            prefix = f"{ACTIVITY_FRAMES[self._activity_frame]} "
        return f"{prefix}{self._label_for_state(state)}"

    def _summary_line(self) -> str:
        text = self.state.details or self.state.summary or self._empty_summary()
        normalized = " ".join(text.split())
        if len(normalized) <= 72:
            return normalized
        return normalized[:71].rstrip() + "…"

    def _label_for_state(self, state: str) -> str:
        ko = {
            "done": "완료",
            "idle": "휴식",
            "issue": "문제",
            "off": "끔",
            "running": "실행",
            "unknown": "?",
            "waiting": "대기",
        }
        en = {
            "done": "DONE",
            "idle": "IDLE",
            "issue": "ISSUE",
            "off": "OFF",
            "running": "RUN",
            "unknown": "?",
            "waiting": "WAIT",
        }
        labels = ko if self.lang == "ko" else en
        return labels.get(state, state.upper())

    def _empty_summary(self) -> str:
        return "응답 없음" if self.lang == "ko" else "No response yet"

    @staticmethod
    def _classes_for(state: ProviderPanelState) -> str:
        classes = ["provider-panel", f"provider-{state.name.lower()}"]
        state_group = ProviderPanel._state_group(state)
        classes.append(f"provider-state-{state_group}")
        if state_group == "running":
            classes.append("provider-running")
        if state_group == "off":
            classes.append("provider-disabled")
        return " ".join(classes)

    @staticmethod
    def _state_group(state: ProviderPanelState) -> str:
        if not state.enabled:
            return "off"
        raw = state.status.strip().lower()
        if raw in RUNNING_STATUSES:
            return "running"
        if raw in WAITING_STATUSES:
            return "waiting"
        if raw in IDLE_STATUSES:
            return "idle"
        if raw in DONE_STATUSES:
            return "done"
        if raw in ISSUE_STATUSES:
            return "issue"
        return "unknown"
