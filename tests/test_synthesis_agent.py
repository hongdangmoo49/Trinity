"""Tests for central deliberation synthesis contracts."""

import json
from pathlib import Path

import pytest

from trinity.deliberation.synthesis import (
    FallbackSynthesisAgent,
    HeuristicSynthesisAgent,
    ModelBackedSynthesisAgent,
    SynthesisInput,
    SynthesisResult,
)
from trinity.models import ConsensusResult, ContextUsage, Provider, ResponseStatus
from trinity.providers.invoker import ProviderTurnResult


BLUEPRINT_TEXT = """\
BLUEPRINT:
Title: Route Bot
Summary: Finds bridge routes.

Architecture:
- Quote Collector: collects quotes

Data Flow:
- request -> quotes -> score

Acceptance Criteria:
- returns ranked paths

VOTE: APPROVE
"""


@pytest.mark.asyncio
async def test_heuristic_synthesis_reaches_structured_consensus():
    agent = HeuristicSynthesisAgent()

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": BLUEPRINT_TEXT},
        )
    )

    assert result.consensus_reached is True
    assert result.consensus is not None
    assert result.consensus.reached is True
    assert result.structured_consensus is not None
    assert result.recommended_blueprint is not None
    assert result.recommended_blueprint.title == "Route Bot"
    assert result.to_dict()["structured_consensus"]["reached"] is True


@pytest.mark.asyncio
async def test_heuristic_synthesis_surfaces_user_questions():
    agent = HeuristicSynthesisAgent()

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={
                "codex": """\
VOTE: BLOCKED_BY_QUESTION

OPEN QUESTIONS:
- Question: Optimize for cost or latency?
  Options: cost | latency | mixed
  Recommended: mixed
  Rationale: Changes route scoring.
"""
            },
        )
    )

    assert result.consensus_reached is False
    assert len(result.open_questions_for_user) == 1
    assert result.open_questions_for_user[0].question == (
        "Optimize for cost or latency?"
    )
    assert result.next_round_prompt == "Wait for user decisions before continuing."


@pytest.mark.asyncio
async def test_heuristic_synthesis_falls_back_to_keyword_consensus():
    agent = HeuristicSynthesisAgent()

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Choose framework",
            round_num=1,
            opinions={
                "claude": "I agree with using pytest.",
                "codex": "I agree too.",
            },
        )
    )

    assert result.consensus_reached is True
    assert result.structured_consensus is not None
    assert result.structured_consensus.reached is False
    assert result.consensus is not None
    assert result.consensus.summary.startswith("Consensus reached")


class BrokenSynthesisAgent:
    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        raise RuntimeError("provider synthesis unavailable")


class StaticFallbackAgent:
    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisResult:
        consensus = ConsensusResult(
            reached=True,
            agreement_count=1,
            total_agents=1,
            opinions={"fallback": "approved"},
            summary="Fallback approved.",
        )
        return SynthesisResult(
            round_num=synthesis_input.round_num,
            consensus_reached=True,
            agreement_count=1,
            total_agents=1,
            summary_for_shared_md=consensus.summary,
            consensus=consensus,
            source="static-fallback",
        )


@pytest.mark.asyncio
async def test_fallback_synthesis_agent_uses_fallback_on_primary_failure():
    agent = FallbackSynthesisAgent(
        primary=BrokenSynthesisAgent(),
        fallback=StaticFallbackAgent(),
    )

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=2,
            opinions={"claude": "anything"},
        )
    )

    assert result.consensus_reached is True
    assert result.source == "static-fallback"
    assert result.metadata["fallback_used"] is True
    assert result.diagnostics == [
        "primary synthesis failed: provider synthesis unavailable"
    ]


class FakeSynthesisInvoker:
    def __init__(self, result: ProviderTurnResult):
        self.result = result
        self.requests = []

    async def invoke(self, request):
        self.requests.append(request)
        return self.result


def _provider_result(
    payload: dict | str,
    status: ResponseStatus = ResponseStatus.OK,
    metadata: dict | None = None,
):
    content = json.dumps(payload) if isinstance(payload, dict) else payload
    return ProviderTurnResult(
        agent_name="codex",
        content=content,
        raw_output=content,
        status=status,
        elapsed_seconds=0.2,
        usage=ContextUsage(used=42, total=0),
        diagnostics=[] if status == ResponseStatus.OK else ["provider failed"],
        metadata=dict(metadata or {}),
    )


