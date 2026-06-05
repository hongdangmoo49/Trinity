from __future__ import annotations

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
