"""Tests for Antigravity one-shot provider invoker."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from trinity.models import Provider, ResponseStatus
from trinity.providers.invoker import (
    AntigravityPrintInvoker,
    PromptRequest,
    parse_antigravity_log,
)
from trinity.providers.policy import ExecutionAuthority, InvocationAccess


def _request(tmp_path: Path) -> PromptRequest:
    log_path = tmp_path / "agy.log"
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
        extra_args=("--log-file", str(log_path)),
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


def test_build_command_uses_antigravity_conversation_resume(tmp_path):
    invoker = AntigravityPrintInvoker()
    request = PromptRequest(
        agent_name="antigravity",
        provider=Provider.ANTIGRAVITY_CLI,
        cli_command="agy",
        prompt="Continue review.",
        cwd=tmp_path,
        provider_session_id="agy-conv-1",
    )

    command = invoker.build_command(request)

    assert "--conversation" in command
    assert command[command.index("--conversation") + 1] == "agy-conv-1"
    assert "--log-file" in command
    assert str(tmp_path / ".trinity" / "provider-sessions") in command[
        command.index("--log-file") + 1
    ]


def test_build_command_preserves_configured_antigravity_log_file(tmp_path):
    invoker = AntigravityPrintInvoker()
    request = _request(tmp_path)

    command = invoker.build_command(request)

    assert command.count("--log-file") == 1
    assert command[command.index("--log-file") + 1] == str(tmp_path / "agy.log")


@pytest.mark.asyncio
async def test_invoke_parses_plain_stdout(tmp_path):
    invoker = AntigravityPrintInvoker()
    (tmp_path / "agy.log").write_text(
        'Print mode: conversation=agy-conv-1\n'
        'Propagating selected model override to backend: label="Gemini 3.5 Flash (Medium)"\n',
        encoding="utf-8",
    )
    completed = subprocess.CompletedProcess(
        args=["agy"],
        returncode=0,
        stdout="Use Antigravity print mode.\n",
        stderr="",
    )

    with patch("trinity.platform.process.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.OK
    assert result.content == "Use Antigravity print mode."
    assert result.usage is None
    assert result.execution_authority == ExecutionAuthority.PROVIDER_MANAGED
    assert result.metadata["output_format"] == "plain-text"
    assert result.metadata["machine_readable_output"] is False
    assert result.metadata["usage_source"] == "unsupported"
    assert result.metadata["conversation_id"] == "agy-conv-1"
    assert result.metadata["model_label"] == "Gemini 3.5 Flash (Medium)"
    assert result.metadata["provider_session"]["provider_session_id"] == "agy-conv-1"
    assert result.metadata["runtime_model"]["model_label"] == "Gemini 3.5 Flash (Medium)"


@pytest.mark.asyncio
async def test_invoke_keeps_json_looking_stdout_as_plain_text(tmp_path):
    invoker = AntigravityPrintInvoker()
    stdout = '{"content": "Reviewed.", "usage": {"input_tokens": 10}}\n'
    completed = subprocess.CompletedProcess(
        args=["agy"],
        returncode=0,
        stdout=stdout,
        stderr="",
    )

    with patch("trinity.platform.process.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.OK
    assert result.content == stdout.strip()
    assert result.usage is None
    assert result.metadata["output_format"] == "plain-text"
    assert result.metadata["machine_readable_output"] is False
    assert result.metadata["usage_source"] == "unsupported"


def test_parse_antigravity_log_extracts_conversation_and_model():
    parsed = parse_antigravity_log(
        'Print mode: conversation=9ab98524-1234\n'
        'Propagating selected model override to backend: label="Gemini 3.5 Flash (Medium)"\n'
        'backend=gemini-3-flash-a\n'
    )

    assert parsed["conversation_id"] == "9ab98524-1234"
    assert parsed["model_label"] == "Gemini 3.5 Flash (Medium)"
    assert parsed["backend_model"] == "gemini-3-flash-a"


@pytest.mark.asyncio
async def test_invoke_classifies_antigravity_auth_failure(tmp_path):
    invoker = AntigravityPrintInvoker()
    completed = subprocess.CompletedProcess(
        args=["agy"],
        returncode=1,
        stdout="",
        stderr="Please sign in with your Google account.",
    )

    with patch("trinity.platform.process.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.AUTH_REQUIRED
    assert "exit code 1" in result.content
    assert result.diagnostics == ["Please sign in with your Google account."]
    assert result.metadata["output_format"] == "plain-text"
    assert result.metadata["machine_readable_output"] is False
    assert result.metadata["usage_source"] == "unsupported"


@pytest.mark.asyncio
async def test_invoke_marks_empty_antigravity_output_with_diagnostic(tmp_path):
    invoker = AntigravityPrintInvoker()
    completed = subprocess.CompletedProcess(
        args=["agy"],
        returncode=0,
        stdout="",
        stderr="",
    )

    with patch("trinity.platform.process.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.EMPTY
    assert result.content == "[Empty response from Antigravity CLI]"
    assert result.raw_output == "[Empty response from Antigravity CLI]"
    assert "empty_response: Antigravity CLI returned empty output." in result.diagnostics
    assert any(item.startswith("antigravity_log_missing:") for item in result.diagnostics)
