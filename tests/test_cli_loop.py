from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from trinity.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def loop_project(tmp_path: Path) -> Path:
    state = tmp_path / ".trinity"
    (state / "loops" / "specs").mkdir(parents=True)
    (state / "agents" / "claude").mkdir(parents=True)
    (state / "shared.md").write_text("# Shared Context\n", encoding="utf-8")
    (state / "trinity.config").write_text(
        """
[general]
session_name = "loop-test"

[agents.claude]
provider = "claude-code"
cli_command = "claude"
enabled = true
""",
        encoding="utf-8",
    )
    command = f"{sys.executable} -c \"import sys; sys.exit(0)\""
    (state / "loops" / "specs" / "quality.toml").write_text(
        f"""
id = "quality"
title = "Quality Loop"
goal = "Run quality checks."
max_iterations = 1

[[gates]]
id = "unit"
type = "command"
command = '''{command}'''
required = true
""",
        encoding="utf-8",
    )
    return tmp_path


def test_loop_run_skip_workflow_persists_run_and_gate_results(
    runner: CliRunner,
    loop_project: Path,
) -> None:
    config_path = loop_project / ".trinity" / "trinity.config"
    with patch("trinity.cli.find_config_path", return_value=config_path):
        result = runner.invoke(main, ["loop", "run", "quality", "--skip-workflow"])

    assert result.exit_code == 0
    assert "Loop Run" in result.output
    assert "complete" in result.output
    run_files = list((loop_project / ".trinity" / "loops" / "runs").glob("*/loop.json"))
    assert len(run_files) == 1
    assert run_files[0].with_name("ledger.md").exists()
    assert (
        run_files[0].parent / "iteration-001" / "gate-results.json"
    ).exists()


def test_loop_status_shows_latest_run(
    runner: CliRunner,
    loop_project: Path,
) -> None:
    config_path = loop_project / ".trinity" / "trinity.config"
    with patch("trinity.cli.find_config_path", return_value=config_path):
        runner.invoke(main, ["loop", "run", "quality", "--skip-workflow"])
        result = runner.invoke(main, ["loop", "status"])

    assert result.exit_code == 0
    assert "quality" in result.output
    assert "complete" in result.output


def test_loop_stop_cancels_latest_run(
    runner: CliRunner,
    loop_project: Path,
) -> None:
    config_path = loop_project / ".trinity" / "trinity.config"
    with patch("trinity.cli.find_config_path", return_value=config_path):
        runner.invoke(main, ["loop", "run", "quality", "--skip-workflow"])
        result = runner.invoke(
            main,
            ["loop", "stop", "--reason", "manual pause"],
        )

    assert result.exit_code == 0
    assert "cancelled" in result.output
    assert "manual pause" in result.output


def test_loop_run_unknown_spec_returns_click_error(
    runner: CliRunner,
    loop_project: Path,
) -> None:
    config_path = loop_project / ".trinity" / "trinity.config"
    with patch("trinity.cli.find_config_path", return_value=config_path):
        result = runner.invoke(main, ["loop", "run", "missing", "--skip-workflow"])

    assert result.exit_code != 0
    assert "Loop spec not found" in result.output
