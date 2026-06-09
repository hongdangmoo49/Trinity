"""Agent recipient and model selector widgets."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Checkbox, Select, Static

from trinity.models import AgentSpec, provider_model_choices
from trinity.textual_app.i18n import command_palette_text


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

    def compose(self) -> ComposeResult:
        yield Static(self._text("recipient_label") + ":", classes="recipient-label")
        yield Checkbox(
            self._text("recipient_all"),
            value=bool(self._enabled_agent_names()),
            id="recipient-all",
            classes="recipient-all",
        )
        for name, spec in self.agents.items():
            enabled = bool(spec.enabled)
            checkbox = Checkbox(
                "",
                value=enabled,
                id=f"recipient-{name}",
                classes="recipient-agent-check",
                disabled=not enabled,
            )
            selector = self._model_select(name, spec)
            selector.disabled = not enabled
            yield checkbox
            yield selector

    def selected_agents(self) -> tuple[str, ...]:
        """Return enabled agents selected for the next prompt."""
        selected: list[str] = []
        for name, spec in self.agents.items():
            if not spec.enabled:
                continue
            checkbox = self.query_one(f"#recipient-{name}", Checkbox)
            if checkbox.value:
                selected.append(name)
        return tuple(selected)

    def model_overrides(self) -> dict[str, str]:
        """Return the current model selection for each agent."""
        values: dict[str, str] = {}
        for name in self.agents:
            selector = self.query_one(f"#recipient-model-{name}", Select)
            value = str(selector.value or "").strip()
            if value:
                values[name] = value
        return values

    def set_selected_agents(self, names: tuple[str, ...] | list[str]) -> None:
        """Update checked agents without changing model selections."""
        requested = {str(name).strip() for name in names if str(name).strip()}
        self._syncing = True
        try:
            for name, spec in self.agents.items():
                checkbox = self.query_one(f"#recipient-{name}", Checkbox)
                checkbox.value = spec.enabled and name in requested
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
                selector.value = normalized

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if self._syncing:
            return
        checkbox_id = event.checkbox.id or ""
        if checkbox_id == "recipient-all":
            self._syncing = True
            try:
                for name, spec in self.agents.items():
                    item = self.query_one(f"#recipient-{name}", Checkbox)
                    item.value = bool(event.checkbox.value and spec.enabled)
            finally:
                self._syncing = False
            return
        if checkbox_id.startswith("recipient-"):
            self._sync_all_checkbox()

    def _sync_all_checkbox(self) -> None:
        all_checkbox = self.query_one("#recipient-all", Checkbox)
        enabled = self._enabled_agent_names()
        all_checkbox.value = bool(enabled) and set(self.selected_agents()) == set(enabled)

    def _model_select(self, name: str, spec: AgentSpec) -> Select[str]:
        values = self._model_values(spec)
        current = spec.model or "default"
        if current not in values:
            values.append(current)
        options = [
            (f"{self._agent_label(name)} · {self._display_model(value)}", value)
            for value in values
        ]
        return Select(
            options,
            allow_blank=False,
            value=current,
            id=f"recipient-model-{name}",
            classes="recipient-agent-model",
        )

    @staticmethod
    def _model_values(spec: AgentSpec) -> list[str]:
        values = [choice.model for choice in provider_model_choices(spec.provider)]
        if spec.model and spec.model not in values:
            values.append(spec.model)
        return values or ["default"]

    def _enabled_agent_names(self) -> tuple[str, ...]:
        return tuple(name for name, spec in self.agents.items() if spec.enabled)

    def _agent_label(self, name: str) -> str:
        labels = {
            "claude": "Claude",
            "codex": "Codex",
            "antigravity": "Antigravity",
        }
        return labels.get(name, name)

    def _display_model(self, model: str) -> str:
        if model == "default":
            return self._text("recipient_provider_default")
        return model

    def _text(self, key: str) -> str:
        return command_palette_text(key, self.lang) or key
