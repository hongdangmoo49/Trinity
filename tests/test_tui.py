"""Tests for trinity.tui.app — TUI application components."""

import time

import pytest
from rich.console import Console

from trinity.config import TrinityConfig
from trinity.models import (
    AgentSpec,
    ConsensusResult,
    DeliberationResult,
    Provider,
    TaskAssignment,
)
from trinity.tui.app import AgentTUIState, AgentTUIStatus, RoundStatus, TrinityTUI


@pytest.fixture
def config():
    return TrinityConfig.default_config()


@pytest.fixture
def tui(config):
    return TrinityTUI(config, Console(force_terminal=True, width=120))


class TestAgentTUIStatus:
    def test_idle_icon(self):
        status = AgentTUIStatus(name="claude", provider="claude-code")
        assert status.state_icon == "⬜"

    def test_responding_icon(self):
        status = AgentTUIStatus(
            name="claude", provider="claude-code", state=AgentTUIState.RESPONDING
        )
        assert status.state_icon == "🔄"

    def test_responded_icon(self):
        status = AgentTUIStatus(
            name="claude", provider="claude-code", state=AgentTUIState.RESPONDED
        )
        assert status.state_icon == "✅"

    def test_error_icon(self):
        status = AgentTUIStatus(
            name="claude", provider="claude-code", state=AgentTUIState.ERROR
        )
        assert status.state_icon == "❌"

    def test_disabled_icon(self):
        status = AgentTUIStatus(
            name="codex", provider="codex", state=AgentTUIState.DISABLED
        )
        assert status.state_icon == "⏸️"

    def test_context_bar_green(self):
        status = AgentTUIStatus(name="claude", provider="claude-code", context_percent=30.0)
        bar = status.context_bar
        assert "30%" in bar

    def test_context_bar_yellow(self):
        status = AgentTUIStatus(name="claude", provider="claude-code", context_percent=65.0)
        bar = status.context_bar
        assert "65%" in bar

    def test_context_bar_red(self):
        status = AgentTUIStatus(name="claude", provider="claude-code", context_percent=85.0)
        bar = status.context_bar
        assert "85%" in bar

    def test_default_state(self):
        status = AgentTUIStatus(name="claude", provider="claude-code")
        assert status.state == AgentTUIState.IDLE
        assert status.response_preview == ""
        assert status.context_percent == 0.0

    def test_role_extraction(self):
        status = AgentTUIStatus(
            name="claude", provider="claude-code", role="You are the Architect"
        )
        assert status.role == "You are the Architect"


