"""Agent recipient and model selector widgets."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from trinity.models import AgentSpec
from trinity.providers.model_discovery import (
    ProviderModelChoice,
    fallback_provider_models,
)
from trinity.textual_app.i18n import command_palette_text


class AgentToggle(Static):
    """Compact target button for one agent."""

    can_focus = True

    class Changed(Message):
        """Posted when an agent target selection changes."""

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
        next_value = bool(value and self.agent_enabled)
        if next_value == self.value:
            return
        self.value = next_value
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
        marker = "[x]" if self.value else "[ ]"
        self.update(Text(f"{marker} {self.label}"))
        self.set_class(self.value, "recipient-agent-toggle-selected")
        self.set_class(not self.agent_enabled, "recipient-agent-toggle-disabled")


class AgentRecipientModelSelector(Horizontal):
    """Select which agents receive the next prompt and store model settings."""

    class SelectionChanged(Message):
        """Posted when the selected recipient agents change."""

        def __init__(self, selected_agents: tuple[str, ...]) -> None:
            super().__init__()
            self.selected_agents = selected_agents

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
        self._selected_models: dict[str, str] = {
            name: spec.model or "default" for name, spec in self.agents.items()
        }
        self._model_choices: dict[str, list[ProviderModelChoice]] = {
            name: self._initial_model_choices(spec)
            for name, spec in self.agents.items()
        }
        self._toggle_cache: dict[str, AgentToggle] = {}

    def compose(self) -> ComposeResult:
        self._toggle_cache = {}
        yield Static(self._text("recipient_label") + ":", classes="recipient-label")
        for name, spec in self.agents.items():
            toggle = AgentToggle(
                name,
                self._agent_label(name),
                value=bool(spec.enabled),
                enabled=bool(spec.enabled),
                id=f"recipient-{name}",
            )
            self._toggle_cache[name] = toggle
            yield toggle

    def selected_agents(self) -> tuple[str, ...]:
        """Return enabled agents selected for the next prompt."""
        selected: list[str] = []
        for name, spec in self.agents.items():
            if not spec.enabled:
                continue
            toggle = self._toggle_for(name)
            if toggle.value:
                selected.append(name)
        return tuple(selected)

    def selected_model(self, name: str) -> str:
        """Return the selected model for an agent."""
        spec = self.agents.get(name)
        fallback = spec.model if spec is not None else "default"
        return self._selected_models.get(name, fallback or "default")

    def selected_models(self) -> dict[str, str]:
        """Return selected model values for every known agent."""
        return {
            name: self.selected_model(name)
            for name in self.agents
        }

    def model_choices(self, name: str) -> tuple[ProviderModelChoice, ...]:
        """Return model choices for a single agent."""
        return tuple(self._model_choices.get(name, ()))

    def model_choices_by_agent(self) -> dict[str, tuple[ProviderModelChoice, ...]]:
        """Return all model choices keyed by agent name."""
        return {
            name: tuple(choices)
            for name, choices in self._model_choices.items()
        }

    def model_overrides(self) -> dict[str, str]:
        """Return explicit model overrides for selected agents."""
        values: dict[str, str] = {}
        selected = set(self.selected_agents())
        for name, spec in self.agents.items():
            if name not in selected:
                continue
            value = self._selected_models.get(name, spec.model or "default").strip()
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
        for name, spec in self.agents.items():
            toggle = self._toggle_for(name)
            toggle.set_value(spec.enabled and name in requested)

    def set_model_overrides(self, values: dict[str, str]) -> None:
        """Update model selections from saved session overrides."""
        for name, value in values.items():
            if name not in self.agents:
                continue
            normalized = str(value).strip()
            if normalized:
                if self._selected_model_matches(name, normalized):
                    continue
                self._ensure_model_choice(name, normalized)
                self._set_selected_model(name, normalized)

    def set_model_selections(self, values: dict[str, str]) -> None:
        """Update explicit model selections for any known agents."""
        for name, value in values.items():
            if name not in self.agents:
                continue
            normalized = str(value).strip() or "default"
            if self._selected_model_matches(name, normalized):
                continue
            self._ensure_model_choice(name, normalized)
            self._set_selected_model(name, normalized)

    def set_model_choices(
        self,
        name: str,
        choices: tuple[ProviderModelChoice, ...] | list[ProviderModelChoice],
    ) -> None:
        """Update model choices for one agent, preserving selection."""
        if name not in self.agents:
            return
        spec = self.agents[name]
        current = self._selected_models.get(name, spec.model or "default").strip()
        current = current or "default"
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
        if (
            tuple(self._model_choices.get(name, ())) == tuple(normalized)
            and self._selected_models.get(name, spec.model or "default") == current
        ):
            return
        self._model_choices[name] = normalized
        self._set_selected_model(name, current)

    def on_agent_toggle_changed(self, event: AgentToggle.Changed) -> None:
        event.stop()
        self.post_message(self.SelectionChanged(self.selected_agents()))

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

    def _set_selected_model(self, name: str, model: str) -> None:
        if self._selected_model_matches(name, model):
            return
        self._selected_models[name] = model

    def _selected_model_matches(self, name: str, model: str) -> bool:
        spec = self.agents.get(name)
        fallback = spec.model if spec is not None else "default"
        current = self._selected_models.get(name, fallback or "default")
        return (current.strip() or "default") == model

    def _toggle_for(self, name: str) -> AgentToggle:
        toggle = self._toggle_cache.get(name)
        if toggle is not None:
            return toggle
        toggle = self.query_one(f"#recipient-{name}", AgentToggle)
        self._toggle_cache[name] = toggle
        return toggle

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
                    source_reason=choice.source_reason,
                )
            )
        if not normalized or normalized[0].model != "default":
            default = fallback_provider_models(spec.provider)[0]
            normalized.insert(0, default)
        return normalized

    def _agent_label(self, name: str) -> str:
        labels = {
            "claude": "Claude",
            "codex": "Codex",
            "antigravity": "Agy",
        }
        return labels.get(name, name)

    def _text(self, key: str) -> str:
        return command_palette_text(key, self.lang) or key
