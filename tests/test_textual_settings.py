from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Static

from trinity.config import TrinityConfig
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.settings import UISettings, UISettingsStore


class SettingsHarness(App[None]):
    def __init__(self, screen: SettingsScreen) -> None:
        super().__init__()
        self.settings_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.settings_screen)


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


@pytest.mark.asyncio
async def test_settings_apply_skips_unchanged_display_updates(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        preview = screen.query_one("#theme-preview", Static)
        status = screen.query_one("#settings-status", Static)
        preview_updates: list[str] = []
        status_updates: list[str] = []
        original_preview_update = preview.update
        original_status_update = status.update

        def counted_preview_update(content) -> None:
            preview_updates.append(str(content))
            original_preview_update(content)

        def counted_status_update(content) -> None:
            status_updates.append(str(content))
            original_status_update(content)

        preview.update = counted_preview_update
        status.update = counted_status_update

        screen.action_apply()
        await pilot.pause()

        assert preview_updates == []
        assert status_updates == ["Saved"]

        status_updates.clear()
        screen.action_apply()
        await pilot.pause()

        assert preview_updates == []
        assert status_updates == []


@pytest.mark.asyncio
async def test_settings_apply_uses_cached_controls(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        queries: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            if str(selector).startswith("#"):
                queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        screen.query_one = counted_query_one

        screen.action_apply()
        await pilot.pause()

        assert queries == []
        assert screen._status_widget is not None
        assert str(screen._status_widget.content) == "Saved"
