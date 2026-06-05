from __future__ import annotations

from click.testing import CliRunner

from trinity.cli import main
from trinity.textual_app.app import TrinityTextualApp
from trinity.textual_app.screens.execution_matrix import ExecutionMatrixScreen
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.settings import SettingsScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.provider_inspector import ProviderInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel
from trinity.textual_app.widgets.workspace_picker import WorkspacePicker


def test_textual_workbench_import_smoke() -> None:
    assert TrinityTextualApp is not None
    assert StartScreen is not None
    assert NexusScreen is not None
    assert ExecutionMatrixScreen is not None
    assert SettingsScreen is not None
    assert PromptComposer is not None
    assert ProviderPanel is not None
    assert CentralAgentView is not None
    assert WorkflowInspector is not None
    assert ProviderInspector is not None
    assert WorkspacePicker is not None


def test_cli_help_exposes_plain_fallback() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "--plain" in result.output
    assert "legacy Rich/prompt_toolkit TUI" in result.output
