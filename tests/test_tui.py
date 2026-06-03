"""Tests for trinity.tui.app — TUI application components."""

import pytest
from rich.console import Console

from trinity.config import TrinityConfig
from trinity.models import (
    ConsensusResult,
    DeliberationResult,
    TaskAssignment,
)
from trinity.tui.app import AgentTUIState, AgentTUIStatus, RoundStatus, TrinityTUI
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.tui.theme import AgentTheme, get_theme
from trinity.workflow import OpenQuestion, WorkPackage, WorkflowSession, WorkflowState


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
        assert status.full_response == ""
        assert status.context_percent == 0.0

    def test_role_extraction(self):
        status = AgentTUIStatus(
            name="claude", provider="claude-code", role="You are the Architect"
        )
        assert status.role == "You are the Architect"

    def test_full_response_default(self):
        status = AgentTUIStatus(name="claude", provider="claude-code")
        assert status.full_response == ""


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

    def test_consume_execution_events_updates_package_statuses(self, tui):
        tui.consume_event(
            TUIEvent(
                type=TUIEventType.EXECUTION_START,
                data={"package_count": 1},
            )
        )
        tui.consume_event(
            TUIEvent(
                type=TUIEventType.WORK_PACKAGE_STARTED,
                data={"package_id": "WP-001", "status": "running"},
            )
        )
        assert tui.work_package_count == 1
        assert tui.work_package_statuses["WP-001"] == "running"

        tui.consume_event(
            TUIEvent(
                type=TUIEventType.WORK_PACKAGE_COMPLETED,
                data={"package_id": "WP-001", "status": "done"},
            )
        )

        assert tui.work_package_statuses["WP-001"] == "done"
        assert tui._work_package_summary() == "1/1 done"

    def test_set_workflow_session_tracks_package_statuses(self, tui):
        session = WorkflowSession(
            id="wf-001",
            goal="Implement",
            state=WorkflowState.EXECUTING,
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="codex package",
                    owner_agent="codex",
                    objective="Implement.",
                )
            ],
        )

        tui.set_workflow_session(session)

        assert tui.work_package_count == 1
        assert tui.work_package_statuses == {"WP-001": "pending"}

    def test_set_workflow_session(self, tui):
        session = WorkflowSession(
            id="wf-001",
            goal="Design",
            state=WorkflowState.NEEDS_USER_DECISION,
            pending_questions=[
                OpenQuestion(id="q-001", question="Choose mode?"),
            ],
        )

        tui.set_workflow_session(session)

        assert tui.workflow_id == "wf-001"
        assert tui.workflow_goal == "Design"
        assert tui.workflow_state == WorkflowState.NEEDS_USER_DECISION
        assert tui.pending_question_count == 1

    def test_reset_agents(self, tui):
        tui.update_agent_status("claude", state=AgentTUIState.RESPONDING)
        tui.reset_agents()
        assert tui.agents["claude"].state == AgentTUIState.IDLE
        assert tui.agents["claude"].full_response == ""

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


