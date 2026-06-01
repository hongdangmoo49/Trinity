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


class TestConsensusWithNegationInMultiAgent:
    """Test multi-agent scenarios with negation filtering."""

    def test_disagree_false_positive_eliminated(self):
        """The original bug: 'disagree' matched 'agree' keyword."""
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I think we should use JWT.",
            "codex": "I disagree, sessions are better.",
            "gemini": "OAuth is the modern standard.",
        }
        result = engine.evaluate(opinions)
        # codex's "disagree" should NOT count → 0/3 → no consensus
        assert not result.reached

    def test_two_agree_one_disagrees_with_consensus(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I agree with the plan.",
            "codex": "I agree too.",
            "gemini": "I disagree with the timeline.",
        }
        result = engine.evaluate(opinions)
        assert result.reached  # 2/3 = 0.67 ≥ 0.6

    def test_all_disagree(self):
        engine = ConsensusEngine(required_fraction=0.6)
        opinions = {
            "claude": "I disagree with option A.",
            "codex": "I don't agree either.",
            "gemini": "I oppose this plan.",
        }
        result = engine.evaluate(opinions)
        assert not result.reached
        assert result.agreement_count == 0