class TestTrinityTUI:
    def test_init_from_config(self, config):
        tui = TrinityTUI(config)
        assert "claude" in tui.agents
        assert "codex" in tui.agents
        assert "gemini" in tui.agents

    def test_agent_states_from_config(self, config):
        tui = TrinityTUI(config)
        # Claude is enabled by default
        assert tui.agents["claude"].state == AgentTUIState.IDLE
        # Codex/Gemini are disabled by default
        assert tui.agents["codex"].state == AgentTUIState.DISABLED
        assert tui.agents["gemini"].state == AgentTUIState.DISABLED

    def test_build_header(self, tui):
        panel = tui.build_header()
        assert panel is not None

    def test_build_agent_panel(self, tui):
        panel = tui.build_agent_panel()
        assert panel is not None

    def test_build_deliberation_panel_no_rounds(self, tui):
        panel = tui.build_deliberation_panel()
        assert panel is not None

    def test_build_result_panel_no_result(self, tui):
        panel = tui.build_result_panel()
        assert panel is None

    def test_build_result_panel_with_consensus(self, tui):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=2,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=2,
                total_agents=2,
                opinions={"claude": "yes", "codex": "yes"},
                summary="Use pytest.",
            ),
            total_tokens_used=1000,
            duration_seconds=5.0,
        )
        tui.set_result(result)
        panel = tui.build_result_panel()
        assert panel is not None

    def test_build_result_panel_no_consensus(self, tui):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=5,
            consensus=ConsensusResult(
                reached=False,
                agreement_count=1,
                total_agents=2,
                opinions={"claude": "yes", "codex": "no"},
            ),
            total_tokens_used=2000,
            duration_seconds=10.0,
        )
        tui.set_result(result)
        panel = tui.build_result_panel()
        assert panel is not None

    def test_build_layout(self, tui):
        layout = tui.build_layout()
        assert layout is not None

    def test_build_layout_with_result(self, tui):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "yes"},
                summary="Done.",
            ),
            tasks=[
                TaskAssignment(agent_name="claude", task_description="Write tests", priority=5),
            ],
        )
        tui.set_result(result)
        layout = tui.build_layout()
        assert layout is not None

    def test_update_agent_status(self, tui):
        tui.update_agent_status(
            "claude",
            state=AgentTUIState.RESPONDING,
            response_preview="Testing...",
            context_percent=42.0,
        )
        assert tui.agents["claude"].state == AgentTUIState.RESPONDING
        assert tui.agents["claude"].response_preview == "Testing..."
        assert tui.agents["claude"].context_percent == 42.0

    def test_update_agent_status_partial(self, tui):
        tui.update_agent_status("claude", state=AgentTUIState.RESPONDED)
        assert tui.agents["claude"].state == AgentTUIState.RESPONDED
        assert tui.agents["claude"].response_preview == ""  # Unchanged

    def test_update_agent_status_unknown_agent(self, tui):
        # Should not raise, just log warning
        tui.update_agent_status("nonexistent", state=AgentTUIState.RESPONDING)

    def test_start_round(self, tui):
        tui.start_round(1)
        assert tui.current_round == 1
        assert len(tui.rounds) == 1
        assert tui.rounds[0].round_num == 1
        # Claude should be RESPONDING (enabled)
        assert tui.rounds[0].agent_states.get("claude") == AgentTUIState.RESPONDING

    def test_mark_agent_responded(self, tui):
        tui.start_round(1)
        tui.mark_agent_responded("claude", "I recommend pytest")
        assert tui.agents["claude"].state == AgentTUIState.RESPONDED
        assert tui.agents["claude"].response_preview == "I recommend pytest"
        assert tui.rounds[0].agent_states["claude"] == AgentTUIState.RESPONDED

    def test_mark_consensus_checking(self, tui):
        tui.start_round(1)
        tui.mark_consensus_checking()
        assert tui.rounds[0].consensus == "checking"

    def test_mark_consensus_reached(self, tui):
        tui.start_round(1)
        tui.mark_consensus_result(True)
        assert tui.rounds[0].consensus == "reached"

    def test_mark_consensus_not_reached(self, tui):
        tui.start_round(1)
        tui.mark_consensus_result(False)
        assert tui.rounds[0].consensus == "not_reached"

    def test_set_result(self, tui):
        result = DeliberationResult(
            user_prompt="test question",
            rounds_completed=3,
            consensus=None,
            total_tokens_used=500,
            duration_seconds=2.5,
        )
        tui.set_result(result)
        assert tui.last_result is result
        assert len(tui.history) == 1
        assert tui.history[0]["prompt"] == "test question"
        assert tui.history[0]["rounds"] == 3
        assert tui.history[0]["consensus"] is False

    def test_reset_agents(self, tui):
        tui.update_agent_status("claude", state=AgentTUIState.RESPONDING)
        tui.reset_agents()
        assert tui.agents["claude"].state == AgentTUIState.IDLE

    def test_reset_agents_preserves_disabled(self, tui):
        tui.reset_agents()
        assert tui.agents["codex"].state == AgentTUIState.DISABLED
        assert tui.agents["gemini"].state == AgentTUIState.DISABLED

    def test_multiple_rounds(self, tui):
        for r in range(1, 4):
            tui.start_round(r)
            tui.mark_agent_responded("claude", f"Round {r} response")
            tui.mark_consensus_result(r == 3)

        assert len(tui.rounds) == 3
        assert tui.rounds[0].consensus == "not_reached"
        assert tui.rounds[1].consensus == "not_reached"
        assert tui.rounds[2].consensus == "reached"

    def test_get_welcome_text(self, tui):
        text = tui.get_welcome_text()
        assert "Trinity" in text
        assert "/status" in text
        assert "/quit" in text
        assert "/help" in text

    def test_result_with_tasks(self, tui):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=2,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=2,
                total_agents=2,
                opinions={"a": "yes", "b": "yes"},
                summary="Go.",
            ),
            tasks=[
                TaskAssignment(agent_name="claude", task_description="Design API", priority=10),
                TaskAssignment(agent_name="codex", task_description="Write code", priority=5),
            ],
        )
        tui.set_result(result)
        panel = tui.build_result_panel()
        assert panel is not None


class TestRoundStatus:
    def test_default_values(self):
        rs = RoundStatus(round_num=1)
        assert rs.round_num == 1
        assert rs.consensus == "waiting"
        assert rs.duration == 0.0
        assert rs.agent_states == {}

    def test_with_agent_states(self):
        rs = RoundStatus(
            round_num=2,
            agent_states={"claude": AgentTUIState.RESPONDED},
            consensus="reached",
        )
        assert rs.round_num == 2
        assert rs.agent_states["claude"] == AgentTUIState.RESPONDED
        assert rs.consensus == "reached"


class TestAgentTUIState:
    def test_values(self):
        assert AgentTUIState.IDLE.value == "idle"
        assert AgentTUIState.RESPONDING.value == "responding"
        assert AgentTUIState.RESPONDED.value == "responded"
        assert AgentTUIState.ERROR.value == "error"
        assert AgentTUIState.DISABLED.value == "disabled"

    def test_is_string_enum(self):
        assert isinstance(AgentTUIState.IDLE, str)