class TestConsumeEvent:
    """Tests for the consume_event() method — real-time event processing."""

    def test_round_start_event(self, tui):
        event = TUIEvent(type=TUIEventType.ROUND_START, data={"round_num": 1})
        tui.consume_event(event)
        assert tui.current_round == 1
        assert len(tui.rounds) == 1
        assert tui.agents["claude"].state == AgentTUIState.RESPONDING

    def test_agent_thinking_event(self, tui):
        event = TUIEvent(
            type=TUIEventType.AGENT_THINKING,
            data={"agent": "claude", "round_num": 1},
        )
        tui.consume_event(event)
        assert tui.agents["claude"].state == AgentTUIState.RESPONDING

    def test_agent_responded_event(self, tui):
        # Start a round first
        tui.start_round(1)
        event = TUIEvent(
            type=TUIEventType.AGENT_RESPONDED,
            data={"agent": "claude", "content": "I recommend pytest.", "round_num": 1},
        )
        tui.consume_event(event)
        assert tui.agents["claude"].state == AgentTUIState.RESPONDED
        assert tui.agents["claude"].full_response == "I recommend pytest."
        assert tui.rounds[0].agent_opinions["claude"] == "I recommend pytest."

    def test_agent_error_event(self, tui):
        tui.start_round(1)
        event = TUIEvent(
            type=TUIEventType.AGENT_ERROR,
            data={"agent": "claude", "error": "timeout", "round_num": 1},
        )
        tui.consume_event(event)
        assert tui.agents["claude"].state == AgentTUIState.ERROR
        assert "timeout" in tui.rounds[0].agent_opinions["claude"]

    def test_provider_readiness_not_ready_event(self, tui):
        event = TUIEvent(
            type=TUIEventType.PROVIDER_READINESS,
            data={
                "agent": "claude",
                "provider": "claude-code",
                "ready": False,
                "state": "auth_required",
                "reason": "claude-code requires authentication",
                "action_hint": "Run `claude` in a terminal.",
                "excerpt": "OAuth URL",
            },
        )

        tui.consume_event(event)

        status = tui.agents["claude"]
        assert status.state == AgentTUIState.NOT_READY
        assert status.readiness_state == "auth_required"
        assert "authentication" in status.readiness_reason
        assert "OAuth URL" in status.full_response

    def test_start_round_skips_not_ready_agents(self, tui):
        tui.mark_provider_readiness(
            name="claude",
            ready=False,
            readiness_state="auth_required",
            reason="login required",
            action_hint="Run `claude`.",
            excerpt="OAuth URL",
        )

        tui.start_round(1)

        assert "claude" not in tui.rounds[0].agent_states
        assert tui.agents["claude"].state == AgentTUIState.NOT_READY

    def test_consensus_checking_event(self, tui):
        tui.start_round(1)
        event = TUIEvent(type=TUIEventType.CONSENSUS_CHECKING, data={"round_num": 1})
        tui.consume_event(event)
        assert tui.rounds[0].consensus == "checking"

    def test_consensus_result_reached_event(self, tui):
        tui.start_round(1)
        event = TUIEvent(
            type=TUIEventType.CONSENSUS_RESULT,
            data={"reached": True, "agreement_count": 2, "total_agents": 3, "summary": "OK"},
        )
        tui.consume_event(event)
        assert tui.rounds[0].consensus == "reached"
        assert "2/3" in tui.rounds[0].consensus_detail

    def test_consensus_result_not_reached_event(self, tui):
        tui.start_round(1)
        event = TUIEvent(
            type=TUIEventType.CONSENSUS_RESULT,
            data={"reached": False, "agreement_count": 1, "total_agents": 3, "summary": ""},
        )
        tui.consume_event(event)
        assert tui.rounds[0].consensus == "not_reached"
        assert "1/3" in tui.rounds[0].consensus_detail

    def test_deliberation_done_event(self, tui):
        event = TUIEvent(type=TUIEventType.DELIBERATION_DONE, data={})
        # Should not raise
        tui.consume_event(event)

    def test_full_event_sequence(self, tui):
        """Simulate a complete deliberation event sequence."""
        events = [
            TUIEvent(type=TUIEventType.ROUND_START, data={"round_num": 1}),
            TUIEvent(type=TUIEventType.AGENT_THINKING, data={"agent": "claude", "round_num": 1}),
            TUIEvent(
                type=TUIEventType.AGENT_RESPONDED,
                data={"agent": "claude", "content": "Use pytest", "round_num": 1},
            ),
            TUIEvent(type=TUIEventType.CONSENSUS_CHECKING, data={"round_num": 1}),
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={"reached": True, "agreement_count": 1, "total_agents": 1, "summary": "OK"},
            ),
            TUIEvent(type=TUIEventType.DELIBERATION_DONE, data={}),
        ]
        for event in events:
            tui.consume_event(event)

        assert len(tui.rounds) == 1
        assert tui.rounds[0].consensus == "reached"
        assert tui.rounds[0].agent_opinions["claude"] == "Use pytest"
        assert tui.agents["claude"].full_response == "Use pytest"

    def test_deliberation_panel_with_opinions_renders(self, tui):
        """Deliberation panel should render without error when opinions are present."""
        tui.start_round(1)
        tui.rounds[0].agent_opinions["claude"] = "I recommend using pytest for testing."
        tui.rounds[0].agent_states["claude"] = AgentTUIState.RESPONDED
        panel = tui.build_deliberation_panel()
        assert panel is not None

    def test_result_panel_with_consensus_renders(self, tui):
        """Result panel should render with consensus progress bar and Markdown."""
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=2,
                total_agents=3,
                opinions={"claude": "yes", "codex": "yes", "gemini": "no"},
                summary="## Decision\n\nUse pytest with fixtures.",
            ),
            tasks=[
                TaskAssignment(agent_name="claude", task_description="Design API", priority=10),
            ],
            total_tokens_used=1000,
            duration_seconds=5.0,
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
        assert rs.agent_opinions == {}
        assert rs.consensus_detail == ""

    def test_with_agent_states(self):
        rs = RoundStatus(
            round_num=2,
            agent_states={"claude": AgentTUIState.RESPONDED},
            consensus="reached",
        )
        assert rs.round_num == 2
        assert rs.agent_states["claude"] == AgentTUIState.RESPONDED
        assert rs.consensus == "reached"

    def test_with_opinions(self):
        rs = RoundStatus(
            round_num=1,
            agent_opinions={"claude": "I agree", "codex": "I disagree"},
            consensus_detail="1/2 동의 (50%)",
        )
        assert rs.agent_opinions["claude"] == "I agree"
        assert rs.agent_opinions["codex"] == "I disagree"
        assert "1/2" in rs.consensus_detail


