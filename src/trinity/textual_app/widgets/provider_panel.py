"""Provider status panel widgets."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from trinity.textual_app.widgets.status_label import (
    COMPACT_STATUS_LABELS,
    compact_status_group,
)


@dataclass(frozen=True)
class ProviderPanelState:
    """Display state for a provider panel."""

    name: str
    provider: str
    enabled: bool
    status: str
    summary: str = ""
    details: str = ""
    response_status: str = ""
    configured_model: str = ""
    actual_model: str = ""
    model_label: str = ""
    context_window: int = 0
    budget_source: str = ""
    session_id: str = ""
    output_contract: str = ""
    quality_signal_count: int = 0
    quality_success_count: int = 0
    quality_score: float = 0.0


ACTIVITY_FRAMES = ("|", "/", "-", "\\")


def provider_panel_state_group(state: ProviderPanelState) -> str:
    if not state.enabled:
        return "off"
    response_status = state.response_status.strip().lower()
    if response_status and response_status != "ok":
        return "issue"
    if _looks_like_error_output(state.details or state.summary):
        return "issue"
    return compact_status_group(state.status)


def _looks_like_error_output(text: str) -> bool:
    normalized = " ".join(text.strip().split()).lower()
    if not normalized:
        return False
    return (
        normalized.startswith("[error:")
        or normalized.startswith("error:")
        or normalized.startswith("traceback ")
        or "exit code " in normalized
    )


def provider_panel_classes(state: ProviderPanelState) -> str:
    classes = ["provider-panel", f"provider-{state.name.lower()}"]
    state_group = provider_panel_state_group(state)
    classes.append(f"provider-state-{state_group}")
    if state_group == "running":
        classes.append("provider-running")
    if state_group == "off":
        classes.append("provider-disabled")
    return " ".join(classes)


def provider_panel_state_label(state: str, *, lang: str = "en") -> str:
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
        "off": "OFF",
        **COMPACT_STATUS_LABELS,
    }
    labels = ko if lang == "ko" else en
    return labels.get(state, state.upper())


def provider_panel_status_label(
    state: ProviderPanelState,
    *,
    activity_frame: int = 0,
    lang: str = "en",
) -> str:
    state_group = provider_panel_state_group(state)
    prefix = ""
    if state_group == "running":
        prefix = f"{ACTIVITY_FRAMES[activity_frame % len(ACTIVITY_FRAMES)]} "
    return f"{prefix}{provider_panel_state_label(state_group, lang=lang)}"


def provider_panel_summary_line(state: ProviderPanelState, *, lang: str = "en") -> str:
    text = state.details or state.summary or _provider_panel_empty_summary(lang=lang)
    return _compact_provider_panel_line(text)


def _compact_provider_panel_line(text: str, limit: int = 72) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _provider_panel_empty_summary(*, lang: str = "en") -> str:
    return "응답 없음" if lang == "ko" else "No response yet"


def provider_panel_provider_line(state: ProviderPanelState, *, lang: str = "en") -> str:
    parts = [state.provider]
    model = _provider_panel_model_label(state)
    if model and model.lower() not in state.provider.lower():
        parts.append(model)
    return _compact_provider_panel_line(" · ".join(part for part in parts if part))


def _provider_panel_model_label(state: ProviderPanelState) -> str:
    return (
        state.actual_model
        or state.model_label
        or state.configured_model
    ).strip()


class ProviderPanel(Vertical):
    """Compact status surface for a provider."""

    def __init__(
        self,
        state: ProviderPanelState,
        *,
        id: str | None = None,
        lang: str = "en",
    ) -> None:
        super().__init__(id=id, classes=provider_panel_classes(state))
        self.state = state
        self.lang = lang
        self._activity_frame = 0
        self._static_cache: dict[str, Static] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(classes="provider-heading"):
            name = Static(self.state.name.title(), classes="provider-name")
            status = Static(
                provider_panel_status_label(
                    self.state,
                    activity_frame=self._activity_frame,
                    lang=self.lang,
                ),
                classes="provider-status",
            )
            self._static_cache[".provider-name"] = name
            self._static_cache[".provider-status"] = status
            yield name
            yield status
        meta = Static(
            provider_panel_provider_line(self.state, lang=self.lang),
            classes="provider-meta",
        )
        summary = Static(
            provider_panel_summary_line(self.state, lang=self.lang),
            classes="provider-summary",
        )
        self._static_cache[".provider-meta"] = meta
        self._static_cache[".provider-summary"] = summary
        yield meta
        yield summary

    def update_state(self, state: ProviderPanelState) -> None:
        if state == self.state:
            return
        previous_name = self.state.name.title()
        previous_provider_line = provider_panel_provider_line(
            self.state,
            lang=self.lang,
        )
        previous_status_label = provider_panel_status_label(
            self.state,
            activity_frame=self._activity_frame,
            lang=self.lang,
        )
        previous_summary_line = provider_panel_summary_line(
            self.state,
            lang=self.lang,
        )
        previous_classes = provider_panel_classes(self.state)
        self.state = state
        classes = provider_panel_classes(state)
        if classes != previous_classes:
            self.set_classes(classes)
        name = state.name.title()
        provider_line = provider_panel_provider_line(self.state, lang=self.lang)
        status_label = provider_panel_status_label(
            self.state,
            activity_frame=self._activity_frame,
            lang=self.lang,
        )
        summary_line = provider_panel_summary_line(self.state, lang=self.lang)
        if name != previous_name:
            self._static_for(".provider-name").update(name)
        if provider_line != previous_provider_line:
            self._static_for(".provider-meta").update(provider_line)
        if status_label != previous_status_label:
            self._static_for(".provider-status").update(status_label)
        if summary_line != previous_summary_line:
            self._static_for(".provider-summary").update(summary_line)

    def set_activity_frame(self, frame: int) -> None:
        next_frame = frame % len(ACTIVITY_FRAMES)
        if next_frame == self._activity_frame:
            return
        self._activity_frame = next_frame
        if self.is_mounted and provider_panel_state_group(self.state) == "running":
            self._static_for(".provider-status").update(
                provider_panel_status_label(
                    self.state,
                    activity_frame=self._activity_frame,
                    lang=self.lang,
                )
            )

    def has_running_activity(self) -> bool:
        return provider_panel_state_group(self.state) == "running"

    def _static_for(self, selector: str) -> Static:
        widget = self._static_cache.get(selector)
        if widget is not None:
            return widget
        widget = self.query_one(selector, Static)
        self._static_cache[selector] = widget
        return widget
