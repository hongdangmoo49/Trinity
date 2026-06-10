"""Agent recipient and model selector widgets."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Checkbox, OptionList, Static

from trinity.models import AgentSpec
from trinity.providers.model_discovery import (
    ProviderModelChoice,
    fallback_provider_models,
)
from trinity.textual_app.i18n import command_palette_text


class AgentToggle(Static):
    """Small selected/unselected square inside an agent model pill."""

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
        self.update(marker)
        self.set_class(self.value, "recipient-agent-toggle-selected")
        self.set_class(not self.agent_enabled, "recipient-agent-toggle-disabled")


class AgentModelTrigger(Static):
    """One-line model dropdown trigger used by an agent pill."""

    can_focus = True

    class Requested(Message):
        """Posted when the model dropdown should be opened."""

        def __init__(self, trigger: "AgentModelTrigger") -> None:
            super().__init__()
            self.trigger = trigger
            self.agent_name = trigger.agent_name

    def __init__(
        self,
        agent_name: str,
        agent_label: str,
        *,
        model: str,
        model_label: str,
        enabled: bool,
        id: str,
    ) -> None:
        super().__init__("", id=id, classes="recipient-agent-model-trigger")
        self.agent_name = agent_name
        self.agent_label = agent_label
        self.value = model
        self.model_label = model_label
        self.agent_enabled = enabled
        self.disabled = not enabled

    def on_mount(self) -> None:
        self._refresh()

    def set_model(self, model: str, model_label: str) -> None:
        """Set selected model without opening the dropdown."""
        self.value = model
        self.model_label = model_label
        self._refresh()

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self._request()

    def on_key(self, event: events.Key) -> None:
        if event.key not in {"space", "enter", "down"}:
            return
        event.stop()
        self._request()

    def _request(self) -> None:
        if not self.agent_enabled:
            return
        self.post_message(self.Requested(self))

    def _refresh(self) -> None:
        label = _clip_label(self.model_label, 10)
        self.update(f"{self.agent_label} ▾ {label}")
        self.set_class(self.agent_enabled, "recipient-agent-model-enabled")
        self.set_class(not self.agent_enabled, "recipient-agent-model-disabled")


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
                yield self._model_trigger(name, spec)
                menu = OptionList(
                    *self._option_list_items(name),
                    id=f"recipient-model-menu-{name}",
                    classes="recipient-agent-model-menu",
                    compact=True,
                    disabled=True,
                )
                menu.display = False
                yield menu

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
            trigger = self.query_one(f"#recipient-model-{name}", AgentModelTrigger)
            value = str(trigger.value or "").strip()
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
            normalized = str(value).strip()
            if normalized:
                self._ensure_model_choice(name, normalized)
                self._set_trigger_model(name, normalized)

    def set_model_choices(
        self,
        name: str,
        choices: tuple[ProviderModelChoice, ...] | list[ProviderModelChoice],
    ) -> None:
        """Update model dropdown choices for one agent, preserving selection."""
        if name not in self.agents:
            return
        spec = self.agents[name]
        trigger = self.query_one(f"#recipient-model-{name}", AgentModelTrigger)
        current = str(trigger.value or spec.model or "default").strip() or "default"
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
        self._refresh_menu_options(name)
        self._set_trigger_model(name, current)

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
        self._refresh_menu_options(name)

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

    def on_agent_model_trigger_requested(
        self,
        event: AgentModelTrigger.Requested,
    ) -> None:
        event.stop()
        self._toggle_model_menu(event.agent_name)

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        option_list_id = event.option_list.id or ""
        prefix = "recipient-model-menu-"
        if not option_list_id.startswith(prefix):
            return
        event.stop()
        name = option_list_id.removeprefix(prefix)
        choices = self._model_choices.get(name, [])
        if event.option_index >= len(choices):
            return
        self._set_trigger_model(name, choices[event.option_index].model)
        self._close_model_menu(name)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape" and self._close_all_model_menus():
            event.stop()

    def _model_trigger(self, name: str, spec: AgentSpec) -> AgentModelTrigger:
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
        return AgentModelTrigger(
            name,
            self._agent_label(name),
            model=current,
            model_label=self._display_model_label(name, current),
            enabled=bool(spec.enabled),
            id=f"recipient-model-{name}",
        )

    def _option_list_items(self, name: str) -> list[str]:
        return [choice.label for choice in self._model_choices.get(name, [])]

    def _refresh_menu_options(self, name: str) -> None:
        if not self.is_mounted:
            return
        menu = self.query_one(f"#recipient-model-menu-{name}", OptionList)
        menu.clear_options()
        menu.add_options(self._option_list_items(name))

    def _toggle_model_menu(self, name: str) -> None:
        menu = self.query_one(f"#recipient-model-menu-{name}", OptionList)
        if bool(menu.display):
            self._close_model_menu(name)
            return
        self._close_all_model_menus(except_name=name)
        menu.display = True
        menu.disabled = False
        menu.highlighted = self._selected_choice_index(name)
        menu.focus()

    def _close_model_menu(self, name: str) -> None:
        menu = self.query_one(f"#recipient-model-menu-{name}", OptionList)
        menu.display = False
        menu.disabled = True
        self.query_one(f"#recipient-model-{name}", AgentModelTrigger).focus()

    def _close_all_model_menus(self, *, except_name: str = "") -> bool:
        closed = False
        for name in self.agents:
            if name == except_name:
                continue
            menu = self.query_one(f"#recipient-model-menu-{name}", OptionList)
            if bool(menu.display):
                menu.display = False
                menu.disabled = True
                closed = True
        return closed

    def _selected_choice_index(self, name: str) -> int:
        trigger = self.query_one(f"#recipient-model-{name}", AgentModelTrigger)
        for index, choice in enumerate(self._model_choices.get(name, [])):
            if choice.model == trigger.value:
                return index
        return 0

    def _set_trigger_model(self, name: str, model: str) -> None:
        trigger = self.query_one(f"#recipient-model-{name}", AgentModelTrigger)
        trigger.set_model(model, self._display_model_label(name, model))

    def _display_model_label(self, name: str, model: str) -> str:
        if model == "default":
            return "기본값" if self.lang == "ko" else "default"
        for choice in self._model_choices.get(name, []):
            if choice.model == model:
                return choice.label
        return model

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


def _clip_label(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)] + "…"
