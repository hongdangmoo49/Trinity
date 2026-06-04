"""Tests for Antigravity one-shot provider invoker."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from trinity.models import Provider, ResponseStatus
from trinity.providers.invoker import AntigravityPrintInvoker, PromptRequest
from trinity.providers.policy import ExecutionAuthority, InvocationAccess


def _request(tmp_path: Path) -> PromptRequest:
    return PromptRequest(
        agent_name="antigravity",
        provider=Provider.ANTIGRAVITY_CLI,
        cli_command="agy",
        role_prompt="You are the Reviewer.",
        context_prompt="Previous synthesis.",
        prompt="Review the plan.",
        cwd=tmp_path,
        timeout_seconds=7.2,
        model="gemini-3-pro",
        extra_args=("--log-file", str(tmp_path / "agy.log")),
    )


def test_build_command_uses_agy_print_mode(tmp_path):
    invoker = AntigravityPrintInvoker()

    command = invoker.build_command(_request(tmp_path))

    assert command[:4] == [
        "agy",
        "--model",
        "gemini-3-pro",
        "--print-timeout=8s",
    ]
    assert "--sandbox" in command
    assert "--print" in command
    assert "--log-file" in command
    assert "[System Role]" in command[-1]
    assert "[Context]" in command[-1]
    assert "Review the plan." in command[-1]


def test_build_command_omits_sandbox_for_workspace_write(tmp_path):
    invoker = AntigravityPrintInvoker()
    request = PromptRequest(
        agent_name="antigravity",
        provider=Provider.ANTIGRAVITY_CLI,
        cli_command="agy",
        prompt="Implement the change.",
        cwd=tmp_path,
        access=InvocationAccess.WORKSPACE_WRITE,
    )

    command = invoker.build_command(request)

    assert "--sandbox" not in command
    assert "--dangerously-skip-permissions" not in command


@pytest.mark.asyncio
async def test_invoke_parses_plain_stdout(tmp_path):
    invoker = AntigravityPrintInvoker()
    completed = subprocess.CompletedProcess(
        args=["agy"],
        returncode=0,
        stdout="Use Antigravity print mode.\n",
        stderr="",
    )

    with patch("trinity.providers.invoker.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.OK
    assert result.content == "Use Antigravity print mode."
    assert result.usage is None
    assert result.execution_authority == ExecutionAuthority.PROVIDER_MANAGED
    assert result.metadata["output_format"] == "plain-text"


@pytest.mark.asyncio
async def test_invoke_classifies_antigravity_auth_failure(tmp_path):
    invoker = AntigravityPrintInvoker()
    completed = subprocess.CompletedProcess(
        args=["agy"],
        returncode=1,
        stdout="",
        stderr="Please sign in with your Google account.",
    )

    with patch("trinity.providers.invoker.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.AUTH_REQUIRED
    assert "exit code 1" in result.content
    assert result.diagnostics == ["Please sign in with your Google account."]
