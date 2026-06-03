"""Tests for trinity.tui.session — interactive session and commands."""

import json
from unittest.mock import patch

import pytest
from rich.console import Console

from trinity.config import TrinityConfig
from trinity.models import (
    ConsensusResult,
    DeliberationResult,
    TaskAssignment,
)
from trinity.tui.events import TUIEvent, TUIEventBus, TUIEventType
from trinity.tui.session import InteractiveSession
from trinity.workflow import (
    ExecutionResult,
    OpenQuestion,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
    WorkflowState,
)


@pytest.fixture
def config(tmp_path):
    cfg = TrinityConfig.default_config(project_dir=tmp_path)
    # Create state directory
    state = tmp_path / ".trinity"
    state.mkdir(exist_ok=True)
    (state / "trinity.config").write_text(
        '[general]\nsession_name = "test"\n\n'
        '[agents.claude]\nprovider = "claude-code"\ncli_command = "claude"\nenabled = true\n',
        encoding="utf-8",
    )
    (state / "shared.md").write_text(
        "# Shared Context\n\n## Current Goal\nTest\n", encoding="utf-8"
    )
    (state / "history").mkdir(exist_ok=True)
    return cfg


@pytest.fixture
def session(config):
    console = Console(force_terminal=True, width=120)
    return InteractiveSession(config, console)


class TestInteractiveSession:
    def test_init(self, session, config):
        assert session.config is config
        assert session.tui is not None
        assert session.running is False

    def test_has_tmux_check(self, session):
        with patch("shutil.which", return_value="/usr/bin/tmux"):
            assert session._has_tmux() is True
        with patch("shutil.which", return_value=None):
            assert session._has_tmux() is False


class TestSessionCommands:
    def test_cmd_status(self, session):
        session._cmd_status()
        # Should not raise — displays a table

    def test_cmd_context(self, session):
        session._cmd_context()
        # Should not raise — displays shared context

    def test_cmd_rounds_show(self, session):
        session._cmd_rounds([])
        # Should show current max rounds

    def test_cmd_rounds_set(self, session):
        session._cmd_rounds(["3"])
        assert session.config.max_deliberation_rounds == 3
        assert session.tui.max_rounds == 3

    def test_cmd_rounds_invalid(self, session):
        session._cmd_rounds(["abc"])
        # Should print "Invalid number" — no crash

    def test_cmd_rounds_out_of_range(self, session):
        session._cmd_rounds(["0"])
        # Should print range warning
        assert session.config.max_deliberation_rounds == 5  # unchanged

    def test_cmd_rounds_too_high(self, session):
        session._cmd_rounds(["100"])
        assert session.config.max_deliberation_rounds == 5  # unchanged

    def test_cmd_agent_enable(self, session):
        session._cmd_agent(["codex", "on"])
        assert session.config.agents["codex"].enabled is True

    def test_cmd_agent_disable(self, session):
        session._cmd_agent(["claude", "off"])
        assert session.config.agents["claude"].enabled is False

    def test_cmd_agent_unknown(self, session):
        session._cmd_agent(["unknown", "on"])
        # Should print "Unknown agent" — no crash

    def test_cmd_agent_no_args(self, session):
        session._cmd_agent([])
        # Should print usage — no crash

    def test_cmd_agent_invalid_action(self, session):
        session._cmd_agent(["claude", "maybe"])
        # Should print usage — no crash

    def test_cmd_history_empty(self, session):
        session._cmd_history()
        # Should print "No deliberation history yet"

    def test_cmd_history_with_entries(self, session):
        session.tui.history = [
            {"prompt": "test 1", "rounds": 2, "consensus": True, "duration": 1.5},
            {"prompt": "test 2", "rounds": 3, "consensus": False, "duration": 3.0},
        ]
        session._cmd_history()
        # Should display history table

    def test_cmd_save_no_result(self, session):
        session._cmd_save()
        # Should print "No results to save"

    def test_cmd_save_with_result(self, session):
        session.tui.last_result = DeliberationResult(
            user_prompt="test", rounds_completed=1, consensus=None
        )
        session._cmd_save()
        # Should save to history file

    def test_cmd_workflow(self, session):
        session._cmd_workflow()
        # Should display workflow panel without crashing

    def test_cmd_questions_empty(self, session):
        session._cmd_questions()
        # Should print empty-state message

    def test_cmd_questions_with_pending(self, session):
        session.workflow.add_open_question(
            OpenQuestion(id="q-001", question="Choose cost or speed?")
        )
        session._cmd_questions()
        # Should display pending questions table

    def test_cmd_decisions_empty(self, session):
        session._cmd_decisions()
        # Should print empty-state message

    def test_cmd_packages_empty(self, session):
        session._cmd_packages()
        # Should print empty-state message

    def test_cmd_packages_with_generated_package(self, session):
        session.workflow.session.work_packages.append(
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Own architecture work.",
                scope=["Architecture"],
                acceptance_criteria=["Accepted"],
            )
        )

        session._cmd_packages()
        # Should display work packages table

    def test_cmd_subtasks_empty(self, session):
        session._cmd_subtasks()
        # Should print empty-state message

    def test_cmd_subtasks_with_results(self, session):
        session.workflow.session.subtask_results.append(
            SubtaskResult(
                id="ST-001",
                parent_package_id="WP-001",
                parent_agent="codex",
                delegated_to="code-search tool",
                objective="Find patterns.",
                result_summary="Found registry.",
                status=WorkStatus.DONE,
            )
        )

        session._cmd_subtasks()
        # Should display subtask reports table


