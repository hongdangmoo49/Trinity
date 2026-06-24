"""Workbench settings screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Select, Static

from trinity.config import TrinityConfig
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

    def compose(self) -> ComposeResult:
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
            yield Static(self._preview_text(), id="theme-preview")
            yield Button(self._label("apply"), id="apply-settings", variant="primary")
            yield Static("", id="settings-status")
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
        self.query_one("#theme-preview", Static).update(self._preview_text())
        self.query_one("#settings-status", Static).update(self._label("saved"))

    def _select(self, id: str, values: list[str], current: str) -> Select[str]:
        options = [(self._display_value(value), value) for value in values]
        if current not in values:
            options.append((self._display_value(current), current))
        return Select(
            options,
            allow_blank=False,
            value=current,
            id=id,
        )

    def _value(self, id: str) -> str:
        return str(self.query_one(f"#{id}", Select).value)

    def _preview_text(self) -> str:
        model_lines = [
            (
                f"{self._agent_label(name)}: {spec.model or 'default'} · "
                f"{spec.profile.context_profile} · "
                f"{self._profile_strength_summary(spec)} · "
                f"{self._profile_contract_summary(spec)}"
            )
            for name, spec in self.config.agents.items()
        ]
        central_provider = self.config.synthesis_agent or "auto"
        return "\n".join(
            [
                self._label("preview"),
                f"{self._label('theme_mode')}: {self.settings.theme_mode}",
                f"{self._label('density')}: {self.settings.density}",
                f"{self._label('central')}: {central_provider} / {self.config.synthesis_model}",
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

    @staticmethod
    def _profile_strength_summary(spec) -> str:
        strengths = sorted(
            spec.profile.strengths.items(),
            key=lambda item: (-float(item[1]), item[0]),
        )
        if not strengths:
            return "profile balanced"
        name, score = strengths[0]
        return f"{name} {score:.2f}"

    @staticmethod
    def _profile_contract_summary(spec) -> str:
        contracts = spec.profile.output_contracts
        pairs = [
            f"{mode}:{contracts[mode]}"
            for mode in ("execute", "review")
            if contracts.get(mode)
        ]
        if not pairs:
            return "contracts default"
        return f"contracts {' '.join(pairs)}"

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
        }
        labels = ko if self.lang == "ko" else en
        return labels.get(key, key)
