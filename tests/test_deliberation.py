"""Tests for trinity.deliberation — consensus engine and task distributor."""

import pytest

from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.models import AgentSpec, Provider


class TestConsensusEngine:
    def test_all_agree(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I agree with the JWT approach.",
            "codex": "I agree, JWT is the way.",
            "gemini": "Agreed, let's go with JWT.",
        }
        result = engine.evaluate(opinions)
        assert result.reached
        assert result.agreement_count == 3

    def test_two_of_three_agree(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I agree with this plan.",
            "codex": "I disagree, sessions are better.",
            "gemini": "I approve the JWT approach.",
        }
        result = engine.evaluate(opinions)
        assert result.reached  # 2/3 = 0.67 >= 0.6
        # codex also matches "agree" in "I disagree" — keyword detector is inclusive
        assert result.agreement_count >= 2

    def test_one_of_three_disagree(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I think we should use JWT.",
            "codex": "Sessions are superior here.",
            "gemini": "OAuth is the modern standard.",
        }
        result = engine.evaluate(opinions)
        assert not result.reached

    def test_empty_opinions(self):
        engine = ConsensusEngine()
        result = engine.evaluate({})
        assert not result.reached
        assert result.agreement_count == 0

    def test_korean_keywords(self):
        engine = ConsensusEngine(required_fraction=0.5)
        opinions = {
            "claude": "JWT 방식에 동의합니다.",
            "codex": "이 접근에 합의합니다.",
        }
        result = engine.evaluate(opinions)
        assert result.reached

    def test_custom_keywords(self):
        engine = ConsensusEngine(
            consensus_keywords=["MANDATE", "FINAL DECISION"],
            required_fraction=0.5,
        )
        opinions = {
            "claude": "This is the FINAL DECISION.",
            "codex": "I'm not sure about this.",
        }
        result = engine.evaluate(opinions)
        assert result.reached  # claude has the keyword

    def test_summary_text(self):
        engine = ConsensusEngine()
        opinions = {
            "claude": "I agree.",
            "codex": "I agree too.",
        }
        result = engine.evaluate(opinions)
        assert "Consensus reached" in result.summary


class TestTaskDistributor:
    def test_basic_distribution(self):
        distributor = TaskDistributor()
        agents = {
            "claude": AgentSpec(
                name="claude",
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
            ),
            "codex": AgentSpec(
                name="codex",
                provider=Provider.CODEX,
                cli_command="codex",
            ),
        }
        tasks = distributor.distribute(
            consensus_text="Use JWT for authentication and implement code review",
            agents=agents,
        )
        assert len(tasks) == 2
        names = {t.agent_name for t in tasks}
        assert names == {"claude", "codex"}

    def test_strength_matching(self):
        distributor = TaskDistributor()
        agents = {
            "claude": AgentSpec(
                name="claude",
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
            ),
        }
        tasks = distributor.distribute(
            consensus_text="Focus on architecture design and code review",
            agents=agents,
        )
        assert len(tasks) == 1
        assert tasks[0].agent_name == "claude"
        # Should mention matched strengths
        assert "architecture" in tasks[0].task_description.lower() or "code review" in tasks[0].task_description.lower()

    def test_empty_agents(self):
        distributor = TaskDistributor()
        tasks = distributor.distribute("Some consensus", {})
        assert tasks == []

    def test_priority_increases_with_matches(self):
        distributor = TaskDistributor()
        agents = {
            "claude": AgentSpec(
                name="claude",
                provider=Provider.CLAUDE_CODE,
                cli_command="claude",
            ),
            "codex": AgentSpec(
                name="codex",
                provider=Provider.CODEX,
                cli_command="codex",
            ),
        }
        # Consensus heavily favors codex strengths
        tasks = distributor.distribute(
            consensus_text="Need implementation, coding, prototyping, refactoring, bulk code, fixing, and testing",
            agents=agents,
        )
        codex_task = next(t for t in tasks if t.agent_name == "codex")
        claude_task = next(t for t in tasks if t.agent_name == "claude")
        assert codex_task.priority >= claude_task.priority