class TestSessionHandleCommand:
    def test_quit_command(self, session):
        session._handle_command("/quit")
        assert session.running is False

    def test_exit_command(self, session):
        session._handle_command("/exit")
        assert session.running is False

    def test_q_command(self, session):
        session._handle_command("/q")
        assert session.running is False

    def test_help_command(self, session):
        session._handle_command("/help")
        # Should print help text — no crash

    def test_workflow_command(self, session):
        session._handle_command("/workflow")
        # Should print workflow state

    def test_questions_command(self, session):
        session._handle_command("/questions")
        # Should print questions

    def test_decisions_command(self, session):
        session._handle_command("/decisions")
        # Should print decisions

    def test_packages_command(self, session):
        session._handle_command("/packages")
        # Should print packages

    def test_subtasks_command(self, session):
        session._handle_command("/subtasks")
        # Should print subtasks

    def test_unknown_command(self, session):
        session._handle_command("/unknown")
        # Should print "Unknown command"

    def test_empty_command(self, session):
        session._handle_command("/")
        # Should do nothing


class TestSessionPersistence:
    def test_save_history_creates_file(self, session, tmp_path):
        session.tui.history = [
            {"prompt": "test", "rounds": 1, "consensus": True, "duration": 1.0},
        ]
        session._save_history()

        history_file = session._history_file
        assert history_file.exists()

        data = json.loads(history_file.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["prompt"] == "test"

    def test_save_history_appends(self, session, tmp_path):
        # Pre-existing history
        session._history_file.parent.mkdir(parents=True, exist_ok=True)
        session._history_file.write_text(
            json.dumps([{"prompt": "old", "rounds": 1, "consensus": True, "duration": 1.0}]),
            encoding="utf-8",
        )

        session.tui.history = [
            {"prompt": "new", "rounds": 2, "consensus": False, "duration": 2.0},
        ]
        session._save_history()

        data = json.loads(session._history_file.read_text(encoding="utf-8"))
        assert len(data) == 2
        assert data[0]["prompt"] == "old"
        assert data[1]["prompt"] == "new"

    def test_save_history_handles_corrupt_file(self, session):
        session._history_file.parent.mkdir(parents=True, exist_ok=True)
        session._history_file.write_text("not json", encoding="utf-8")

        session.tui.history = [
            {"prompt": "test", "rounds": 1, "consensus": True, "duration": 1.0},
        ]
        session._save_history()

        data = json.loads(session._history_file.read_text(encoding="utf-8"))
        assert len(data) == 1  # Only new entry, old corrupt data replaced


class TestWorkflowRouting:
    def test_handle_user_text_starts_workflow_and_deliberation(self, session):
        with patch.object(session, "_run_deliberation") as run_deliberation:
            session._handle_user_text("Design a system")

        run_deliberation.assert_called_once_with("Design a system")
        assert session.workflow.state == WorkflowState.DELIBERATING
        assert session.workflow.session.goal == "Design a system"
        assert session.tui.workflow_state == WorkflowState.DELIBERATING

    def test_pending_question_answer_does_not_start_new_workflow(self, session):
        session.workflow.start("Original goal", ["claude"])
        original_id = session.workflow.session.id
        session.workflow.add_open_question(
            OpenQuestion(
                id="q-001",
                question="Which metric should be optimized?",
                options=["cost", "latency"],
            )
        )

        with patch.object(session, "_run_deliberation") as run_deliberation:
            session._handle_user_text("Use mixed score")

        assert session.workflow.session.id == original_id
        assert len(session.workflow.decisions) == 1
        assert session.workflow.decisions[0].decision == "Use mixed score"
        continuation_prompt = run_deliberation.call_args.args[0]
        assert "Original goal" in continuation_prompt
        assert "Use mixed score" in continuation_prompt

    def test_run_deliberation_updates_workflow_state(self, session):
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
        )
        with patch.object(session, "_run_with_live", return_value=result):
            with patch.object(session, "_has_tmux", return_value=False):
                session.workflow.start("test", ["claude"])
                session._run_deliberation("test")

        assert session.workflow.state == WorkflowState.BLUEPRINT_READY
        assert session.tui.workflow_state == WorkflowState.BLUEPRINT_READY

    def test_run_deliberation_updates_work_package_count(self, session):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "yes"},
                summary="Structured consensus reached.",
            ),
            metadata={
                "structured_consensus": {
                    "reached": True,
                    "final_blueprint": {
                        "title": "Route Bot",
                        "summary": "Find bridge routes.",
                        "architecture": [],
                        "data_flow": ["request -> quote -> score"],
                        "external_dependencies": [],
                        "risks": [],
                        "acceptance_criteria": ["rank paths"],
                        "open_questions": [],
                    },
                    "open_questions": [],
                }
            },
        )
        with patch.object(session, "_run_with_live", return_value=result):
            with patch.object(session, "_has_tmux", return_value=False):
                session.workflow.start("test", ["claude"])
                session._run_deliberation("test")

        assert len(session.workflow.work_packages) == 1
        assert session.tui.work_package_count == 1

    def test_run_deliberation_executes_generated_packages(self, session):
        result = DeliberationResult(
            user_prompt="Implement route bot",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "yes"},
                summary="Implement route bot.",
            ),
            metadata={
                "structured_consensus": {
                    "reached": True,
                    "final_blueprint": {
                        "title": "Route Bot",
                        "summary": "Find bridge routes.",
                        "architecture": [],
                        "data_flow": ["request -> quote -> score"],
                        "external_dependencies": [],
                        "risks": [],
                        "acceptance_criteria": ["rank paths"],
                        "open_questions": [],
                    },
                    "open_questions": [],
                }
            },
        )
        execution_result = ExecutionResult(
            package_id="WP-001",
            agent_name="claude",
            status=WorkStatus.DONE,
            summary="Implemented route bot.",
            subtasks=[
                SubtaskResult(
                    id="ST-001",
                    parent_package_id="WP-001",
                    parent_agent="claude",
                    delegated_to="planner helper",
                    objective="Check route scoring assumptions.",
                    result_summary="Confirmed scoring assumptions.",
                    status=WorkStatus.DONE,
                )
            ],
        )
        with patch.object(session, "_run_with_live", return_value=result):
            with patch.object(
                session,
                "_run_execution_with_live",
                return_value=[execution_result],
            ) as run_execution:
                with patch.object(session, "_has_tmux", return_value=False):
                    session.workflow.start("Implement route bot", ["claude"])
                    session._run_deliberation("Implement route bot")

        run_execution.assert_called_once()
        assert session.workflow.state == WorkflowState.REVIEWING
        assert session.workflow.work_packages[0].status == WorkStatus.DONE
        assert len(session.workflow.subtask_results) == 1
        assert session.tui.workflow_state == WorkflowState.REVIEWING
        assert session.tui.subtask_result_count == 1


