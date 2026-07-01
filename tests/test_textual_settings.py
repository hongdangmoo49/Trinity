from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Select, Static

from trinity.config import TrinityConfig
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.settings import UISettings, UISettingsStore, textual_theme_for_mode

SETTINGS_APPLIED_STATUS = "Saved · applied to UI and Start/Nexus model selectors"
SETTINGS_UNSAVED_STATUS = "Unsaved changes · press Apply to save"


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

    assert settings.theme_mode == "dark"
    assert settings.color_profile == "default"
    assert settings.density == "comfortable"
    assert settings.unicode_rendering == "ascii"


def test_ui_settings_store_preserves_legacy_system_theme(tmp_path) -> None:
    store = UISettingsStore(tmp_path / ".trinity")
    store.path.parent.mkdir(parents=True)
    store.path.write_text("[theme]\ntheme_mode='system'\n", encoding="utf-8")

    settings = store.load()

    assert settings.theme_mode == "system"
    assert textual_theme_for_mode(settings.theme_mode) == "textual-dark"


def test_ui_settings_store_preserves_legacy_auto_glyphs(tmp_path) -> None:
    store = UISettingsStore(tmp_path / ".trinity")
    store.path.parent.mkdir(parents=True)
    store.path.write_text("[theme]\nunicode_rendering='auto'\n", encoding="utf-8")

    settings = store.load()

    assert settings.unicode_rendering == "auto"


def test_ui_settings_store_preserves_legacy_auto_color_profile(tmp_path) -> None:
    store = UISettingsStore(tmp_path / ".trinity")
    store.path.parent.mkdir(parents=True)
    store.path.write_text("[theme]\ncolor_profile='auto'\n", encoding="utf-8")

    settings = store.load()

    assert settings.color_profile == "auto"


def test_settings_preview_includes_agent_profile_summary(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)

    preview = screen.preview_text()

    assert "Current selections" in preview
    assert "UI preferences" in preview
    assert "- Theme mode: dark" in preview
    assert "Agent model defaults" in preview
    assert "- Claude: default" in preview
    assert textual_theme_for_mode("system") == "textual-dark"
    assert "architect" in preview
    assert "implementer" in preview
    assert "architecture 0.95" in preview
    assert "implementation 0.95" in preview


def test_settings_labels_describe_ui_and_model_scopes(tmp_path) -> None:
    en = SettingsScreen(
        UISettingsStore(tmp_path / ".trinity-en"),
        TrinityConfig.default_config(project_dir=tmp_path / "en"),
    )
    ko = SettingsScreen(
        UISettingsStore(tmp_path / ".trinity-ko"),
        TrinityConfig.default_config(project_dir=tmp_path / "ko", lang="ko"),
        lang="ko",
    )

    assert en.label_text("appearance") == "UI preferences"
    assert en.label_text("color_profile") == "Color compatibility"
    assert en.label_text("agent_models") == "Agent model defaults"
    assert en.label_text("central_agent") == "Central agent default model"
    assert en.label_text("central_provider") == "Central agent provider"
    assert en.label_text("central_model") == "Central agent model"
    assert ko.label_text("appearance") == "화면 설정"
    assert ko.label_text("color_profile") == "색상 호환성"
    assert ko.label_text("agent_models") == "에이전트 기본 모델"
    assert ko.label_text("central_agent") == "중앙 에이전트 기본 모델"
    assert ko.label_text("central_provider") == "중앙 에이전트 프로바이더"
    assert ko.label_text("central_model") == "중앙 에이전트 모델"


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
        assert status_updates == [SETTINGS_APPLIED_STATUS]

        status_updates.clear()
        screen.action_apply()
        await pilot.pause()

        assert preview_updates == []
        assert status_updates == []


