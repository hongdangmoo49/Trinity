"""Tests for Claude one-shot provider invoker."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from trinity.models import Provider, ResponseStatus
from trinity.providers.invoker import ClaudePrintInvoker, PromptRequest
from trinity.providers.policy import ExecutionAuthority


def _request(tmp_path: Path) -> PromptRequest:
    return PromptRequest(
        agent_name="claude",
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        role_prompt="You are the Architect.",
        context_prompt="Previous context.",
        prompt="Design the system.",
        cwd=tmp_path,
        model="opus[1m]",
        extra_args=("--no-session-persistence",),
    )


def test_build_command_uses_claude_print_json_and_system_prompt(tmp_path):
    invoker = ClaudePrintInvoker()

    command = invoker.build_command(_request(tmp_path))

    assert command[:6] == [
        "claude",
        "--model",
        "opus[1m]",
        "-p",
        "--output-format",
        "json",
    ]
    assert "--append-system-prompt" in command
    assert "You are the Architect." in command
    assert "--no-session-persistence" in command
    assert "[System Role]" not in command[-1]
    assert "[Context]" in command[-1]
    assert "Design the system." in command[-1]


def test_build_command_uses_explicit_claude_resume(tmp_path):
    invoker = ClaudePrintInvoker()
    request = _request(tmp_path)
    request = PromptRequest(
        **{**request.__dict__, "provider_session_id": "claude-session-1"}
    )

    command = invoker.build_command(request)

    assert "--resume" in command
    assert command[command.index("--resume") + 1] == "claude-session-1"


@pytest.mark.asyncio
async def test_invoke_parses_claude_json_response(tmp_path):
    invoker = ClaudePrintInvoker()
    completed = subprocess.CompletedProcess(
        args=["claude"],
        returncode=0,
        stdout=json.dumps(
            {
                "result": "Use a stateless one-shot transport.",
                "usage": {"input_tokens": 100, "output_tokens": 40},
                "session_id": "claude-session-1",
                "modelUsage": {
                    "GLM-5.1[1m]": {
                        "contextWindow": 1000000,
                        "maxOutputTokens": 64000,
                    }
                },
            }
        ),
        stderr="",
    )

    with patch("trinity.platform.process.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.OK
    assert result.content == "Use a stateless one-shot transport."
    assert result.usage is not None
    assert result.usage.used == 140
    assert result.execution_authority == ExecutionAuthority.PROVIDER_MANAGED
    assert result.metadata["model"] == "GLM-5.1[1m]"
    assert result.metadata["session_id"] == "claude-session-1"
    assert result.metadata["provider_session"]["provider_session_id"] == "claude-session-1"
    assert result.metadata["runtime_model"]["actual_model"] == "GLM-5.1[1m]"
    assert result.metadata["runtime_model"]["context_window"] == 1000000
    assert result.metadata["runtime_model"]["budget_source"] == "runtime_metadata"


@pytest.mark.asyncio
async def test_invoke_classifies_claude_auth_failure(tmp_path):
    invoker = ClaudePrintInvoker()
    completed = subprocess.CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout="",
        stderr="Please sign in to continue.",
    )

    with patch("trinity.platform.process.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.AUTH_REQUIRED
    assert "exit code 1" in result.content
    assert result.diagnostics == ["Please sign in to continue."]


@pytest.mark.asyncio
async def test_invoke_returns_timeout_status(tmp_path):
    invoker = ClaudePrintInvoker()

    with patch(
        "trinity.platform.process.subprocess.run",
        side_effect=subprocess.TimeoutExpired("claude", 1),
    ):
        result = await invoker.invoke(
            PromptRequest(
                agent_name="claude",
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
                prompt="slow",
                cwd=tmp_path,
                timeout_seconds=1,
            )
        )

    assert result.status == ResponseStatus.TIMEOUT
    assert "Timeout" in result.content
