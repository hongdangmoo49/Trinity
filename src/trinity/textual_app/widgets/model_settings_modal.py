"""Modal for editing per-agent model selections."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, OptionList, Static

from trinity.display_labels import display_source_value
from trinity.models import AgentSpec
from trinity.providers.model_discovery import ProviderModelChoice


class ModelSettingsModal(ModalScreen[dict[str, str] | None]):
    """Centered modal that edits model selections for all agents."""

    DEFAULT_CSS = """
    ModelSettingsModal {
        align: center middle;
    }

    #model-settings-modal {
        width: 94;
        max-width: 94%;
        height: 28;
        max-height: 90%;
        border: round $accent;
        background: $surface;
        padding: 1 2;
    }

    #model-settings-title {
        height: 1;
        margin-bottom: 1;
        color: $accent;
        text-style: bold;
    }

    #model-settings-body {
        height: 1fr;
    }

    #model-agent-list {
        width: 34;
        height: 1fr;
        margin-right: 1;
    }

    .model-agent-row {
        width: 100%;
        margin-bottom: 1;
    }

    #model-choice-panel {
        width: 1fr;
        height: 1fr;
    }

    #model-choice-header {
        height: 3;
        color: $text-muted;
    }

    #model-choice-list {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }

    #model-settings-actions {
        height: auto;
        align-horizontal: right;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        agents: dict[str, AgentSpec],
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
        selected_models: dict[str, str],
        *,
        lang: str = "en",
    ) -> None:
        super().__init__()
        self.agents = agents
        self.lang = lang
        self.selected_models = {
            name: selected_models.get(name, spec.model or "default")
            for name, spec in self.agents.items()
        }
        self.choices_by_agent = {
            name: self._choices_with_selected_model(
                name,
                tuple(choices_by_agent.get(name, ())),
            )
            for name in self.agents
        }
        self.active_agent = next(iter(self.agents), "")
        self._choice_highlight_key: tuple[object, ...] | None = None
        self._choice_list_widget: OptionList | None = None

    def compose(self) -> ComposeResult:
        self._choice_list_widget = None
        with Vertical(id="model-settings-modal"):
            yield Static(self._text("title"), id="model-settings-title")
            with Horizontal(id="model-settings-body"):
                with Vertical(id="model-agent-list"):
                    for name, spec in self.agents.items():
                        yield Button(
                            self._agent_button_label(name, spec),
                            id=f"model-agent-{name}",
                            classes="model-agent-row",
                            variant=(
                                "primary"
                                if name == self.active_agent
                                else "default"
                            ),
                        )
                with Vertical(id="model-choice-panel"):
                    yield Static(
                        self._choice_header(),
                        id="model-choice-header",
                    )
                    choice_list = OptionList(
                        *self.choice_labels(self.active_agent),
                        id="model-choice-list",
                        compact=True,
                    )
                    self._choice_list_widget = choice_list
                    yield choice_list
            with Horizontal(id="model-settings-actions"):
                yield Button(self._text("cancel"), id="cancel-model-settings")
                yield Button(
                    self._text("apply"),
                    id="apply-model-settings",
                    variant="primary",
                )
        yield Footer()

    def on_mount(self) -> None:
        self._sync_choice_highlight()

    def set_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        """Refresh available choices while preserving modal selections."""
        changed = False
        for name, choices in choices_by_agent.items():
            if name not in self.agents:
                continue
            next_choices = self._choices_with_selected_model(name, tuple(choices))
            if tuple(self.choices_by_agent.get(name, ())) == next_choices:
                continue
            self.choices_by_agent[name] = next_choices
            changed = True
        if changed and self.is_mounted:
            self._refresh_choices()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("model-agent-"):
            event.stop()
            next_agent = button_id.removeprefix("model-agent-")
            if next_agent == self.active_agent:
                return
            self.active_agent = next_agent
            self._refresh_choices()
            return
        if button_id == "cancel-model-settings":
            event.stop()
            self.dismiss(None)
            return
        if button_id == "apply-model-settings":
            event.stop()
            self.dismiss(dict(self.selected_models))

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        if event.option_list.id != "model-choice-list":
            return
        event.stop()
        choices = self.choices_by_agent.get(self.active_agent, ())
        if event.option_index >= len(choices):
            return
        selected_model = choices[event.option_index].model
        if self.selected_models.get(self.active_agent, "default") == selected_model:
            return
        self.selected_models[self.active_agent] = selected_model
        self._refresh_choices()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _refresh_choices(self) -> None:
        self._choice_highlight_key = None
        self.refresh(recompose=True)
        self.call_after_refresh(self._sync_choice_highlight)

    def _sync_choice_highlight(self) -> None:
        current = self.selected_models.get(self.active_agent, "default")
        choices = self.choices_by_agent.get(self.active_agent, ())
        target_index = 0
        for index, choice in enumerate(choices):
            if choice.model == current:
                target_index = index
                break
        highlight_key = (
            self.active_agent,
            current,
            tuple(choice.model for choice in choices),
            target_index,
        )
        if highlight_key == self._choice_highlight_key:
            return
        choice_list = self._choice_list()
        choice_list.highlighted = target_index
        self._choice_highlight_key = highlight_key

    def _choice_list(self) -> OptionList:
        if self._choice_list_widget is None:
            self._choice_list_widget = self.query_one("#model-choice-list", OptionList)
        return self._choice_list_widget

    def _agent_button_label(self, name: str, spec: AgentSpec) -> str:
        prefix = "> " if name == self.active_agent else "  "
        enabled = "" if spec.enabled else " off"
        model = self._model_label(name, self.selected_models.get(name, "default"))
        return f"{prefix}{self._agent_label(name)}{enabled}: {model}"

    def _choice_header(self) -> str:
        if not self.active_agent:
            return self._text("no_agents")
        current = self._model_label(
            self.active_agent,
            self.selected_models.get(self.active_agent, "default"),
        )
        return f"{self._agent_label(self.active_agent)}\n{self._text('current')}: {current}"

    def choice_labels(self, name: str) -> list[str]:
        return [
            self._choice_label(choice)
            for choice in self.choices_by_agent.get(name, ())
        ]

    def _choice_label(self, choice: ProviderModelChoice) -> str:
        details: list[str] = [choice.label]
        if choice.source:
            details.append(display_source_value(choice.source, lang=self.lang))
        if choice.context_budget:
            details.append(f"{choice.context_budget:,} ctx")
        return "  ".join(details)

    def _choices_with_selected_model(
        self,
        name: str,
        choices: tuple[ProviderModelChoice, ...],
    ) -> tuple[ProviderModelChoice, ...]:
        selected = str(self.selected_models.get(name, "default")).strip() or "default"
        if selected in {choice.model for choice in choices}:
            return choices
        spec = self.agents[name]
        label = "기본값" if selected == "default" and self.lang == "ko" else selected
        return (
            *choices,
            ProviderModelChoice(
                provider=spec.provider,
                model=selected,
                label=label,
                source="static-fallback",
            ),
        )

    def _model_label(self, name: str, model: str) -> str:
        for choice in self.choices_by_agent.get(name, ()):
            if choice.model == model:
                return choice.label
        if model == "default":
            return "기본값" if self.lang == "ko" else "default"
        return model

    def _agent_label(self, name: str) -> str:
        labels = {
            "claude": "Claude",
            "codex": "Codex",
            "antigravity": "Agy",
        }
        return labels.get(name, name)

    def _text(self, key: str) -> str:
        if self.lang == "ko":
            return {
                "title": "모델 설정",
                "cancel": "취소",
                "apply": "적용",
                "current": "현재",
                "no_agents": "설정할 에이전트가 없습니다.",
            }[key]
        return {
            "title": "Model Settings",
            "cancel": "Cancel",
            "apply": "Apply",
            "current": "Current",
            "no_agents": "No agents to configure.",
        }[key]
