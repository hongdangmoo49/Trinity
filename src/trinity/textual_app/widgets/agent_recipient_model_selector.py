"""Agent recipient and model selector widgets."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Checkbox, Select, Static

from trinity.models import AgentSpec
from trinity.providers.model_discovery import (
    ProviderModelChoice,
    fallback_provider_models,
)
from trinity.textual_app.i18n import command_palette_text


class AgentToggle(Static):
    """Compact selected/unselected indicator inside an agent model chip."""

    can_focus = True

    class Changed(Message):
        """Posted when an agent chip selection changes."""

        def __init__(self, toggle: "AgentToggle") -> None:
            super().__init__()
            self.toggle = toggle
            self.agent_name = toggle.agent_name
            self.value = toggle.value

    def __init__(
        self,
        agent_name: str,
        label: str,
        *,
        value: bool,
        enabled: bool,
        id: str,
    ) -> None:
        super().__init__("", id=id, classes="recipient-agent-toggle")
        self.agent_name = agent_name
        self.label = label
        self.value = bool(value and enabled)
        self.agent_enabled = enabled
        self.disabled = not enabled

    def on_mount(self) -> None:
        self._refresh()

    def set_value(self, value: bool) -> None:
        """Set selected state without posting a changed message."""
        self.value = bool(value and self.agent_enabled)
        self._refresh()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self._toggle()

    def on_key(self, event: events.Key) -> None:
        if event.key not in {"space", "enter"}:
            return
        event.stop()
        self._toggle()

    def _toggle(self) -> None:
        if not self.agent_enabled:
            return
        self.value = not self.value
        self._refresh()
        self.post_message(self.Changed(self))

    def _refresh(self) -> None:
        marker = "■" if self.value else "□"
        self.update(f"{marker} {self.label} ·")
        self.set_class(self.value, "recipient-agent-toggle-selected")
        self.set_class(not self.agent_enabled, "recipient-agent-toggle-disabled")


class AgentRecipientModelSelector(Horizontal):
    """Select which agents receive the next prompt and which model they use."""

    def __init__(
        self,
        agents: dict[str, AgentSpec],
        *,
        lang: str = "en",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id, classes="agent-recipient-selector")
        self.agents = agents
        self.lang = lang
        self._syncing = False
        self._model_choices: dict[str, list[ProviderModelChoice]] = {
            name: self._initial_model_choices(spec)
            for name, spec in self.agents.items()
        }

    def compose(self) -> ComposeResult:
        yield Static(self._text("recipient_label") + ":", classes="recipient-label")
        yield Checkbox(
            self._text("recipient_all"),
            value=bool(self._enabled_agent_names()),
            id="recipient-all",
            classes="recipient-all",
            compact=True,
        )
        for name, spec in self.agents.items():
            enabled = bool(spec.enabled)
            chip_classes = "recipient-agent-chip"
            if enabled:
                chip_classes += " recipient-agent-chip-selected"
            else:
                chip_classes += " recipient-agent-chip-disabled"
            with Horizontal(id=f"recipient-chip-{name}", classes=chip_classes):
                yield AgentToggle(
                    name,
                    self._agent_label(name),
                    value=enabled,
                    enabled=enabled,
                    id=f"recipient-{name}",
                )
                selector = self._model_select(name, spec)
                selector.disabled = not enabled
                yield selector

    def selected_agents(self) -> tuple[str, ...]:
        """Return enabled agents selected for the next prompt."""
        selected: list[str] = []
        for name, spec in self.agents.items():
            if not spec.enabled:
                continue
            toggle = self.query_one(f"#recipient-{name}", AgentToggle)
            if toggle.value:
                selected.append(name)
        return tuple(selected)

    def model_overrides(self) -> dict[str, str]:
        """Return explicit model overrides for selected agents."""
        values: dict[str, str] = {}
        selected = set(self.selected_agents())
        for name, spec in self.agents.items():
            if name not in selected:
                continue
            selector = self.query_one(f"#recipient-model-{name}", Select)
            value = str(selector.value or "").strip()
            default = spec.model or "default"
            if value and value != default:
                values[name] = value
        return values

    def model_option_labels(self, name: str) -> tuple[str, ...]:
        """Return model option labels for tests and diagnostics."""
        return tuple(choice.label for choice in self._model_choices.get(name, ()))

    def set_selected_agents(self, names: tuple[str, ...] | list[str]) -> None:
        """Update checked agents without changing model selections."""
        requested = {str(name).strip() for name in names if str(name).strip()}
        self._syncing = True
        try:
            for name, spec in self.agents.items():
                toggle = self.query_one(f"#recipient-{name}", AgentToggle)
                toggle.set_value(spec.enabled and name in requested)
                self._sync_chip_class(name)
            self._sync_all_checkbox()
        finally:
            self._syncing = False

    def set_model_overrides(self, values: dict[str, str]) -> None:
        """Update model dropdowns from saved session overrides."""
        for name, value in values.items():
            if name not in self.agents:
                continue
            selector = self.query_one(f"#recipient-model-{name}", Select)
            normalized = str(value).strip()
            if normalized:
                self._ensure_model_choice(name, normalized)
                selector.value = normalized

    def set_model_choices(
        self,
        name: str,
        choices: tuple[ProviderModelChoice, ...] | list[ProviderModelChoice],
    ) -> None:
        """Update model dropdown choices for one agent, preserving selection."""
        if name not in self.agents:
            return
        spec = self.agents[name]
        selector = self.query_one(f"#recipient-model-{name}", Select)
        current = str(selector.value or spec.model or "default").strip() or "default"
        normalized = self._normalize_choices(spec, list(choices))
        if current not in {choice.model for choice in normalized}:
            normalized.append(
                ProviderModelChoice(
                    provider=spec.provider,
                    model=current,
                    label=current,
                    source="static-fallback",
                    context_budget=None,
                )
            )
        self._model_choices[name] = normalized
        selector.set_options(self._options_for_choices(normalized))
        selector.value = current

    def _ensure_model_choice(self, name: str, model: str) -> None:
        if name not in self.agents:
            return
        spec = self.agents[name]
        choices = list(self._model_choices.get(name, self._initial_model_choices(spec)))
        if model in {choice.model for choice in choices}:
            return
        choices.append(
            ProviderModelChoice(
                provider=spec.provider,
                model=model,
                label=model,
                source="static-fallback",
                context_budget=None,
            )
        )
        self._model_choices[name] = choices
        selector = self.query_one(f"#recipient-model-{name}", Select)
        selector.set_options(self._options_for_choices(choices))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if self._syncing:
            return
        checkbox_id = event.checkbox.id or ""
        if checkbox_id == "recipient-all":
            if not event.checkbox.value:
                return
            self._syncing = True
            try:
                for name, spec in self.agents.items():
                    item = self.query_one(f"#recipient-{name}", AgentToggle)
                    item.set_value(bool(event.checkbox.value and spec.enabled))
                    self._sync_chip_class(name)
            finally:
                self._syncing = False
            return

    def on_agent_toggle_changed(self, event: AgentToggle.Changed) -> None:
        event.stop()
        if self._syncing:
            return
        self._sync_chip_class(event.agent_name)
        self._sync_all_checkbox()

    def _sync_all_checkbox(self) -> None:
        all_checkbox = self.query_one("#recipient-all", Checkbox)
        enabled = self._enabled_agent_names()
        self._syncing = True
        try:
            all_checkbox.value = bool(enabled) and set(self.selected_agents()) == set(enabled)
        finally:
            self._syncing = False

    def _sync_chip_class(self, name: str) -> None:
        chip = self.query_one(f"#recipient-chip-{name}", Horizontal)
        toggle = self.query_one(f"#recipient-{name}", AgentToggle)
        chip.set_class(toggle.value, "recipient-agent-chip-selected")
        chip.set_class(not self.agents[name].enabled, "recipient-agent-chip-disabled")

    def _model_select(self, name: str, spec: AgentSpec) -> Select[str]:
        choices = self._model_choices.get(name, self._initial_model_choices(spec))
        current = spec.model or "default"
        if current not in {choice.model for choice in choices}:
            choices = [
                *choices,
                ProviderModelChoice(
                    provider=spec.provider,
                    model=current,
                    label=current,
                    source="static-fallback",
                    context_budget=None,
                ),
            ]
        return Select(
            self._options_for_choices(choices),
            allow_blank=False,
            value=current,
            id=f"recipient-model-{name}",
            classes="recipient-agent-model",
            compact=True,
        )

    @staticmethod
    def _options_for_choices(
        choices: list[ProviderModelChoice],
    ) -> list[tuple[str, str]]:
        return [(choice.label, choice.model) for choice in choices]

    def _initial_model_choices(self, spec: AgentSpec) -> list[ProviderModelChoice]:
        return self._normalize_choices(spec, fallback_provider_models(spec.provider))

    def _normalize_choices(
        self,
        spec: AgentSpec,
        choices: list[ProviderModelChoice],
    ) -> list[ProviderModelChoice]:
        normalized: list[ProviderModelChoice] = []
        seen: set[str] = set()
        for choice in choices:
            model = str(choice.model or "").strip()
            label = str(choice.label or model).strip()
            if not model or model in seen:
                continue
            seen.add(model)
            normalized.append(
                ProviderModelChoice(
                    provider=spec.provider,
                    model=model,
                    label=label,
                    source=choice.source,
                    is_default=choice.is_default,
                    context_budget=choice.context_budget,
                )
            )
        if not normalized or normalized[0].model != "default":
            default = fallback_provider_models(spec.provider)[0]
            normalized.insert(0, default)
        return normalized

    def _enabled_agent_names(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self.agents.items() if spec.enabled)

    def _agent_label(self, name: str) -> str:
        labels = {
            "claude": "Claude",
            "codex": "Codex",
            "antigravity": "Agy",
        }
        return labels.get(name, name)

    def _text(self, key: str) -> str:
        return command_palette_text(key, self.lang) or key