def _model_synthesis_agent(tmp_path: Path, result: ProviderTurnResult):
    invoker = FakeSynthesisInvoker(result)
    agent = ModelBackedSynthesisAgent(
        invoker=invoker,
        agent_name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        cwd=tmp_path,
        model="default",
        requested_model="fast",
        artifact_dir=tmp_path / "synthesis",
    )
    return agent, invoker


def _korean_model_synthesis_agent(tmp_path: Path, result: ProviderTurnResult):
    invoker = FakeSynthesisInvoker(result)
    agent = ModelBackedSynthesisAgent(
        invoker=invoker,
        agent_name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        cwd=tmp_path,
        model="default",
        requested_model="fast",
        artifact_dir=tmp_path / "synthesis",
        lang="ko",
    )
    return agent, invoker


def _valid_model_payload(**overrides):
    payload = {
        "consensus_reached": True,
        "agreement_count": 1,
        "total_agents": 1,
        "summary_for_shared_md": "Model selected a bridge route blueprint.",
        "next_round_prompt": "",
        "open_questions_for_user": [],
        "recommended_blueprint": {
            "title": "Route Bot",
            "summary": "Finds bridge routes across L2 chains.",
            "architecture": [
                {
                    "name": "Quote Collector",
                    "responsibility": "Collect bridge quotes.",
                }
            ],
            "data_flow": ["request -> quotes -> ranked routes"],
            "external_dependencies": ["Bridge APIs"],
            "risks": ["Provider rate limits"],
            "acceptance_criteria": ["returns ranked paths"],
            "open_questions": [],
        },
        "votes": {"claude": {"vote": "approve", "rationale": "Solid plan."}},
        "diagnostics": [],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_model_backed_synthesis_parses_valid_json_and_writes_artifacts(tmp_path):
    agent, invoker = _model_synthesis_agent(
        tmp_path,
        _provider_result(_valid_model_payload()),
    )

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": "Approved blueprint."},
        )
    )

    assert result.source == "model-backed"
    assert result.consensus_reached is True
    assert result.recommended_blueprint is not None
    assert result.recommended_blueprint.title == "Route Bot"
    assert result.metadata["provider"] == "codex"
    assert result.metadata["fallback_used"] is False
    assert Path(result.metadata["raw_output_path"]).exists()
    assert Path(result.metadata["json_path"]).exists()
    assert invoker.requests[0].access.value == "read-only"
    assert "Return exactly one JSON object" in invoker.requests[0].prompt


@pytest.mark.asyncio
async def test_model_backed_synthesis_payload_includes_target_workspace(tmp_path):
    agent, invoker = _model_synthesis_agent(
        tmp_path,
        _provider_result(_valid_model_payload()),
    )
    target = tmp_path / "route-bot"

    await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": "Approved blueprint."},
            target_workspace=str(target),
        )
    )

    prompt = invoker.requests[0].prompt
    payload = json.loads(prompt[prompt.index("{") :])
    assert payload["target_workspace"] == str(target)
    assert any("target_workspace is present" in rule for rule in payload["rules"])


@pytest.mark.asyncio
async def test_model_backed_synthesis_continues_provider_session_and_exposes_metadata(
    tmp_path,
):
    provider_session = {
        "provider": "codex",
        "agent_name": "central:codex",
        "session_key": "codex:central:codex:read-only",
        "provider_session_id": "thread-after",
        "session_kind": "codex_thread",
        "access": "read-only",
    }
    runtime_model = {
        "provider": "codex",
        "agent_name": "central:codex",
        "actual_model": "gpt-5",
    }
    invoker = FakeSynthesisInvoker(
        _provider_result(
            _valid_model_payload(),
            metadata={
                "provider_session": provider_session,
                "runtime_model": runtime_model,
            },
        )
    )
    agent = ModelBackedSynthesisAgent(
        invoker=invoker,
        agent_name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        cwd=tmp_path,
        model="gpt-5",
        requested_model="agent-default",
        artifact_dir=tmp_path / "synthesis",
        provider_session_agent_name="central:codex",
        provider_session_id="thread-before",
    )

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": "Approved blueprint."},
        )
    )

    request = invoker.requests[0]
    assert request.agent_name == "central:codex"
    assert request.provider_session_id == "thread-before"
    assert request.continuity_enabled is True
    assert result.metadata["provider_agent"] == "codex"
    assert result.metadata["provider_session_agent"] == "central:codex"
    assert result.metadata["provider_session"] == provider_session
    assert result.metadata["runtime_model"] == runtime_model


