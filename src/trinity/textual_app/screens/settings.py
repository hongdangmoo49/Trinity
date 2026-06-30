"""Workbench settings screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Select, Static

from trinity.config import TrinityConfig
from trinity.display_labels import display_profile_value
from trinity.models import Provider, provider_model_choices
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.settings import UISettings, UISettingsStore


class SettingsScreen(Screen[None]):
    """User UI preference screen."""

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
        self._preview_widget: Static | None = None
        self._status_widget: Static | None = None

    def compose(self) -> ComposeResult:
        self._select_cache = {}
        self._preview_widget = None
        self._status_widget = None
        self._status_key = ""
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
                        self._agent_model_values(spec.provider, spec.model),
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
                    self._central_model_values(self.config.synthesis_model),
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-settings":
            event.stop()
            self.action_apply()

    def action_apply(self) -> None:
        self.settings = UISettings(
            theme_mode=self._value("theme-mode"),
            color_profile=self._value("color-profile"),
            density=self._value("density"),
            motion=self._value("motion"),
            unicode_rendering=self._value("unicode-rendering"),
        )
        self.settings_store.save(self.settings)
        for name, spec in self.config.agents.items():
            selector_id = f"model-{name}"
            spec.model = self._value(selector_id)
        central_provider = self._value("central-provider")
        self.config.synthesis_agent = "" if central_provider == "auto" else central_provider
        self.config.synthesis_model = self._value("central-model")
        self.config.save(self.config.effective_state_dir / "trinity.config")
        self._set_preview_text(self.preview_text())
        self._set_status_text(self._label("saved"))

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
        options = [(self._display_value(value), value) for value in values]
        if current not in values:
            options.append((self._display_value(current), current))
        select = Select(
            options,
            allow_blank=False,
            value=current,
            id=id,
        )
        self._select_cache[id] = select
        return select

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

    def preview_text(self) -> str:
        model_lines = []
        for name, spec in self.config.agents.items():
            model = self._display_value(spec.model or "default")
            model_lines.append(
                (
                    f"{self._agent_label(name)}: {model} · "
                    f"{display_profile_value(spec.profile.context_profile, lang=self.lang)} · "
                    f"{self._profile_strength_summary(spec)} · "
                    f"{self._profile_contract_summary(spec)}"
                )
            )
        central_provider = self.config.synthesis_agent or "auto"
        central_model = self.config.synthesis_model or "agent-default"
        return "\n".join(
            [
                self._label("preview"),
                (
                    f"{self._label('theme_mode')}: "
                    f"{self._display_value(self.settings.theme_mode)}"
                ),
                f"{self._label('density')}: {self._display_value(self.settings.density)}",
                (
                    f"{self._label('central')}: {self._display_value(central_provider)} / "
                    f"{self._display_value(central_model)}"
                ),
                *model_lines,
            ]
        )

    @staticmethod
    def _agent_model_values(provider: Provider, current: str) -> list[str]:
        values = [choice.model for choice in provider_model_choices(provider)]
        if current and current not in values:
            values.append(current)
        return values or ["default"]

    def _central_provider_values(self) -> list[str]:
        values = ["auto", *self.config.agents.keys()]
        current = self.config.synthesis_agent
        if current and current not in values:
            values.append(current)
        return values

    @staticmethod
    def _central_model_values(current: str) -> list[str]:
        values = [
            "agent-default",
            "default",
            "fast",
            "strong",
        ]
        for provider in Provider:
            for choice in provider_model_choices(provider):
                if choice.model not in values:
                    values.append(choice.model)
        if current and current not in values:
            values.append(current)
        return values

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
            "motion": "애니메이션",
            "unicode": "유니코드",
            "agent_models": "에이전트 모델",
            "central": "중앙",
            "central_agent": "중앙 에이전트",
            "central_provider": "중앙 프로바이더",
            "central_model": "중앙 모델",
            "agent_default": "에이전트 기본값",
            "auto": "자동",
            "apply": "적용",
            "saved": "저장됨",
            "preview": "미리보기",
            "profile": "프로필",
            "balanced": "균형",
            "contracts": "출력 형식",
            "default": "기본값",
            "fast": "빠름",
            "strong": "강력",
            "system": "시스템",
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
            "motion": "Motion",
            "unicode": "Unicode",
            "agent_models": "Agent models",
            "central": "Central",
            "central_agent": "Central agent",
            "central_provider": "Central provider",
            "central_model": "Central model",
            "agent_default": "Agent default",
            "auto": "Auto",
            "apply": "Apply",
            "saved": "Saved",
            "preview": "Preview",
            "profile": "profile",
            "balanced": "balanced",
            "contracts": "contracts",
            "default": "default",
            "fast": "fast",
            "strong": "strong",
            "system": "system",
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
