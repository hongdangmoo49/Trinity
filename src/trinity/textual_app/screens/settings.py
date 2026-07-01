"""Workbench settings screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Select, Static

from trinity.config import TrinityConfig
from trinity.display_labels import display_profile_value, display_source_value
from trinity.models import Provider, provider_model_choices
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.settings import (
    UISettings,
    UISettingsStore,
    textual_theme_for_mode,
)


class SettingsScreen(Screen[None]):
    """User UI preference screen."""

    class Applied(Message):
        """Posted when settings are saved and applied to config."""

    BINDINGS = [
        ("ctrl+s", "apply", "Apply"),
    ]

    LOCALIZED_BINDINGS = {
        ("ctrl+s", "apply"): ("binding_apply", None),
    }

    def __init__(
        self,
        settings_store: UISettingsStore,
        config: TrinityConfig,
        *,
        lang: str = "en",
    ) -> None:
        super().__init__(name="settings")
        self.settings_store = settings_store
        self.config = config
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)
        self.settings = settings_store.load()
        self._preview_render_key: str | None = None
        self._status_key = ""
        self._select_cache: dict[str, Select[str]] = {}
        self._agent_model_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        self._preview_widget: Static | None = None
        self._status_widget: Static | None = None
        self._central_provider_value = config.synthesis_agent or "auto"
        self._select_events_ready = False

    def compose(self) -> ComposeResult:
        self._select_cache = {}
        self._preview_widget = None
        self._status_widget = None
        self._status_key = ""
        self._central_provider_value = self.config.synthesis_agent or "auto"
        self._select_events_ready = False
        yield Header(show_clock=False)
        with VerticalScroll(id="settings-screen"):
            yield Static(self._label("settings"), id="settings-title")
            yield Static(self._label("appearance"), classes="settings-section-title")
            with Horizontal(classes="settings-row"):
                yield Label(self._label("theme_mode"))
                yield self._select(
                    "theme-mode",
                    ["system", "dark", "light"],
                    self.settings.theme_mode,
                )
            with Horizontal(classes="settings-row"):
                yield Label(self._label("color_profile"))
                yield self._select(
                    "color-profile",
                    ["auto", "truecolor", "256color", "ascii-safe"],
                    self.settings.color_profile,
                )
            with Horizontal(classes="settings-row"):
                yield Label(self._label("density"))
                yield self._select(
                    "density",
                    ["comfortable", "compact"],
                    self.settings.density,
                )
            with Horizontal(classes="settings-row"):
                yield Label(self._label("motion"))
                yield self._select("motion", ["normal", "reduced"], self.settings.motion)
            with Horizontal(classes="settings-row"):
                yield Label(self._label("unicode"))
                yield self._select(
                    "unicode-rendering",
                    ["auto", "unicode", "ascii"],
                    self.settings.unicode_rendering,
                )
            yield Static(self._label("agent_models"), classes="settings-section-title")
            for name, spec in self.config.agents.items():
                with Horizontal(classes="settings-row"):
                    yield Label(self._agent_label(name))
                    yield self._select(
                        f"model-{name}",
                        self._agent_model_values(name, spec.provider, spec.model),
                        spec.model or "default",
                    )
            yield Static(self._label("central_agent"), classes="settings-section-title")
            with Horizontal(classes="settings-row"):
                yield Label(self._label("central_provider"))
                yield self._select(
                    "central-provider",
                    self._central_provider_values(),
                    self.config.synthesis_agent or "auto",
                )
            with Horizontal(classes="settings-row"):
                yield Label(self._label("central_model"))
                yield self._select(
                    "central-model",
                    self._central_model_values(
                        self.config.synthesis_model,
                        self.config.synthesis_agent or "auto",
                    ),
                    self.config.synthesis_model or "agent-default",
                )
            preview_text = self.preview_text()
            self._preview_render_key = preview_text
            preview = Static(preview_text, id="theme-preview")
            self._preview_widget = preview
            yield preview
            yield Button(self._label("apply"), id="apply-settings", variant="primary")
            status = Static("", id="settings-status")
            self._status_widget = status
            yield status
        yield Footer()

    def on_mount(self) -> None:
        self._select_events_ready = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-settings":
            event.stop()
            self.action_apply()

    def on_select_changed(self, event: Select.Changed) -> None:
        if not self._select_events_ready:
            return
        if event.select.id != "central-provider":
            self._set_preview_text(self.preview_text())
            self._set_status_text(self._label("unsaved_changes"))
            return
        event.stop()
        central_provider = str(event.value)
        if central_provider == self._central_provider_value:
            return
        self._central_provider_value = central_provider
        self._refresh_select_options(
            "central-model",
            self._central_model_values("agent-default", central_provider),
            current="agent-default",
        )
        self._set_preview_text(self.preview_text())
        self._set_status_text(self._label("unsaved_changes"))

    def set_agent_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        changed = False
        for name, choices in choices_by_agent.items():
            if name not in self.config.agents:
                continue
            next_choices = tuple(choices)
            if tuple(self._agent_model_choices.get(name, ())) == next_choices:
                continue
            self._agent_model_choices[name] = next_choices
            changed = True
            if self.is_mounted:
                spec = self.config.agents[name]
                self._refresh_select_options(
                    f"model-{name}",
                    self._agent_model_values(name, spec.provider, spec.model),
                )
        if changed and self.is_mounted:
            central_model = self._value("central-model")
            central_provider = self._value("central-provider")
            self._refresh_select_options(
                "central-model",
                self._central_model_values(central_model, central_provider),
            )
            self._set_preview_text(self.preview_text())

    def action_apply(self) -> None:
        self.settings = UISettings(
            theme_mode=self._value("theme-mode"),
            color_profile=self._value("color-profile"),
            density=self._value("density"),
            motion=self._value("motion"),
            unicode_rendering=self._value("unicode-rendering"),
        )
        self.settings_store.save(self.settings)
        self.app.theme = textual_theme_for_mode(self.settings.theme_mode)
        for name, spec in self.config.agents.items():
            selector_id = f"model-{name}"
            spec.model = self._value(selector_id)
        central_provider = self._value("central-provider")
        self.config.synthesis_agent = "" if central_provider == "auto" else central_provider
        self.config.synthesis_model = self._value("central-model")
        self.config.save(self.config.effective_state_dir / "trinity.config")
        self._set_preview_text(self.preview_text())
        self._set_status_text(self._label("saved_applied"))
        self.post_message(self.Applied())

    def _set_preview_text(self, text: str) -> None:
        if text == self._preview_render_key:
            return
        self._preview_static().update(text)
        self._preview_render_key = text

    def _set_status_text(self, text: str) -> None:
        if text == self._status_key:
            return
        self._status_static().update(text)
        self._status_key = text

    def _select(self, id: str, values: list[str], current: str) -> Select[str]:
        select = Select(
            self._select_options(id, values, current),
            allow_blank=False,
            value=current,
            id=id,
        )
        self._select_cache[id] = select
        return select

    def _refresh_select_options(
        self,
        id: str,
        values: list[str],
        *,
        current: str | None = None,
    ) -> None:
        select = self._select_for(id)
        next_current = str(select.value) if current is None else current
        select.set_options(self._select_options(id, values, next_current))
        select.value = next_current

    def _value(self, id: str) -> str:
        return str(self._select_for(id).value)

    def _select_for(self, id: str) -> Select[str]:
        select = self._select_cache.get(id)
        if select is not None:
            return select
        select = self.query_one(f"#{id}", Select)
        self._select_cache[id] = select
        return select

    def _preview_static(self) -> Static:
        if self._preview_widget is not None:
            return self._preview_widget
        self._preview_widget = self.query_one("#theme-preview", Static)
        return self._preview_widget

    def _status_static(self) -> Static:
        if self._status_widget is not None:
            return self._status_widget
        self._status_widget = self.query_one("#settings-status", Static)
        return self._status_widget

    def _select_options(
        self,
        id: str,
        values: list[str],
        current: str,
    ) -> list[tuple[str, str]]:
        return [
            (self._select_display_value(id, value), value)
            for value in self._dedupe_values([*values, current])
        ]

    def _select_display_value(self, id: str, value: str) -> str:
        if id.startswith("model-"):
            name = id.removeprefix("model-")
            spec = self.config.agents.get(name)
            if spec is not None:
                return self._agent_model_display_value(name, spec.provider, value)
        if id == "central-model":
            return self._central_model_display_value(
                value,
                self._current_central_provider(),
            )
        if id == "central-provider" and value != "auto":
            return self._agent_label(value)
        if id == "theme-mode" and value == "system":
            return self._label("dark_fallback")
        if id == "color-profile" and value == "auto":
            return self._label("default_palette")
        if id == "unicode-rendering" and value == "auto":
            return self._label("ascii_fallback")
        return self._display_value(value)

    def preview_text(self) -> str:
        model_lines = []
        for name, spec in self.config.agents.items():
            model_value = self._preview_value(f"model-{name}", spec.model or "default")
            model = (
                self._display_value(model_value)
                if model_value == "default"
                else self._agent_model_display_value(name, spec.provider, model_value)
            )
            model_lines.append(
                (
                    f"{self._agent_label(name)}: {model} · "
                    f"{display_profile_value(spec.profile.context_profile, lang=self.lang)} · "
                    f"{self._profile_strength_summary(spec)} · "
                    f"{self._profile_contract_summary(spec)}"
                )
            )
        central_provider = self._preview_value(
            "central-provider",
            self.config.synthesis_agent or "auto",
        )
        central_model = self._preview_value(
            "central-model",
            self.config.synthesis_model or "agent-default",
        )
        central_provider_label = (
            self._display_value(central_provider)
            if central_provider == "auto"
            else self._agent_label(central_provider)
        )
        central_model_label = self._central_model_display_value(
            central_model,
            central_provider,
        )
        theme_mode = self._preview_value("theme-mode", self.settings.theme_mode)
        density = self._preview_value("density", self.settings.density)
        color_profile = self._preview_value(
            "color-profile",
            self.settings.color_profile,
        )
        motion = self._preview_value("motion", self.settings.motion)
        unicode_rendering = self._preview_value(
            "unicode-rendering",
            self.settings.unicode_rendering,
        )
        return "\n".join(
            [
                self._label("preview"),
                (
                    f"{self._label('theme_mode')}: "
                    f"{self._settings_display_value('theme-mode', theme_mode)}"
                ),
                f"{self._label('density')}: {self._display_value(density)}",
                (
                    f"{self._label('color_profile')}: "
                    f"{self._settings_display_value('color-profile', color_profile)} · "
                    f"{self._label('motion')}: "
                    f"{self._display_value(motion)} · "
                    f"{self._label('unicode')}: "
                    f"{self._settings_display_value('unicode-rendering', unicode_rendering)}"
                ),
                (
                    f"{self._label('central')}: {central_provider_label} / "
                    f"{central_model_label}"
                ),
                *model_lines,
            ]
        )

    def _settings_display_value(self, id: str, value: str) -> str:
        return self._select_display_value(id, value)

    def _preview_value(self, id: str, fallback: str) -> str:
        if self.is_mounted:
            return self._value(id)
        return fallback

    def _agent_model_values(
        self,
        name: str,
        provider: Provider,
        current: str,
    ) -> list[str]:
        values = [choice.model for choice in provider_model_choices(provider)]
        choices = self._agent_model_choices.get(name)
        if choices:
            values.extend(choice.model for choice in choices)
        return self._dedupe_values([*values, current or "default"])

    def _central_provider_values(self) -> list[str]:
        values = ["auto", *self.config.agents.keys()]
        current = self.config.synthesis_agent
        if current and current not in values:
            values.append(current)
        return values

    def _central_model_values(
        self,
        current: str,
        central_provider: str | None = None,
    ) -> list[str]:
        values = [
            "agent-default",
            "default",
            "fast",
            "strong",
        ]
        agent_name = central_provider if central_provider not in {None, "", "auto"} else ""
        if agent_name:
            spec = self.config.agents.get(agent_name)
            if spec is not None:
                values.extend(choice.model for choice in provider_model_choices(spec.provider))
            choices = self._agent_model_choices.get(agent_name)
            if choices:
                values.extend(choice.model for choice in choices)
        else:
            for provider in Provider:
                for choice in provider_model_choices(provider):
                    values.append(choice.model)
            for choices in self._agent_model_choices.values():
                values.extend(choice.model for choice in choices)
        return self._dedupe_values([*values, current or "agent-default"])

    def _current_central_provider(self) -> str:
        if self.is_mounted:
            return self._value("central-provider")
        return self.config.synthesis_agent or "auto"

    def _central_model_display_value(
        self,
        value: str,
        central_provider: str | None = None,
    ) -> str:
        if value in {"agent-default", "default", "fast", "strong"}:
            return self._display_value(value)
        agent_name = central_provider if central_provider not in {None, "", "auto"} else ""
        if agent_name:
            spec = self.config.agents.get(agent_name)
            if spec is not None:
                label = self._agent_model_display_value(agent_name, spec.provider, value)
                if label != value:
                    return label
        for name, spec in self.config.agents.items():
            label = self._agent_model_display_value(name, spec.provider, value)
            if label != value:
                return label
        return value

    def _agent_model_display_value(
        self,
        name: str,
        provider: Provider,
        value: str,
    ) -> str:
        for choice in self._agent_model_choices.get(name, ()):
            if choice.model == value:
                return self._provider_model_choice_label(choice)
        for choice in provider_model_choices(provider):
            if choice.model == value:
                details = [choice.display_name or choice.model]
                if choice.context_budget:
                    details.append(f"{choice.context_budget:,} ctx")
                return "  ".join(details)
        return self._display_value(value)

    def _provider_model_choice_label(self, choice: ProviderModelChoice) -> str:
        details: list[str] = [choice.label]
        if choice.source:
            details.append(display_source_value(choice.source, lang=self.lang))
        if choice.context_budget:
            details.append(f"{choice.context_budget:,} ctx")
        return "  ".join(details)

    @staticmethod
    def _dedupe_values(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for raw in values:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output or ["default"]

    def _profile_strength_summary(self, spec) -> str:
        strengths = sorted(
            spec.profile.strengths.items(),
            key=lambda item: (-float(item[1]), item[0]),
        )
        if not strengths:
            return f"{self._label('profile')} {self._label('balanced')}"
        name, score = strengths[0]
        return f"{display_profile_value(name, lang=self.lang)} {score:.2f}"

    def _profile_contract_summary(self, spec) -> str:
        contracts = spec.profile.output_contracts
        pairs = [
            (
                f"{display_profile_value(mode, lang=self.lang)}:"
                f"{display_profile_value(contracts[mode], lang=self.lang)}"
            )
            for mode in ("execute", "review")
            if contracts.get(mode)
        ]
        if not pairs:
            return f"{self._label('contracts')} {self._label('default')}"
        return f"{self._label('contracts')} {' '.join(pairs)}"

    def _agent_label(self, name: str) -> str:
        labels = {
            "claude": "Claude",
            "codex": "Codex",
            "antigravity": "Antigravity",
        }
        return labels.get(name, name)

    def _display_value(self, value: str) -> str:
        labels = {
            "agent-default": self._label("agent_default"),
            "auto": self._label("auto"),
            "default": self._label("default"),
            "fast": self._label("fast"),
            "strong": self._label("strong"),
            "system": self._label("system"),
            "dark": self._label("dark"),
            "light": self._label("light"),
            "truecolor": self._label("truecolor"),
            "256color": self._label("256color"),
            "ascii-safe": self._label("ascii_safe"),
            "comfortable": self._label("comfortable"),
            "compact": self._label("compact"),
            "normal": self._label("normal"),
            "reduced": self._label("reduced"),
            "unicode": self._label("unicode_value"),
            "ascii": self._label("ascii"),
        }
        return labels.get(value, value)

    def _label(self, key: str) -> str:
        ko = {
            "settings": "설정",
            "appearance": "화면",
            "theme_mode": "테마 모드",
            "color_profile": "색상 프로필",
            "density": "밀도",
            "motion": "로고 애니메이션",
            "unicode": "로고 글리프",
            "agent_models": "에이전트 모델",
            "central": "중앙",
            "central_agent": "중앙 에이전트",
            "central_provider": "중앙 프로바이더",
            "central_model": "중앙 모델",
            "agent_default": "에이전트 기본값",
            "auto": "자동",
            "apply": "적용",
            "saved": "저장됨",
            "saved_applied": "저장됨 · UI와 Start/Nexus 모델 선택에 적용됨",
            "unsaved_changes": "미저장 변경 · 적용을 눌러 저장",
            "preview": "미리보기",
            "profile": "프로필",
            "balanced": "균형",
            "contracts": "출력 형식",
            "default": "기본값",
            "fast": "빠름",
            "strong": "강력",
            "dark_fallback": "다크 대체",
            "default_palette": "기본 팔레트",
            "ascii_fallback": "ASCII 대체",
            "system": "다크 대체",
            "dark": "다크",
            "light": "라이트",
            "truecolor": "트루컬러",
            "256color": "256색",
            "ascii_safe": "ASCII 안전",
            "comfortable": "여유",
            "compact": "간결",
            "normal": "기본",
            "reduced": "줄임",
            "unicode_value": "유니코드",
            "ascii": "ASCII",
        }
        en = {
            "settings": "Settings",
            "appearance": "Appearance",
            "theme_mode": "Theme mode",
            "color_profile": "Color profile",
            "density": "Density",
            "motion": "Logo motion",
            "unicode": "Logo glyphs",
            "agent_models": "Agent models",
            "central": "Central",
            "central_agent": "Central agent",
            "central_provider": "Central provider",
            "central_model": "Central model",
            "agent_default": "Agent default",
            "auto": "Auto",
            "apply": "Apply",
            "saved": "Saved",
            "saved_applied": "Saved · applied to UI and Start/Nexus model selectors",
            "unsaved_changes": "Unsaved changes · press Apply to save",
            "preview": "Preview",
            "profile": "profile",
            "balanced": "balanced",
            "contracts": "contracts",
            "default": "default",
            "fast": "fast",
            "strong": "strong",
            "dark_fallback": "dark fallback",
            "default_palette": "default palette",
            "ascii_fallback": "ASCII fallback",
            "system": "dark fallback",
            "dark": "dark",
            "light": "light",
            "truecolor": "truecolor",
            "256color": "256color",
            "ascii_safe": "ascii-safe",
            "comfortable": "comfortable",
            "compact": "compact",
            "normal": "normal",
            "reduced": "reduced",
            "unicode_value": "unicode",
            "ascii": "ascii",
        }
        labels = ko if self.lang == "ko" else en
        return labels.get(key, key)

    def label_text(self, key: str) -> str:
        return self._label(key)
