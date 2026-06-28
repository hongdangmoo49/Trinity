from __future__ import annotations

from trinity.config import TrinityConfig
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.report import ReportScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.settings import UISettingsStore
from trinity.textual_app.workbench_screens import workbench_screen_specs


def test_workbench_screen_specs_build_default_routes(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    settings_store = UISettingsStore(config.effective_state_dir)
    workspace_candidate = tmp_path / "app"

    specs = workbench_screen_specs(config, settings_store, workspace_candidate)

    assert tuple(spec.route for spec in specs) == (
        "start",
        "nexus",
        "settings",
        "execution",
        "report",
    )
    assert [type(spec.screen) for spec in specs] == [
        StartScreen,
        NexusScreen,
        SettingsScreen,
        ExecutionMatrixScreen,
        ReportScreen,
    ]


def test_workbench_screen_specs_preserve_constructor_state(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    settings_store = UISettingsStore(config.effective_state_dir)
    workspace_candidate = tmp_path / "target"

    specs = workbench_screen_specs(config, settings_store, workspace_candidate)

    start = specs[0].screen
    nexus = specs[1].screen
    settings = specs[2].screen
    execution = specs[3].screen
    report = specs[4].screen

    assert isinstance(start, StartScreen)
    assert start.config is config
    assert start.workspace_candidate == workspace_candidate
    assert start.initial_prompt == ""
    assert start.lang == "ko"

    assert isinstance(nexus, NexusScreen)
    assert nexus.config is config

    assert isinstance(settings, SettingsScreen)
    assert settings.settings_store is settings_store
    assert settings.config is config
    assert settings.lang == "ko"

    assert isinstance(execution, ExecutionMatrixScreen)
    assert execution.lang == "ko"

    assert isinstance(report, ReportScreen)
    assert report.lang == "ko"


def test_workbench_screen_specs_can_seed_start_prompt(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    settings_store = UISettingsStore(config.effective_state_dir)
    workspace_candidate = tmp_path / "target"

    specs = workbench_screen_specs(
        config,
        settings_store,
        workspace_candidate,
        start_prompt="새 프로젝트를 설계해줘",
    )

    start = specs[0].screen

    assert isinstance(start, StartScreen)
    assert start.initial_prompt == "새 프로젝트를 설계해줘"
