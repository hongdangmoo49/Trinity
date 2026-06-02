"""Tests for TokenBudgetChecker."""
import pytest
from trinity.context.budget import TokenBudgetChecker
from trinity.models import AgentSpec, ContextUsage, Provider

def _spec():
    return AgentSpec(name="claude", provider=Provider.CLAUDE_CODE, cli_command="claude")

class TestTokenBudgetChecker:
    def test_check_safe_prompt(self):
        checker = TokenBudgetChecker()
        result = checker.check("Short.", ContextUsage(used=1000, total=200_000), _spec())
        assert result.safe is True
        assert result.estimated_prompt_tokens > 0
        assert result.projected_ratio < 0.6

    def test_check_dangerous_prompt(self):
        checker = TokenBudgetChecker(threshold=0.60)
        result = checker.check("x " * 5000, ContextUsage(used=110_000, total=200_000), _spec())
        assert result.safe is False

    def test_check_with_margin(self):
        checker = TokenBudgetChecker(threshold=0.60, safety_margin=0.05)
        result = checker.check("x " * 5000, ContextUsage(used=104_000, total=200_000), _spec())
        assert result.safe is False

    def test_estimate_prompt_tokens(self):
        checker = TokenBudgetChecker()
        tokens = checker.estimate_prompt_tokens("Hello world test.")
        assert tokens > 0

    def test_get_recommendation(self):
        checker = TokenBudgetChecker()
        r1 = checker.check("short", ContextUsage(used=10_000, total=200_000), _spec())
        assert r1.recommendation == "proceed"
        r2 = checker.check("x " * 5000, ContextUsage(used=115_000, total=200_000), _spec())
        assert r2.recommendation == "rotate_first"
        r3 = checker.check("x " * 5000, ContextUsage(used=100_000, total=200_000), _spec())
        assert r3.recommendation == "proceed_with_caution"
