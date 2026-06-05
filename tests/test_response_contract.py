"""Tests for structured provider response contract metadata."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.protocol import DeliberationProtocol
from trinity.models import (
    AgentResponse,
    AgentSpec,
    ContextUsage,
    DeliberationMessage,
    MessageRole,
    Provider,
    ResponseStatus,
)


def _agent(name: str = "claude") -> MagicMock:
    agent = MagicMock(spec=AgentWrapper)
    agent.name = name
    agent.spec = AgentSpec(
        name=name,
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
    )
    agent.context_usage = ContextUsage(used=100, total=200_000)
    return agent


def _message(name: str, content: str, metadata: dict | None = None) -> DeliberationMessage:
    return DeliberationMessage(
        source=name,
        target="all",
        round_num=0,
        role=MessageRole.OPINION,
        content=content,
        metadata=metadata or {},
    )


def test_agent_response_metadata_serializes_paths(tmp_path):
    response = AgentResponse(
        agent_name="claude",
        request_id="req-1",
        content="Use pytest.",
        raw_output_path=tmp_path / "raw.txt",
        clean_output_path=tmp_path / "clean.txt",
        status=ResponseStatus.OK,
        confidence=1.0,
        token_usage=ContextUsage(used=12, total=100),
        diagnostics=["ok"],
    )

    metadata = response.to_metadata()

    assert metadata["status"] == "ok"
    assert metadata["raw_output_path"].endswith("raw.txt")
    assert metadata["clean_output_path"].endswith("clean.txt")
    assert metadata["token_usage"]["used"] == 12
    assert metadata["diagnostics"] == ["ok"]


@pytest.mark.asyncio
async def test_collect_opinions_wraps_request_and_writes_response_artifacts(tmp_path):
    shared = SharedContextEngine(path=tmp_path / "shared.md")
    agent = _agent("claude")
    captured_prompt = {}

    async def send_and_wait(prompt: str, timeout: float = 120.0):
        captured_prompt["text"] = prompt
        return _message(
            "claude",
            "I agree with the scoped implementation.",
            metadata={
                "raw_output": f"{prompt}\nI agree with the scoped implementation.",
                "token_count": 17,
            },
        )

    agent.send_and_wait = AsyncMock(side_effect=send_and_wait)
    protocol = DeliberationProtocol(
        agents={"claude": agent},
        shared=shared,
        response_artifact_dir=tmp_path / "responses",
    )

    opinions = await protocol._collect_opinions(1, "Design the response contract.")

    prompt = captured_prompt["text"]
    msg = opinions["claude"]
    contract = msg.metadata["agent_response"]

    assert prompt.startswith("TRINITY_REQUEST_START ")
    assert "Design the response contract." in prompt
    assert "TRINITY_REQUEST_END " in prompt
    assert msg.metadata["response_status"] == "ok"
    assert contract["status"] == "ok"
    assert contract["request_id"] in prompt
    assert contract["token_usage"]["used"] == 17

    raw_path = contract["raw_output_path"]
    clean_path = contract["clean_output_path"]
    assert raw_path.endswith(".raw.txt")
    assert clean_path.endswith(".clean.txt")
    assert "TRINITY_REQUEST_START" in open(raw_path, encoding="utf-8").read()
    assert open(clean_path, encoding="utf-8").read() == (
        "I agree with the scoped implementation."
    )


@pytest.mark.asyncio
async def test_invalid_response_contract_status_excludes_shared_opinion(tmp_path):
    shared = SharedContextEngine(path=tmp_path / "shared.md")
    agent = _agent("antigravity")
    agent.send_and_wait = AsyncMock(
        return_value=_message(
            "antigravity",
            "Waiting for authentication.\nOpen the following URL to login.",
        )
    )
    protocol = DeliberationProtocol(
        agents={"antigravity": agent},
        shared=shared,
        max_rounds=1,
        response_artifact_dir=tmp_path / "responses",
    )

    result = await protocol.run("Need a design.")

    assert result.rounds_completed == 1
    assert not result.has_consensus
    assert shared.read_section("Round 1 Opinions") is None
    diagnostics = shared.read_section("Response Diagnostics")
    assert diagnostics is not None
    assert "classification: auth_wait" in diagnostics

    response_files = list((tmp_path / "responses" / "round-01").glob("*.clean.txt"))
    assert len(response_files) == 1
    clean_text = response_files[0].read_text(encoding="utf-8")
    assert "authentication" in clean_text