@pytest.mark.asyncio
async def test_settings_select_change_marks_unsaved(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        status = screen.query_one("#settings-status", Static)

        screen.action_apply()
        await pilot.pause()
        assert str(status.content) == SETTINGS_APPLIED_STATUS

        screen.query_one("#density").value = "compact"
        await pilot.pause()
        assert str(status.content) == SETTINGS_UNSAVED_STATUS

        screen.action_apply()
        await pilot.pause()
        assert str(status.content) == SETTINGS_APPLIED_STATUS


@pytest.mark.asyncio
async def test_settings_status_uses_korean_apply_label(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config, lang="ko")
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        status = screen.query_one("#settings-status", Static)

        screen.action_apply()
        await pilot.pause()

        assert str(status.content) == "저장됨 · 화면과 시작/넥서스 모델 선택에 적용됨"
        assert "Start/Nexus" not in str(status.content)


@pytest.mark.asyncio
async def test_settings_preview_updates_before_apply(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        preview = screen.query_one("#theme-preview", Static)

        screen.query_one("#theme-mode").value = "light"
        screen.query_one("#density").value = "compact"
        screen.query_one("#central-provider").value = "codex"
        await pilot.pause()

        text = str(preview.content)
        assert "- Theme mode: light" in text
        assert "- Density: compact" in text
        assert "Central agent default model\n- Codex / Agent default" in text

    assert UISettingsStore(tmp_path / ".trinity").load() == UISettings()
    assert config.synthesis_agent == ""


@pytest.mark.asyncio
async def test_settings_select_labels_describe_fallbacks(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        theme_labels = {
            value: str(label)
            for label, value in screen.query_one("#theme-mode", Select)._options
        }
        color_labels = {
            value: str(label)
            for label, value in screen.query_one("#color-profile", Select)._options
        }
        motion_labels = {
            value: str(label)
            for label, value in screen.query_one("#motion", Select)._options
        }
        glyph_labels = {
            value: str(label)
            for label, value in screen.query_one("#unicode-rendering", Select)._options
        }
        central_labels = {
            value: str(label)
            for label, value in screen.query_one("#central-provider", Select)._options
        }

    assert "system" not in theme_labels
    assert theme_labels["dark"] == "dark"
    assert "auto" not in color_labels
    assert color_labels["default"] == "default colors"
    assert motion_labels["normal"] == "animated"
    assert motion_labels["reduced"] == "reduced motion"
    assert "auto" not in glyph_labels
    assert glyph_labels["ascii"] == "ascii"
    assert central_labels["auto"] == "Auto"


@pytest.mark.asyncio
async def test_settings_theme_select_keeps_legacy_system_value(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    store = UISettingsStore(tmp_path / ".trinity")
    store.save(UISettings(theme_mode="system"))
    screen = SettingsScreen(store, config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        theme = screen.query_one("#theme-mode", Select)
        labels = {value: str(label) for label, value in theme._options}

    assert theme.value == "system"
    assert labels["system"] == "dark fallback"


@pytest.mark.asyncio
async def test_settings_glyph_select_keeps_legacy_auto_value(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    store = UISettingsStore(tmp_path / ".trinity")
    store.save(UISettings(unicode_rendering="auto"))
    screen = SettingsScreen(store, config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        glyphs = screen.query_one("#unicode-rendering", Select)
        labels = {value: str(label) for label, value in glyphs._options}

    assert glyphs.value == "auto"
    assert labels["auto"] == "ASCII fallback"


@pytest.mark.asyncio
async def test_settings_color_profile_select_keeps_legacy_auto_value(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    store = UISettingsStore(tmp_path / ".trinity")
    store.save(UISettings(color_profile="auto"))
    screen = SettingsScreen(store, config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        color = screen.query_one("#color-profile", Select)
        labels = {value: str(label) for label, value in color._options}

    assert color.value == "auto"
    assert labels["auto"] == "default colors"


@pytest.mark.asyncio
async def test_settings_legacy_select_labels_use_korean_fallbacks(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    store = UISettingsStore(tmp_path / ".trinity")
    store.save(
        UISettings(
            theme_mode="system",
            color_profile="auto",
            unicode_rendering="auto",
        )
    )
    screen = SettingsScreen(store, config, lang="ko")
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        theme = screen.query_one("#theme-mode", Select)
        color = screen.query_one("#color-profile", Select)
        glyphs = screen.query_one("#unicode-rendering", Select)
        theme_labels = {value: str(label) for label, value in theme._options}
        color_labels = {value: str(label) for label, value in color._options}
        glyph_labels = {value: str(label) for label, value in glyphs._options}

    assert theme_labels["system"] == "다크 모드로 대체"
    assert color_labels["auto"] == "기본 색상"
    assert glyph_labels["auto"] == "ASCII로 대체"


@pytest.mark.asyncio
async def test_settings_apply_normalizes_legacy_visual_values(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    store = UISettingsStore(tmp_path / ".trinity")
    store.save(
        UISettings(
            theme_mode="system",
            color_profile="auto",
            unicode_rendering="auto",
        )
    )
    screen = SettingsScreen(store, config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        screen.action_apply()
        await pilot.pause()

        theme = screen.query_one("#theme-mode", Select)
        color = screen.query_one("#color-profile", Select)
        glyphs = screen.query_one("#unicode-rendering", Select)
        preview = str(screen.query_one("#theme-preview", Static).content)

    saved = store.load()
    assert saved.theme_mode == "dark"
    assert saved.color_profile == "default"
    assert saved.unicode_rendering == "ascii"
    assert "Current selections" in preview
    assert theme.value == "dark"
    assert color.value == "default"
    assert glyphs.value == "ascii"
    assert "system" not in {value for _, value in theme._options}
    assert "auto" not in {value for _, value in color._options}
    assert "auto" not in {value for _, value in glyphs._options}
    assert "- Theme mode: dark" in preview
    assert "- Color compatibility: default colors" in preview
    assert "- Start logo glyphs: ascii" in preview


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
        assert str(screen._status_widget.content) == SETTINGS_APPLIED_STATUS


@pytest.mark.asyncio
async def test_settings_recompose_rebinds_cached_controls(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = SettingsScreen(UISettingsStore(tmp_path / ".trinity"), config)
    app = SettingsHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        first_select = screen._select_cache["theme-mode"]
        first_status = screen._status_widget

        screen.action_apply()
        await pilot.pause()
        assert screen._status_key == SETTINGS_APPLIED_STATUS

        screen.refresh(recompose=True)
        await pilot.pause()

        assert screen._select_cache["theme-mode"] is not first_select
        assert screen._status_widget is not None
        assert screen._status_widget is not first_status
        assert screen._status_key == ""
        assert str(screen._status_widget.content) == ""

        queries: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            if selector in {"#theme-mode", "#settings-status"}:
                queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        screen.query_one = counted_query_one

        screen.action_apply()
        await pilot.pause()

        assert queries == []
        assert isinstance(screen._select_cache["theme-mode"], Select)
        assert str(screen._status_widget.content) == SETTINGS_APPLIED_STATUS
