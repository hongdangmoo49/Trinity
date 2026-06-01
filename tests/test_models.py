"""Tests for trinity.models dataclasses."""

import time

import pytest

from trinity.models import (
    AgentSpec,
    AgentHealth,
    ConsensusResult,
    ContextUsage,
    DeliberationMessage,
    DeliberationResult,
    MessageRole,
    Provider,
    TaskAssignment,
)


class TestAgentSpec:
    def test_default_values(self):
        spec = AgentSpec(name="claude", provider=Provider.CLAUDE_CODE, cli_command="claude")
        assert spec.workspace_mode == "inplace"
        assert spec.enabled is True
        assert spec.context_budget == 0

    def test_effective_context_budget_explicit(self):
        spec = AgentSpec(
            name="test",
            provider=Provider.CLAUDE_CODE,
            cli_command="test",
            context_budget=100_000,
        )
        assert spec.effective_context_budget == 100_000

    def test_effective_context_budget_auto_claude(self):
        spec = AgentSpec(name="claude", provider=Provider.CLAUDE_CODE, cli_command="claude")
        assert spec.effective_context_budget == 200_000

    def test_effective_context_budget_auto_codex(self):
        spec = AgentSpec(name="codex", provider=Provider.CODEX, cli_command="codex")
        assert spec.effective_context_budget == 128_000

    def test_effective_context_budget_auto_gemini(self):
        spec = AgentSpec(name="gemini", provider=Provider.GEMINI_CLI, cli_command="gemini")
        assert spec.effective_context_budget == 1_000_000


class TestContextUsage:
    def test_zero_usage(self):
        usage = ContextUsage(used=0, total=200_000)
        assert usage.ratio == 0.0
        assert not usage.should_rotate
        assert usage.remaining == 200_000

    def test_at_threshold(self):
        usage = ContextUsage(used=120_000, total=200_000)
        assert usage.ratio == 0.6
        assert usage.should_rotate  # >= 0.60

    def test_above_threshold(self):
        usage = ContextUsage(used=150_000, total=200_000)
        assert usage.ratio == 0.75
        assert usage.should_rotate

    def test_below_threshold(self):
        usage = ContextUsage(used=100_000, total=200_000)
        assert usage.ratio == 0.5
        assert not usage.should_rotate

    def test_str_format(self):
        usage = ContextUsage(used=100_000, total=200_000)
        s = str(usage)
        assert "100,000" in s
        assert "200,000" in s
        assert "50.0%" in s


class TestDeliberationMessage:
    def test_creation(self):
        msg = DeliberationMessage(
            source="claude",
            target="all",
            round_num=1,
            role=MessageRole.OPINION,
            content="JWT is the way to go.",
        )
        assert msg.source == "claude"
        assert msg.role == MessageRole.OPINION
        assert msg.token_count == 0  # default from metadata
        assert msg.timestamp > 0

    def test_with_metadata(self):
        msg = DeliberationMessage(
            source="codex",
            target="all",
            round_num=2,
            role=MessageRole.COUNTER,
            content="I disagree.",
            metadata={"token_count": 150},
        )
        assert msg.token_count == 150


class TestConsensusResult:
    def test_consensus_reached(self):
        result = ConsensusResult(
            reached=True,
            agreement_count=2,
            total_agents=3,
            opinions={"a": "agree", "b": "agree", "c": "no"},
        )
        assert result.reached
        assert result.fraction == pytest.approx(2 / 3)

    def test_no_consensus(self):
        result = ConsensusResult(
            reached=False,
            agreement_count=1,
            total_agents=3,
            opinions={"a": "agree", "b": "no", "c": "no"},
        )
        assert not result.reached


class TestDeliberationResult:
    def test_has_consensus(self):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=2,
            consensus=ConsensusResult(
                reached=True, agreement_count=2, total_agents=2, opinions={}
            ),
        )
        assert result.has_consensus

    def test_no_consensus(self):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=5,
            consensus=None,
        )
        assert not result.has_consensus


class TestAgentHealth:
    def test_healthy_agent(self):
        health = AgentHealth(name="claude", alive=True, context_ratio=0.3)
        assert health.alive
        assert not health.context_warning

    def test_context_warning(self):
        health = AgentHealth(name="claude", alive=True, context_ratio=0.65)
        assert health.context_warning
