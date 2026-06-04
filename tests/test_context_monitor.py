"""Tests for trinity.context.monitor — ContextMonitor."""

import pytest
from unittest.mock import MagicMock

from trinity.agents.base import AgentWrapper
from trinity.context.monitor import ContextMonitor, ProviderContextLimits
from trinity.models import AgentSpec, ContextUsage, Provider


class FakeAgent:
    """A minimal fake agent that properly tracks context_usage updates."""

    def __init__(self, name: str, used: int, total: int = 200_000):
        self.name = name
        self.spec = AgentSpec(
            name=name,
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
        )
        self._context_usage = ContextUsage(used=used, total=total)

    @property
    def context_usage(self) -> ContextUsage:
        return self._context_usage

    def _update_usage(self, used: int, total: int | None = None) -> None:
        self._context_usage = ContextUsage(
            used=used,
            total=total if total is not None else self._context_usage.total,
        )


def _make_agent(name: str, used: int, total: int = 200_000) -> FakeAgent:
    return FakeAgent(name=name, used=used, total=total)


class TestProviderContextLimits:
    def test_default_limits(self):
        limits = ProviderContextLimits()
        assert limits.get_limit(Provider.CLAUDE_CODE) == 200_000
        assert limits.get_limit(Provider.CODEX) == 128_000
        assert limits.get_limit(Provider.ANTIGRAVITY_CLI) == 1_000_000
        assert limits.get_limit(Provider.GEMINI_CLI) == 1_000_000

    def test_unknown_provider_returns_default(self):
        limits = ProviderContextLimits()
        assert limits.get_limit("unknown") == 200_000


class TestContextMonitorCheckUsage:
    def test_no_rotation_needed(self):
        agents = {
            "claude": _make_agent("claude", 50_000),  # 25%
        }
        monitor = ContextMonitor(agents=agents, rotate_threshold=0.60)
        result = monitor.check_usage()
        assert result == []

    def test_rotation_needed_at_threshold(self):
        agents = {
            "claude": _make_agent("claude", 120_000),  # 60%
        }
        monitor = ContextMonitor(agents=agents, rotate_threshold=0.60)
        result = monitor.check_usage()
        assert "claude" in result

    def test_rotation_needed_above_threshold(self):
        agents = {
            "claude": _make_agent("claude", 150_000),  # 75%
        }
        monitor = ContextMonitor(agents=agents, rotate_threshold=0.60)
        result = monitor.check_usage()
        assert "claude" in result

    def test_multiple_agents_partial_rotation(self):
        agents = {
            "claude": _make_agent("claude", 150_000),  # 75% → needs rotation
            "codex": _make_agent("codex", 50_000),     # 25% → OK
        }
        monitor = ContextMonitor(agents=agents, rotate_threshold=0.60)
        result = monitor.check_usage()
        assert "claude" in result
        assert "codex" not in result

    def test_all_need_rotation(self):
        agents = {
            "claude": _make_agent("claude", 180_000),  # 90%
            "codex": _make_agent("codex", 100_000, 128_000),  # 78%
        }
        monitor = ContextMonitor(agents=agents, rotate_threshold=0.60)
        result = monitor.check_usage()
        assert len(result) == 2

    def test_custom_threshold(self):
        agents = {
            "claude": _make_agent("claude", 50_000),  # 25%
        }
        monitor = ContextMonitor(agents=agents, rotate_threshold=0.20)
        result = monitor.check_usage()
        assert "claude" in result  # 25% >= 20%

    def test_get_all_usage(self):
        agents = {
            "claude": _make_agent("claude", 100_000),
            "codex": _make_agent("codex", 50_000),
        }
        monitor = ContextMonitor(agents=agents)
        usage = monitor.get_all_usage()

        assert "claude" in usage
        assert "codex" in usage
        assert usage["claude"].used == 100_000
        assert usage["codex"].used == 50_000


class TestContextMonitorUpdateUsage:
    def test_update_usage(self):
        agents = {
            "claude": _make_agent("claude", 50_000),
        }
        monitor = ContextMonitor(agents=agents)
        monitor.update_usage("claude", used=150_000)

        assert agents["claude"].context_usage.used == 150_000

    def test_update_usage_with_total(self):
        agents = {
            "claude": _make_agent("claude", 50_000),
        }
        monitor = ContextMonitor(agents=agents)
        monitor.update_usage("claude", used=100_000, total=300_000)

        assert agents["claude"].context_usage.used == 100_000
        assert agents["claude"].context_usage.total == 300_000

    def test_update_nonexistent_agent(self):
        agents = {"claude": _make_agent("claude", 50_000)}
        monitor = ContextMonitor(agents=agents)
        # Should not crash
        monitor.update_usage("nonexistent", used=100)


class TestContextMonitorParseUsage:
    def test_parse_claude_json(self):
        agents = {"claude": _make_agent("claude", 0)}
        monitor = ContextMonitor(agents=agents)

        monitor.parse_usage_from_claude_json("claude", {
            "result": "Hello",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })
        assert agents["claude"].context_usage.used == 150

    def test_parse_claude_json_empty_usage(self):
        agents = {"claude": _make_agent("claude", 0)}
        monitor = ContextMonitor(agents=agents)

        monitor.parse_usage_from_claude_json("claude", {"result": "Hello"})
        # Should not update (no usage data)
        assert agents["claude"].context_usage.used == 0

    def test_parse_codex_session(self):
        agents = {"codex": _make_agent("codex", 0)}
        monitor = ContextMonitor(agents=agents)

        monitor.parse_usage_from_codex_session("codex", {
            "usage": {"total_tokens": 5000},
        })
        assert agents["codex"].context_usage.used == 5000

    def test_parse_gemini_output(self):
        agents = {"gemini": _make_agent("gemini", 0)}
        monitor = ContextMonitor(agents=agents)

        monitor.parse_usage_from_gemini_output(
            "gemini",
            "Response text\nToken count: 8000",
        )
        assert agents["gemini"].context_usage.used == 8000

    def test_parse_gemini_output_no_tokens(self):
        agents = {"gemini": _make_agent("gemini", 0)}
        monitor = ContextMonitor(agents=agents)

        monitor.parse_usage_from_gemini_output(
            "gemini",
            "Just a response with no token info",
        )
        assert agents["gemini"].context_usage.used == 0
