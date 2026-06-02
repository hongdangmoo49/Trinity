"""Tests for trinity.models dataclasses."""

import pytest

from trinity.models import (
    AgentSpec,
    AgentHealth,
    ConsensusResult,
    ContextUsage,
    DeliberationMessage,
    DeliberationResult,
    MessageRole,
    model_context_budget,
    Provider,
    provider_default_budget,
    provider_model_choices,
    TaskAssignment,
    TaskIntent,
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

    def test_model_context_budget_overrides_provider_default(self):
        spec = AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            model="opus[1m]",
        )
        assert spec.effective_context_budget == 1_000_000

    def test_explicit_context_budget_wins_over_model_budget(self):
        spec = AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            model="opus[1m]",
            context_budget=750_000,
        )
        assert spec.effective_context_budget == 750_000


class TestModelRegistry:
    def test_provider_model_choices_include_claude_1m(self):
        choices = provider_model_choices(Provider.CLAUDE_CODE)
        assert any(choice.model == "opus[1m]" for choice in choices)

    def test_model_context_budget_known_model(self):
        assert model_context_budget(Provider.CODEX, "gpt-5.1") == 400_000

    def test_model_context_budget_unknown_model(self):
        assert model_context_budget(Provider.CODEX, "custom-model") is None

    def test_provider_default_budget_preserves_existing_defaults(self):
        assert provider_default_budget(Provider.CLAUDE_CODE) == 200_000
        assert provider_default_budget(Provider.CODEX) == 128_000
        assert provider_default_budget(Provider.GEMINI_CLI) == 1_000_000


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


class TestTaskAssignment:
    def test_defaults_to_plan_metadata(self):
        task = TaskAssignment(agent_name="claude", task_description="Plan next steps")
        assert task.intent == TaskIntent.PLAN
        assert not task.requires_execution
        assert not task.design_only

    def test_design_only_property(self):
        task = TaskAssignment(
            agent_name="claude",
            task_description="Design API",
            intent=TaskIntent.DESIGN_ONLY,
        )
        assert task.design_only


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
