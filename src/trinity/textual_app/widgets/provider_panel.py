"""Provider status panel widgets."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from trinity.display_labels import compact_source_value, display_profile_value
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
        if state == self.state:
            return
        previous_name = self.state.name.title()
        previous_provider_line = self._provider_line()
        previous_status_label = self._status_label()
        previous_summary_line = self._summary_line()
        self.state = state
        self.set_classes(self._classes_for(state))
        name = state.name.title()
        provider_line = self._provider_line()
        status_label = self._status_label()
        summary_line = self._summary_line()
        if name != previous_name:
            self.query_one(".provider-name", Static).update(name)
        if provider_line != previous_provider_line:
            self.query_one(".provider-meta", Static).update(provider_line)
        if status_label != previous_status_label:
            self.query_one(".provider-status", Static).update(status_label)
        if summary_line != previous_summary_line:
            self.query_one(".provider-summary", Static).update(summary_line)

    def set_activity_frame(self, frame: int) -> None:
        self._activity_frame = frame % len(ACTIVITY_FRAMES)
        if self.is_mounted and self._state_group(self.state) == "running":
            self.query_one(".provider-status", Static).update(self._status_label())

    def has_running_activity(self) -> bool:
        return self._state_group(self.state) == "running"

    def _provider_line(self) -> str:
        parts = [self.state.provider]
        model = self._model_label()
        if model and model.lower() not in self.state.provider.lower():
            parts.append(model)
        context = self._context_label()
        if context:
            parts.append(context)
        session = self.state.session_id.strip()
        if session:
            parts.append(f"{self._meta_label('session')} {session[:8]}")
        output_contract = self.state.output_contract.strip()
        if output_contract:
            parts.append(
                f"{self._meta_label('output')} "
                f"{display_profile_value(output_contract, lang=self.lang)}"
            )
        quality = self._quality_label()
        if quality:
            parts.append(quality)
        return self._compact_line(" · ".join(part for part in parts if part))

    def _status_label(self) -> str:
        prefix = ""
        state = self._state_group(self.state)
        if state == "running":
            prefix = f"{ACTIVITY_FRAMES[self._activity_frame]} "
        return f"{prefix}{self._label_for_state(state)}"

    def _summary_line(self) -> str:
        text = self.state.details or self.state.summary or self._empty_summary()
        return self._compact_line(text)

    @staticmethod
    def _compact_line(text: str, limit: int = 72) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"

    def _model_label(self) -> str:
        return (
            self.state.actual_model
            or self.state.model_label
            or self.state.configured_model
        ).strip()

    def _context_label(self) -> str:
        if self.state.context_window <= 0:
            return ""
        label = (
            f"{self._meta_label('context')} "
            f"{self._format_context_window(self.state.context_window)}"
        )
        source = self._budget_source_label()
        if source:
            label = f"{label}/{source}"
        return label

    def _quality_label(self) -> str:
        if self.state.quality_signal_count <= 0:
            return ""
        label = self._meta_label("quality")
        score = self._format_score(self.state.quality_score)
        return (
            f"{label} {score} "
            f"{self.state.quality_success_count}/{self.state.quality_signal_count}"
        )

    def _budget_source_label(self) -> str:
        return compact_source_value(self.state.budget_source, lang=self.lang)

    def _meta_label(self, key: str) -> str:
        labels = {
            "ko": {
                "context": "컨텍스트",
                "output": "출력",
                "quality": "품질",
                "session": "세션",
            },
            "en": {
                "context": "ctx",
                "output": "out",
                "quality": "q",
                "session": "sid",
            },
        }
        return labels.get(self.lang, labels["en"]).get(key, key)

    @staticmethod
    def _format_context_window(context_window: int) -> str:
        if context_window >= 1_000_000:
            value = context_window / 1_000_000
            return f"{value:g}M"
        if context_window >= 1_000:
            value = context_window / 1_000
            return f"{value:g}K"
        return str(context_window)

    @staticmethod
    def _format_score(score: float) -> str:
        text = f"{score:.3f}".rstrip("0").rstrip(".")
        if text == "-0":
            return "0"
        return text or "0"

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
            "off": "OFF",
            **COMPACT_STATUS_LABELS,
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
        response_status = state.response_status.strip().lower()
        if response_status and response_status != "ok":
            return "issue"
        if ProviderPanel._looks_like_error_output(state.details or state.summary):
            return "issue"
        return compact_status_group(state.status)

    @staticmethod
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
