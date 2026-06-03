"""Tests for StructuredConsensusEngine — explicit VOTE:-based consensus."""

import pytest

from trinity.deliberation.consensus import StructuredConsensusEngine
from trinity.models import VoteType


# ======================================================================
# Vote extraction
# ======================================================================


class TestStructuredVoteExtraction:
    """Test that extract_vote correctly parses VOTE: lines."""

    def setup_method(self):
        self.engine = StructuredConsensusEngine()

    def test_approve_detected(self):
        text = "The design looks solid.\nVOTE: APPROVE"
        assert self.engine.extract_vote(text) == VoteType.APPROVE

    def test_approve_with_changes(self):
        text = "Mostly good but needs tweaks.\nVOTE: APPROVE_WITH_CHANGES"
        assert self.engine.extract_vote(text) == VoteType.APPROVE_WITH_CHANGES

    def test_blocked_by_question(self):
        text = "I have concerns.\nVOTE: BLOCKED_BY_QUESTION\nWhat about X?"
        assert self.engine.extract_vote(text) == VoteType.BLOCKED_BY_QUESTION

    def test_reject(self):
        text = "This approach is flawed.\nVOTE: REJECT"
        assert self.engine.extract_vote(text) == VoteType.REJECT

    def test_no_vote_defaults_to_approve_with_changes(self):
        text = "I think the plan is good but forgot to cast a vote."
        assert self.engine.extract_vote(text) == VoteType.APPROVE_WITH_CHANGES

    def test_korean_approve(self):
        text = "좋은 설계입니다.\n투표: 승인"
        assert self.engine.extract_vote(text) == VoteType.APPROVE


# ======================================================================
# Consensus evaluation
# ======================================================================


class TestStructuredConsensusEvaluation:
    """Test evaluate_structured with various agent vote scenarios."""

    def setup_method(self):
        self.engine = StructuredConsensusEngine()

    def test_all_approve_reaches_consensus(self):
        opinions = {
            "claude": "Great plan.\nVOTE: APPROVE",
            "codex": "Looks good.\nVOTE: APPROVE",
            "gemini": "No issues.\nVOTE: APPROVE",
        }
        result = self.engine.evaluate_structured(opinions)
        assert result.reached is True
        assert result.vote_count["approve"] == 3
        assert len(result.blockers) == 0
        assert len(result.open_questions) == 0

    def test_two_approve_one_reject_no_consensus(self):
        opinions = {
            "claude": "Vits good.\nVOTE: APPROVE",
            "codex": "Nice.\nVOTE: APPROVE",
            "gemini": "Bad idea.\nVOTE: REJECT",
        }
        result = self.engine.evaluate_structured(opinions)
        assert result.reached is False
        assert len(result.blockers) == 1
        assert "gemini: rejected the design" in result.blockers

    def test_blocked_by_question_produces_open_questions(self):
        opinions = {
            "claude": "VOTE: APPROVE",
            "codex": "VOTE: BLOCKED_BY_QUESTION\nShould we use REST or gRPC?",
            "gemini": "VOTE: APPROVE",
        }
        result = self.engine.evaluate_structured(opinions)
        assert result.reached is False
        assert len(result.open_questions) == 1
        assert result.open_questions[0].question == "Should we use REST or gRPC?"
        assert result.open_questions[0].raised_by == ["codex"]

    def test_single_agent_approve_is_consensus(self):
        opinions = {
            "claude": "Everything checks out.\nVOTE: APPROVE",
        }
        result = self.engine.evaluate_structured(opinions)
        assert result.reached is True

    def test_single_agent_reject_no_consensus(self):
        opinions = {
            "claude": "This is wrong.\nVOTE: REJECT",
        }
        result = self.engine.evaluate_structured(opinions)
        assert result.reached is False
        assert len(result.blockers) == 1
