"""Tests for Codex one-shot provider invoker."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from trinity.models import Provider, ResponseStatus
from trinity.providers.invoker import CodexExecInvoker, PromptRequest, parse_codex_jsonl
from trinity.providers.policy import ExecutionAuthority, InvocationAccess


def _request(tmp_path: Path) -> PromptRequest:
    return PromptRequest(
        agent_name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        role_prompt="You are the Implementer.",
        prompt="Summarize the repo.",
        cwd=tmp_path,
        model="gpt-5.1",
        extra_args=("--ignore-rules",),
    )


def test_build_command_uses_codex_exec_json_ephemeral(tmp_path):
    invoker = CodexExecInvoker()

    command = invoker.build_command(_request(tmp_path))

    assert command[:2] == ["codex", "exec"]
    assert "--json" in command
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--cd") + 1] == str(tmp_path)
    assert "--model" in command
    assert "gpt-5.1" in command
    assert "--ignore-rules" in command
    assert "[System Role]" in command[-1]
    assert "Summarize the repo." in command[-1]


def test_build_command_uses_workspace_write_when_requested(tmp_path):
    invoker = CodexExecInvoker()
    request = PromptRequest(
        agent_name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        prompt="Implement it.",
        cwd=tmp_path,
        access=InvocationAccess.WORKSPACE_WRITE,
    )

    command = invoker.build_command(request)

    assert command[command.index("--sandbox") + 1] == "workspace-write"


def test_parse_codex_jsonl_extracts_final_message_usage_and_tools():
    stdout = "\n".join(
        [
            '{"type":"thread.started","thread_id":"thread-1"}',
            '{"type":"turn.started"}',
            '{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"bash -lc ls","status":"in_progress"}}',
            '{"type":"item.completed","item":{"id":"item_1","type":"command_execution","status":"completed"}}',
            '{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"Repo contains src and tests."}}',
            '{"type":"turn.completed","usage":{"input_tokens":20,"output_tokens":5,"reasoning_output_tokens":2}}',
        ]
    )

    parsed = parse_codex_jsonl(stdout)

    assert parsed["content"] == "Repo contains src and tests."
    assert parsed["status"] == ResponseStatus.OK
    assert parsed["usage"].used == 27
    assert parsed["tool_activity_summary"] == ["command_execution:2"]


@pytest.mark.asyncio
async def test_invoke_parses_codex_jsonl_response(tmp_path):
    invoker = CodexExecInvoker()
    completed = subprocess.CompletedProcess(
        args=["codex"],
        returncode=0,
        stdout="\n".join(
            [
                '{"type":"item.completed","item":{"type":"agent_message","text":"Use one-shot invokers."}}',
                '{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":25}}',
            ]
        ),
        stderr="",
    )

    with patch("trinity.providers.invoker.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.OK
    assert result.content == "Use one-shot invokers."
    assert result.usage is not None
    assert result.usage.used == 125
    assert result.execution_authority == ExecutionAuthority.PROVIDER_MANAGED


@pytest.mark.asyncio
async def test_invoke_classifies_codex_auth_failure(tmp_path):
    invoker = CodexExecInvoker()
    completed = subprocess.CompletedProcess(
        args=["codex"],
        returncode=1,
        stdout="",
        stderr="Authentication required. Run codex login.",
    )

    with patch("trinity.providers.invoker.subprocess.run", return_value=completed):
        result = await invoker.invoke(_request(tmp_path))

    assert result.status == ResponseStatus.AUTH_REQUIRED
    assert "exit code 1" in result.content
    assert result.diagnostics == ["Authentication required. Run codex login."]