@pytest.mark.asyncio
async def test_model_backed_synthesis_parses_central_work_package_graph(tmp_path):
    payload = _valid_model_payload()
    payload["recommended_blueprint"]["work_packages"] = [
        {
            "id": "WP-010",
            "title": "Shared type contract",
            "owner_agent": "claude",
            "objective": "Define the shared interface before implementation.",
            "scope": "Document DTOs and ownership boundaries.",
            "dependencies": [],
            "expected_files": ["src/types/contracts.py"],
            "acceptance_criteria": ["contract is documented"],
            "estimated_weight": 2,
            "parallel_group": 1,
            "parallelizable": False,
            "risk": "high",
        },
        {
            "id": "WP-020",
            "title": "Adapter implementation",
            "owner_agent": "codex",
            "objective": "Implement the adapter against the shared contract.",
            "scope": ["Add adapter", "Add tests"],
            "dependencies": ["WP-010"],
            "expected_files": ["src/adapters/route_adapter.py"],
            "acceptance_criteria": ["adapter tests pass"],
            "estimated_weight": 3,
            "parallel_group": 2,
            "parallelizable": True,
            "risk": "medium",
        },
    ]
    agent, invoker = _model_synthesis_agent(tmp_path, _provider_result(payload))

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": "Approved blueprint."},
        )
    )

    assert result.recommended_blueprint is not None
    packages = result.recommended_blueprint.work_packages
    assert [package.id for package in packages] == ["WP-010", "WP-020"]
    assert packages[0].scope == ["Document DTOs and ownership boundaries."]
    assert packages[0].parallelizable is False
    assert packages[0].risk == "high"
    assert packages[1].dependencies == ["WP-010"]
    assert packages[1].parallel_group == 2
    assert "work_packages" in invoker.requests[0].prompt
    assert "wp_graph_guidance" in invoker.requests[0].prompt
    assert "narrowest relative files" in invoker.requests[0].prompt
    assert "serial_example" in invoker.requests[0].prompt


@pytest.mark.asyncio
async def test_model_backed_synthesis_ko_requests_korean_user_facing_values(tmp_path):
    agent, invoker = _korean_model_synthesis_agent(
        tmp_path,
        _provider_result(_valid_model_payload()),
    )

    await agent.synthesize(
        SynthesisInput(
            user_prompt="레이어2 브릿지 봇을 설계해라",
            round_num=1,
            opinions={"codex": "한국어 설계안"},
        )
    )

    request = invoker.requests[0]
    assert "All user-facing string values must be Korean" in request.role_prompt
    assert "All user-facing string values must be Korean" in request.prompt


@pytest.mark.asyncio
async def test_model_backed_synthesis_normalizes_open_questions_to_no_consensus(tmp_path):
    payload = _valid_model_payload(
        consensus_reached=True,
        open_questions_for_user=[
            {
                "id": "q-1",
                "question": "Optimize for cost or latency?",
                "options": "cost | latency | mixed",
                "recommended_option": "mixed",
                "blocking": True,
                "raised_by": "codex",
                "rationale": "Scoring depends on it.",
            }
        ],
    )
    agent, _ = _model_synthesis_agent(tmp_path, _provider_result(payload))

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": "Needs decision."},
        )
    )

    assert result.consensus_reached is False
    assert result.consensus is not None
    assert result.consensus.reached is False
    assert result.open_questions_for_user[0].options == ["cost", "latency", "mixed"]
    assert "open questions" in " ".join(result.diagnostics)


@pytest.mark.asyncio
async def test_model_backed_synthesis_invalid_json_falls_back(tmp_path):
    primary, _ = _model_synthesis_agent(tmp_path, _provider_result("not json"))
    agent = FallbackSynthesisAgent(primary=primary, fallback=StaticFallbackAgent())

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": "anything"},
        )
    )

    assert result.source == "static-fallback"
    assert result.metadata["fallback_used"] is True
    assert "no JSON object" in result.metadata["fallback_reason"]
    assert (tmp_path / "synthesis" / "round-01" / "synthesis.raw.txt").exists()


@pytest.mark.asyncio
async def test_model_backed_synthesis_provider_failure_falls_back(tmp_path):
    primary, _ = _model_synthesis_agent(
        tmp_path,
        _provider_result("", status=ResponseStatus.TIMEOUT),
    )
    agent = FallbackSynthesisAgent(primary=primary, fallback=StaticFallbackAgent())

    result = await agent.synthesize(
        SynthesisInput(
            user_prompt="Design route bot",
            round_num=1,
            opinions={"claude": "anything"},
        )
    )

    assert result.metadata["fallback_used"] is True
    assert "timeout" in result.metadata["fallback_reason"]
