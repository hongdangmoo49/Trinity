"""Tests for cross-platform process helpers."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from trinity.platform.process import CommandSpec, ProcessRunner, render_command


def test_command_spec_rejects_empty_argv(tmp_path):
    with pytest.raises(ValueError, match="argv"):
        CommandSpec(argv=(), cwd=tmp_path)


def test_process_runner_run_uses_argv_env_cwd_and_utf8(tmp_path):
    runner = ProcessRunner()
    completed = subprocess.CompletedProcess(
        args=["tool"],
        returncode=0,
        stdout="ok",
        stderr="",
    )

    with patch("trinity.platform.process.subprocess.run", return_value=completed) as run:
        result = runner.run(
            CommandSpec(
                argv=("tool", "arg with spaces"),
                cwd=tmp_path,
                env={"TRINITY_TEST": "1"},
                timeout_seconds=5,
            )
        )

    assert result.stdout == "ok"
    kwargs = run.call_args.kwargs
    assert run.call_args.args[0] == ["tool", "arg with spaces"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"]["TRINITY_TEST"] == "1"
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["timeout"] == 5
    assert "shell" not in kwargs


def test_process_runner_run_validates_cwd(tmp_path):
    runner = ProcessRunner()

    with pytest.raises(FileNotFoundError, match="cwd"):
        runner.run(CommandSpec(argv=("tool",), cwd=tmp_path / "missing"))


def test_process_runner_stream_interactive_returns_exit_code(tmp_path):
    runner = ProcessRunner()
    completed = subprocess.CompletedProcess(args=["tool"], returncode=7)

    with patch("trinity.platform.process.subprocess.run", return_value=completed) as run:
        code = runner.stream_interactive(CommandSpec(argv=("tool",), cwd=tmp_path))

    assert code == 7
    kwargs = run.call_args.kwargs
    assert kwargs["cwd"] == tmp_path
    assert "capture_output" not in kwargs
    assert "text" not in kwargs


def test_render_command_posix_quotes_for_display_only():
    assert render_command(["tool", "arg with spaces"], os_name="linux") == (
        "tool 'arg with spaces'"
    )


def test_render_command_windows_quotes_for_display_only():
    assert render_command(["tool.exe", "arg with spaces"], os_name="windows") == (
        'tool.exe "arg with spaces"'
    )
