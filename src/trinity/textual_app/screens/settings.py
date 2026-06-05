"""Theme settings screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Select, Static

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

    def __init__(self, settings_store: UISettingsStore, *, lang: str = "en") -> None:
        super().__init__(name="settings")
        self.settings_store = settings_store
        self.lang = lang
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)
        self.settings = settings_store.load()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="settings-screen"):
            yield Static("Settings", id="settings-title")
            with Horizontal(classes="settings-row"):
                yield Label("Theme mode")
                yield self._select(
                    "theme-mode",
                    ["system", "dark", "light"],
                    self.settings.theme_mode,
                )
            with Horizontal(classes="settings-row"):
                yield Label("Color profile")
                yield self._select(
                    "color-profile",
                    ["auto", "truecolor", "256color", "ascii-safe"],
                    self.settings.color_profile,
                )
            with Horizontal(classes="settings-row"):
                yield Label("Density")
                yield self._select(
                    "density",
                    ["comfortable", "compact"],
                    self.settings.density,
                )
            with Horizontal(classes="settings-row"):
                yield Label("Motion")
                yield self._select("motion", ["normal", "reduced"], self.settings.motion)
            with Horizontal(classes="settings-row"):
                yield Label("Unicode")
                yield self._select(
                    "unicode-rendering",
                    ["auto", "unicode", "ascii"],
                    self.settings.unicode_rendering,
                )
            yield Static(self._preview_text(), id="theme-preview")
            yield Button("Apply", id="apply-settings", variant="primary")
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
        self.query_one("#theme-preview", Static).update(self._preview_text())
        self.query_one("#settings-status", Static).update("Saved")

    def _select(self, id: str, values: list[str], current: str) -> Select[str]:
        return Select(
            [(value, value) for value in values],
            allow_blank=False,
            value=current,
            id=id,
        )

    def _value(self, id: str) -> str:
        return str(self.query_one(f"#{id}", Select).value)

    def _preview_text(self) -> str:
        return "\n".join(
            [
                "Preview",
                f"Mode: {self.settings.theme_mode}",
                f"Density: {self.settings.density}",
                "Claude · Codex · Antigravity",
                "Consensus Reached",
            ]
        )
