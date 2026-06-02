"""Tests for TokenAnalytics — historical usage tracking and prediction."""
import pytest
from trinity.context.analytics import TokenAnalytics, RoundRecord

class TestRoundRecord:
    def test_creation(self):
        r = RoundRecord(round_num=1, agent_tokens={"claude": 500, "codex": 300}, prompt_tokens=200, duration_seconds=2.5)
        assert r.round_num == 1
        assert r.total_tokens == 800

    def test_total_tokens_sums_agents(self):
        r = RoundRecord(round_num=2, agent_tokens={"claude": 1000}, prompt_tokens=400, duration_seconds=5.0)
        assert r.total_tokens == 1000

    def test_average_tokens_per_agent(self):
        r = RoundRecord(round_num=1, agent_tokens={"claude": 600, "codex": 400}, prompt_tokens=200, duration_seconds=3.0)
        assert r.average_tokens_per_agent == 500.0

class TestTokenAnalytics:
    def test_record_and_get_history(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 500}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 600}, 150, 3.0))
        assert len(a.history) == 2

    def test_total_session_tokens(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 500}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 700}, 200, 3.0))
        assert a.total_session_tokens == 1200

    def test_average_tokens_per_round(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 400}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 600}, 200, 3.0))
        assert a.average_tokens_per_round == 500.0

    def test_agent_burn_rate(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 300, "codex": 200}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 500, "codex": 300}, 150, 3.0))
        assert a.agent_burn_rate("claude") == 400.0
        assert a.agent_burn_rate("codex") == 250.0

    def test_projected_depletion_rounds(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 40000}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 40000}, 150, 3.0))
        remaining = a.projected_remaining_rounds("claude", current_used=80000, total_budget=200000)
        assert remaining == 3.0

    def test_projected_depletion_unlimited(self):
        a = TokenAnalytics()
        assert a.projected_remaining_rounds("claude", 1000, 200000) == float("inf")

    def test_is_high_burn_session(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 50000}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 50000}, 150, 3.0))
        assert a.is_high_burn_session("claude", total_budget=200000) is True

    def test_is_not_high_burn_session(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 5000}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 5000}, 150, 3.0))
        assert a.is_high_burn_session("claude", total_budget=200000) is False

    def test_summary_dict(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 5000}, 200, 2.0))
        s = a.summary()
        assert "total_tokens" in s
        assert "rounds_recorded" in s
        assert "avg_tokens_per_round" in s
        assert s["rounds_recorded"] == 1

    def test_trend_increasing(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 1000}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 2000}, 200, 3.0))
        a.record(RoundRecord(3, {"claude": 3000}, 300, 4.0))
        assert a.trend() == "increasing"

    def test_trend_stable(self):
        a = TokenAnalytics()
        a.record(RoundRecord(1, {"claude": 1000}, 100, 2.0))
        a.record(RoundRecord(2, {"claude": 1050}, 100, 2.0))
        assert a.trend() == "stable"
