"""Tests for consensus engine v2 — negation-aware agreement detection."""

import pytest

from trinity.deliberation.consensus import ConsensusEngine


class TestNegationFiltering:
    """Test that negated agreement keywords are properly filtered."""

    def test_disagree_not_counted_as_agree(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I disagree with this approach.",
        }
        result = engine.evaluate(opinions)
        assert not result.reached
        assert result.agreement_count == 0

    def test_dont_agree_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I don't agree with the proposal.",
        }
        result = engine.evaluate(opinions)
        assert not result.reached
        assert result.agreement_count == 0

    def test_do_not_agree_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I do not agree.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 0

    def test_not_agree_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "We can not agree on this.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 0

    def test_mixed_negation_and_agreement(self):
        """Agent disagrees on one point but agrees on another."""
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I disagree with the database choice. However, I agree with the API design.",
        }
        result = engine.evaluate(opinions)
        # Should detect the positive agreement in the second sentence
        assert result.agreement_count == 1

    def test_oppose_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I oppose this plan.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 0

    def test_against_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I am against this proposal.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 0

    def test_pure_agreement_still_works(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I agree with this approach.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 1

    def test_korean_agreement(self):
        engine = ConsensusEngine(required_fraction=0.5)
        opinions = {
            "claude": "이 방안에 동의합니다.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 1


class TestKoreanNegation:
    """Test Korean negation patterns in consensus evaluation."""

    def test_korean_disagree_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "a": "I agree with this approach.",
            "b": "동의하지 않습니다. 다른 방법이 필요합니다.",
            "c": "I agree too.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 2

    def test_korean_oppose_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "a": "이 방안에 반대합니다.",
            "b": "I agree.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 1

    def test_korean_cannot_agree_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "a": "동의할 수 없습니다.",
            "b": "I agree.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 1

    def test_korean_reject_not_counted(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "a": "이 제안을 거부합니다.",
        }
        result = engine.evaluate(opinions)
        assert result.agreement_count == 0


class TestConsensusWithNegationInMultiAgent:
    """Test multi-agent scenarios with negation filtering."""

    def test_disagree_false_positive_eliminated(self):
        """The original bug: 'disagree' matched 'agree' keyword."""
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I think we should use JWT.",
            "codex": "I disagree, sessions are better.",
            "antigravity": "OAuth is the modern standard.",
        }
        result = engine.evaluate(opinions)
        # codex's "disagree" should NOT count → 0/3 → no consensus
        assert not result.reached

    def test_two_agree_one_disagrees_with_consensus(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I agree with the plan.",
            "codex": "I agree too.",
            "antigravity": "I disagree with the timeline.",
        }
        result = engine.evaluate(opinions)
        assert result.reached  # 2/3 = 0.67 ≥ 0.6

    def test_all_disagree(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I disagree with option A.",
            "codex": "I don't agree either.",
            "antigravity": "I oppose this plan.",
        }
        result = engine.evaluate(opinions)
        assert not result.reached
        assert result.agreement_count == 0


class TestUnusableOpinionFiltering:
    """Test that unusable captured responses are excluded from consensus math."""

    def test_invalid_response_placeholder_excluded_from_total(self):
        engine = ConsensusEngine(required_fraction=1.0)
        opinions = {
            "claude": "I agree with the plan.",
            "antigravity": "[Invalid response omitted: auth_wait]",
        }

        result = engine.evaluate(opinions)

        assert result.reached
        assert result.agreement_count == 1
        assert result.total_agents == 1
        assert result.opinions == {"claude": "I agree with the plan."}

    def test_all_unusable_responses_have_no_usable_consensus(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "codex": "[Timeout after 120s]",
            "antigravity": "[Invalid response omitted: auth_wait]",
        }

        result = engine.evaluate(opinions)

        assert not result.reached
        assert result.agreement_count == 0
        assert result.total_agents == 0
        assert result.opinions == {}
        assert "No usable consensus" in result.summary