class TestAgentTUIState:
    def test_values(self):
        assert AgentTUIState.IDLE.value == "idle"
        assert AgentTUIState.RESPONDING.value == "responding"
        assert AgentTUIState.RESPONDED.value == "responded"
        assert AgentTUIState.ERROR.value == "error"
        assert AgentTUIState.DISABLED.value == "disabled"

    def test_is_string_enum(self):
        assert isinstance(AgentTUIState.IDLE, str)


class TestAgentTheme:
    """Tests for the agent theme system."""

    def test_get_theme_claude(self):
        theme = get_theme("claude")
        assert theme.name == "claude"
        assert theme.color == "cyan"
        assert theme.icon == "🏗️"
        assert theme.role_label == "Architect"

    def test_get_theme_codex(self):
        theme = get_theme("codex")
        assert theme.name == "codex"
        assert theme.color == "green"
        assert theme.role_label == "Implementer"

    def test_get_theme_gemini(self):
        theme = get_theme("gemini")
        assert theme.name == "gemini"
        assert theme.color == "magenta"
        assert theme.role_label == "Reviewer"

    def test_get_theme_unknown_agent(self):
        theme = get_theme("unknown_agent")
        assert theme.name == "unknown_agent"
        assert theme.icon == "🤖"
        assert theme.role_label == "Unknown_Agent"
        # Should have a fallback color
        assert theme.color in [
            "bright_blue", "bright_green", "bright_magenta",
            "bright_yellow", "bright_red", "bright_cyan",
        ]

    def test_get_theme_consistent(self):
        """Same name always returns same theme."""
        t1 = get_theme("custom_agent")
        t2 = get_theme("custom_agent")
        assert t1.color == t2.color
        assert t1.icon == t2.icon

    def test_agent_theme_is_frozen(self):
        theme = get_theme("claude")
        assert isinstance(theme, AgentTheme)
        # Frozen dataclass
        with pytest.raises(AttributeError):
            theme.color = "red"  # type: ignore[misc]
