from __future__ import annotations

from trinity.config import TrinityConfig
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.settings import UISettings, UISettingsStore


def test_ui_settings_store_round_trips_theme_preferences(tmp_path) -> None:
    store = UISettingsStore(tmp_path / ".trinity")
    settings = UISettings(
        theme_mode="dark",
        color_profile="truecolor",
        density="compact",
        motion="reduced",
        unicode_rendering="unicode",
    )

    store.save(settings)

    assert store.load() == settings
    assert store.path == tmp_path / ".trinity" / "ui" / "settings.toml"


def test_ui_settings_store_uses_defaults_for_invalid_values(tmp_path) -> None:
    store = UISettingsStore(tmp_path / ".trinity")
    store.path.parent.mkdir(parents=True)
    store.path.write_text(
        "[theme]\ntheme_mode='bad'\ndensity='bad'\n",
        encoding="utf-8",
    )

    settings = store.load()

    assert settings.theme_mode == "system"
    assert settings.density == "comfortable"


def test_settings_preview_includes_agent_profile_summary(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)

    preview = screen._preview_text()

    assert "architect" in preview
    assert "implementer" in preview
    assert "architecture 0.95" in preview
    assert "implementation 0.95" in preview