class TestSessionDisplayResult:
    def test_display_consensus(self, session):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=2,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=2,
                total_agents=2,
                opinions={"a": "yes", "b": "yes"},
                summary="Use pytest.",
            ),
        )
        session._display_result(result)
        # Should not raise

    def test_display_no_consensus(self, session):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=5,
            consensus=None,
        )
        session._display_result(result)

    def test_display_with_tasks(self, session):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"a": "yes"},
                summary="Done.",
            ),
            tasks=[
                TaskAssignment(agent_name="claude", task_description="Write code", priority=10),
                TaskAssignment(agent_name="codex", task_description="Write tests", priority=5),
            ],
        )
        session._display_result(result)

    def test_display_with_long_task_description(self, session):
        result = DeliberationResult(
            user_prompt="test",
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"a": "yes"},
                summary="Done.",
            ),
            tasks=[
                TaskAssignment(
                    agent_name="claude",
                    task_description="x" * 120,  # Very long description
                    priority=10,
                ),
            ],
        )
        session._display_result(result)


class TestTUIEventBus:
    """Tests for the thread-safe event bus."""

    def test_emit_and_poll(self):
        bus = TUIEventBus()
        bus.emit(TUIEvent(type=TUIEventType.ROUND_START, data={"round_num": 1}))
        events = bus.poll()
        assert len(events) == 1
        assert events[0].type == TUIEventType.ROUND_START
        assert events[0].data["round_num"] == 1

    def test_poll_empty(self):
        bus = TUIEventBus()
        events = bus.poll()
        assert events == []

    def test_multiple_events_in_order(self):
        bus = TUIEventBus()
        bus.emit(TUIEvent(type=TUIEventType.ROUND_START, data={"round_num": 1}))
        bus.emit(TUIEvent(type=TUIEventType.AGENT_THINKING, data={"agent": "claude"}))
        bus.emit(TUIEvent(type=TUIEventType.AGENT_RESPONDED, data={"agent": "claude"}))

        events = bus.poll()
        assert len(events) == 3
        assert events[0].type == TUIEventType.ROUND_START
        assert events[1].type == TUIEventType.AGENT_THINKING
        assert events[2].type == TUIEventType.AGENT_RESPONDED

    def test_poll_drains_queue(self):
        bus = TUIEventBus()
        bus.emit(TUIEvent(type=TUIEventType.ROUND_START, data={}))
        bus.poll()
        events = bus.poll()
        assert events == []

    def test_all_event_types(self):
        """All TUIEventType values can be emitted and polled."""
        bus = TUIEventBus()
        for et in TUIEventType:
            bus.emit(TUIEvent(type=et, data={}))
        events = bus.poll()
        assert len(events) == len(TUIEventType)
