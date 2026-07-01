"""Tests for trinity.tui.session — interactive session and commands."""

import asyncio
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
from trinity.slash_commands import SESSION_ONLY_SETTING_NOTICE
from trinity.tui.events import TUIEvent, TUIEventBus, TUIEventType
from trinity.tui.prompt import CUSTOM_OPTION_VALUE
from trinity.tui.session import InteractiveSession
from trinity.workflow import (
    Blueprint,
    ExecutionResult,
    OpenQuestion,
    ReviewResult,
    ReviewStatus,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
    WorkflowEngine,
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

    def test_default_transport_is_one_shot(self, session):
        assert session._uses_tmux_transport() is False
        assert session._transport_mode_label() == "one-shot"

    def test_tmux_transport_requires_explicit_config(self, session):
        session.config.transport_mode = "tmux"

        assert session._uses_tmux_transport() is True
        assert session._transport_mode_label() == "legacy tmux"

    def test_run_deliberation_uses_one_shot_even_when_tmux_exists(self, session):
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

        with patch("trinity.orchestrator.TrinityOrchestrator") as MockOrch:
            with patch.object(session, "_run_with_live", return_value=result):
                with patch.object(session, "_has_tmux", return_value=True):
                    session.workflow.start("test", ["claude"])
                    session._run_deliberation("test")

        MockOrch.assert_called_once()
        assert MockOrch.call_args.kwargs["interactive"] is False

    def test_run_deliberation_passes_selected_target_workspace(self, session, tmp_path):
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
        target = tmp_path / "route-bot"
        session.workflow.set_target_workspace(target)

        with patch("trinity.orchestrator.TrinityOrchestrator") as MockOrch:
            with patch.object(session, "_run_with_live", return_value=result):
                session.workflow.start("test", ["claude"])
                session._run_deliberation("test")

        MockOrch.assert_called_once()
        assert MockOrch.call_args.kwargs["target_workspace"] == target.resolve()
        assert MockOrch.call_args.kwargs["allow_control_repo_writes"] is False

    def test_run_deliberation_uses_tmux_when_configured(self, session):
        session.config.transport_mode = "tmux"
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

        with patch("trinity.orchestrator.TrinityOrchestrator") as MockOrch:
            with patch.object(session, "_run_with_live", return_value=result):
                with patch.object(session, "_has_tmux", return_value=True):
                    session.workflow.start("test", ["claude"])
                    session._run_deliberation("test")

        MockOrch.assert_called_once()
        assert MockOrch.call_args.kwargs["interactive"] is True

    def test_run_deliberation_rejects_tmux_mode_when_tmux_missing(self, session):
        session.config.transport_mode = "tmux"

        with patch("trinity.orchestrator.TrinityOrchestrator") as MockOrch:
            with patch.object(session, "_run_with_live") as run_with_live:
                with patch.object(session, "_has_tmux", return_value=False):
                    session._run_deliberation("test")

        MockOrch.assert_not_called()
        run_with_live.assert_not_called()

    def test_starts_with_new_workflow_and_archives_previous(self, config):
        previous = WorkflowEngine(config.effective_state_dir)
        previous.start("Old whale tracker goal", ["claude"])
        previous_id = previous.session.id

        console = Console(force_terminal=True, width=120)
        session = InteractiveSession(config, console)

        assert session.workflow.session.id != previous_id
        assert session.workflow.state == WorkflowState.IDLE
        assert session.workflow.session.goal == ""

        archives = session.workflow_persistence.list_archives()
        assert len(archives) == 1
        assert archives[0].session.id == previous_id
        assert archives[0].session.goal == "Old whale tracker goal"


class TestSessionCommands:
    def test_cmd_status(self, session):
        session._cmd_status()
        # Should not raise — displays a table

    def test_cmd_context(self, session):
        session._cmd_context()
        # Should not raise — displays current session context state

    def test_cmd_context_uses_current_session_not_shared_file(self, config):
        config.shared_context_path.write_text(
            "# Shared Context\n\n## Agreed Conclusion\nOld session summary.\n",
            encoding="utf-8",
        )
        console = Console(force_terminal=True, width=120, record=True)
        session = InteractiveSession(config, console)
        session.workflow.start("Current session goal", ["claude"])

        session._cmd_context()

        output = console.export_text()
        assert "Current session goal" in output
        assert "Old session summary" not in output

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

    def test_session_setting_commands_show_session_only_notice(self, config):
        console = Console(force_terminal=True, width=120, record=True)
        session = InteractiveSession(config, console)

        session._cmd_rounds(["3"])
        session._cmd_agent(["claude", "off"])
        session._cmd_caveman(["lite"])

        output = console.export_text()
        assert SESSION_ONLY_SETTING_NOTICE in output
        assert output.count(SESSION_ONLY_SETTING_NOTICE) == 3

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

    def test_workspace_command_sets_target_workspace(self, session):
        target = session.config.project_dir.parent / "workspace-alias"

        session._handle_command(f"/workspace {target}")

        assert session.workflow.session.target_workspace == target.resolve()
        assert target.is_dir()

    def test_project_command_shows_plain_diagnostics(self, session):
        with patch.object(session.console, "print") as print_:
            session._handle_command("/project")

        print_.assert_called_once()

    def test_project_command_rejects_workspace_shortcut(self, session):
        target = session.config.project_dir.parent / "project-workspace-alias"

        with patch.object(session.console, "print") as print_:
            session._handle_command(f"/project workspace {target}")

        print_.assert_called_once_with(
            "[yellow]/project only shows diagnostics. Use /target <path> to select a target.[/yellow]"
        )
        assert session.workflow.session.target_workspace is None
        assert not target.exists()

    def test_providers_command_shows_plain_status(self, session):
        with patch.object(session, "_cmd_status") as status:
            session._handle_command("/providers")

        status.assert_called_once()

    def test_settings_command_explains_textual_settings(self, session):
        with patch.object(session.console, "print") as print_:
            session._handle_command("/settings")

        print_.assert_called_once_with(
            "[yellow]/settings opens the Textual Workbench settings screen. "
            "Run `trinity --textual` or use Ctrl+, in the workbench.[/yellow]"
        )

    def test_workflow_command(self, session):
        session._handle_command("/workflow")
        # Should print workflow state

    def test_questions_command(self, session):
        session._handle_command("/questions")
        # Should print questions

    def test_answer_command(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.add_open_question(
            OpenQuestion(
                id="q-001",
                question="Which metric should be optimized?",
                options=["cost", "latency"],
            )
        )

        with patch.object(session, "_run_deliberation") as run_deliberation:
            session._handle_command("/answer q-001 Use mixed score")

        assert len(session.workflow.decisions) == 1
        assert session.workflow.decisions[0].question_id == "q-001"
        assert session.workflow.decisions[0].decision == "Use mixed score"
        run_deliberation.assert_called_once()

    def test_decisions_command(self, session):
        session._handle_command("/decisions")
        # Should print decisions

    def test_packages_command(self, session):
        session._handle_command("/packages")
        # Should print packages

    def test_subtasks_command(self, session):
        session._handle_command("/subtasks")
        # Should print subtasks

    def test_resume_command_restores_latest_workflow(self, config):
        previous = WorkflowEngine(config.effective_state_dir)
        previous.start("Resume this workflow", ["claude"])
        previous_id = previous.session.id

        console = Console(force_terminal=True, width=120)
        session = InteractiveSession(config, console)

        session._handle_command("/resume latest")

        assert session.workflow.session.id == previous_id
        assert session.workflow.session.goal == "Resume this workflow"

    def test_resume_command_lists_sessions_without_selector(self, config):
        previous = WorkflowEngine(config.effective_state_dir)
        previous.start("List this workflow", ["claude"])

        console = Console(force_terminal=True, width=120)
        session = InteractiveSession(config, console)

        with patch("trinity.tui.session.sys.stdin.isatty", return_value=False):
            session._handle_command("/resume")
        # Should print saved workflow table and not raise.

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

    def test_pending_question_text_answers_next_question(self, session):
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

    def test_answer_command_does_not_start_new_workflow(self, session):
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
            session._handle_command("/answer q-001 Use mixed score")

        assert session.workflow.session.id == original_id
        assert len(session.workflow.decisions) == 1
        assert session.workflow.decisions[0].decision == "Use mixed score"
        continuation_prompt = run_deliberation.call_args.args[0]
        assert "Original goal" in continuation_prompt
        assert "Use mixed score" in continuation_prompt

    def test_answer_command_replaces_decision(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.add_open_question(
            OpenQuestion(id="q-001", question="Which API?")
        )
        with patch.object(session, "_run_deliberation"):
            session._handle_command("/answer q-001 LI.FI")
            session._handle_command("/answer --replace q-001 Socket")

        assert len(session.workflow.decisions) == 1
        assert session.workflow.decisions[0].decision == "Socket"

    def test_blueprint_ready_text_can_continue_existing_workflow(self, session):
        session.workflow.start("Original goal", ["claude"])
        original_id = session.workflow.session.id
        session.workflow.session.blueprint = Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            acceptance_criteria=["rank paths"],
        )
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Plan route bot.",
                requires_execution=False,
            )
        ]
        session.workflow.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="test blueprint ready",
        )

        with patch.object(
            session,
            "_select_blueprint_followup_action",
            return_value="continue",
        ):
            with patch.object(session, "_run_deliberation") as run_deliberation:
                session._handle_user_text("Add Telegram alerts")

        assert session.workflow.session.id == original_id
        continuation_prompt = run_deliberation.call_args.args[0]
        assert "Continue the existing workflow" in continuation_prompt
        assert "Add Telegram alerts" in continuation_prompt

    def test_blueprint_ready_text_can_execute_current_blueprint(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.session.blueprint = Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            acceptance_criteria=["rank paths"],
        )
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Plan route bot.",
                requires_execution=False,
            )
        ]
        session.workflow.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="test blueprint ready",
        )

        with patch.object(
            session,
            "_select_blueprint_followup_action",
            return_value="execute",
        ):
            with patch.object(session, "_execute_current_blueprint") as execute:
                session._handle_user_text("Implement it")

        execute.assert_called_once_with(instruction="Implement it")

    def test_blueprint_ready_korean_execute_intent_skips_followup_picker(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.session.blueprint = Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            acceptance_criteria=["rank paths"],
        )
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Plan route bot.",
                requires_execution=False,
            )
        ]
        session.workflow.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="test blueprint ready",
        )

        with patch.object(session._prompt_session, "select_option") as select_option:
            with patch.object(session, "_execute_current_blueprint") as execute:
                session._handle_user_text("개발해라")

        select_option.assert_not_called()
        execute.assert_called_once_with(instruction="개발해라")

    def test_execute_command_marks_current_blueprint_executable(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.session.blueprint = Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            acceptance_criteria=["rank paths"],
        )
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Plan route bot.",
                requires_execution=False,
            )
        ]
        session.workflow.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="test blueprint ready",
        )
        target = session.config.project_dir.parent / "route-bot"
        target.mkdir(exist_ok=True)
        session.workflow.set_target_workspace(target)

        with patch.object(session, "_maybe_run_execution") as maybe_run_execution:
            session._handle_command("/execute Implement it")

        assert session.workflow.work_packages[0].requires_execution is True
        assert session.workflow.decisions[0].decision == "Implement it"
        maybe_run_execution.assert_called_once()

    def test_execute_command_without_target_workspace_waits_for_target(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.session.blueprint = Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            acceptance_criteria=["rank paths"],
        )
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Plan route bot.",
                requires_execution=False,
            )
        ]
        session.workflow.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="test blueprint ready",
        )

        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=False):
                session._handle_command("/execute Implement it")

        assert session.workflow.session.target_workspace is None
        assert session.workflow.work_packages[0].requires_execution is False
        assert session.workflow.decisions == []

    def test_execute_retry_command_prepares_selected_package(self, session):
        session.workflow.start("Original goal", ["claude", "codex"])
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="client",
                owner_agent="claude",
                objective="Build client.",
                status=WorkStatus.FAILED,
            ),
            WorkPackage(
                id="WP-002",
                title="server",
                owner_agent="codex",
                objective="Build server.",
                status=WorkStatus.FAILED,
            ),
        ]
        target = session.config.project_dir.parent / "route-bot"
        target.mkdir(exist_ok=True)
        session.workflow.set_target_workspace(target)
        session.workflow.set_state(WorkflowState.FAILED, reason="simulate failed execution")

        with patch.object(session, "_run_enabled_execution") as run_enabled_execution:
            session._handle_command("/execute-retry custom WP-002")

        assert [package.status for package in session.workflow.work_packages] == [
            WorkStatus.FAILED,
            WorkStatus.PENDING,
        ]
        assert session.workflow.session.execution_run["retry_packages"] == ["WP-002"]
        run_enabled_execution.assert_called_once()

    def test_execute_command_can_select_default_target_workspace(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.session.blueprint = Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            acceptance_criteria=["rank paths"],
        )
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Plan route bot.",
                requires_execution=False,
            )
        ]
        session.workflow.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="test blueprint ready",
        )

        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=True):
                with patch.object(
                    session._prompt_session,
                    "select_option",
                    return_value="1",
                ):
                    with patch.object(session, "_maybe_run_execution") as execute:
                        session._handle_command("/execute Implement it")

        expected = session.config.project_dir.parent / "route-bot"
        assert session.workflow.session.target_workspace == expected.resolve()
        assert expected.is_dir()
        assert session.workflow.work_packages[0].requires_execution is True
        execute.assert_called_once()

    def test_execution_live_loop_persists_incremental_package_progress(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Implement route bot.",
            )
        ]
        target = session.config.project_dir.parent / "route-bot"
        target.mkdir(exist_ok=True)
        session.workflow.set_target_workspace(target)
        session.workflow.begin_execution()

        class FakeOrchestrator:
            def __init__(self):
                self.bus = None

            def set_event_bus(self, bus):
                self.bus = bus

            async def execute_work_packages(
                self,
                work_packages,
                decisions=None,
                result_callback=None,
            ):
                assert self.bus is not None
                self.bus.emit(
                    TUIEvent(
                        type=TUIEventType.WORK_PACKAGE_STARTED,
                        data={
                            "package_id": "WP-001",
                            "agent": "claude",
                            "status": WorkStatus.RUNNING.value,
                            "occurred_at": 1234.5,
                        },
                    )
                )
                result = ExecutionResult(
                    package_id="WP-001",
                    agent_name="claude",
                    status=WorkStatus.DONE,
                    summary="Implemented route bot.",
                    files_changed=["src/routes.py"],
                )
                if result_callback:
                    result_callback(result)
                self.bus.emit(
                    TUIEvent(
                        type=TUIEventType.WORK_PACKAGE_COMPLETED,
                        data={
                            "package_id": "WP-001",
                            "agent": "claude",
                            "status": WorkStatus.DONE.value,
                            "summary": "Implemented route bot.",
                            "occurred_at": 1300.25,
                        },
                    )
                )
                self.bus.emit(
                    TUIEvent(
                        type=TUIEventType.EXECUTION_DONE,
                        data={"package_count": len(work_packages)},
                    )
                )
                return [result]

        results = session._run_execution_with_live(FakeOrchestrator())

        assert results[0].status == WorkStatus.DONE
        assert session.workflow.session.work_packages[0].status == WorkStatus.DONE
        assert session.workflow.execution_results[0].summary == "Implemented route bot."
        loaded = WorkflowEngine(session.config.effective_state_dir)
        assert loaded.session.work_packages[0].status == WorkStatus.DONE
        assert loaded.execution_results[0].files_changed == ["src/routes.py"]
        events = loaded.persistence.load_events()
        started = [
            event
            for event in events
            if event["event"] == "work_package_started"
        ][-1]
        completed = [
            event
            for event in events
            if event["event"] == "work_package_completed"
        ][-1]
        assert started["timestamp"] == 1234.5
        assert completed["timestamp"] == 1300.25
        assert completed["data"]["summary"] == "Implemented route bot."

    def test_execution_live_loop_waits_for_thread_after_done_event(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="claude package",
                owner_agent="claude",
                objective="Implement route bot.",
            )
        ]
        target = session.config.project_dir.parent / "route-bot"
        target.mkdir(exist_ok=True)
        session.workflow.set_target_workspace(target)
        session.workflow.begin_execution()

        class FakeOrchestrator:
            def __init__(self):
                self.bus = None

            def set_event_bus(self, bus):
                self.bus = bus

            async def execute_work_packages(
                self,
                work_packages,
                decisions=None,
                result_callback=None,
            ):
                assert self.bus is not None
                self.bus.emit(
                    TUIEvent(
                        type=TUIEventType.EXECUTION_DONE,
                        data={"package_count": len(work_packages)},
                    )
                )
                await asyncio.sleep(0.05)
                self.bus.emit(
                    TUIEvent(
                        type=TUIEventType.WORK_PACKAGE_STARTED,
                        data={
                            "package_id": "WP-001",
                            "agent": "claude",
                            "status": WorkStatus.RUNNING.value,
                        },
                    )
                )
                result = ExecutionResult(
                    package_id="WP-001",
                    agent_name="claude",
                    status=WorkStatus.DONE,
                    summary="Finished after done event.",
                )
                if result_callback:
                    result_callback(result)
                return [result]

        results = session._run_execution_with_live(FakeOrchestrator())

        assert results[0].status == WorkStatus.DONE
        assert session.workflow.execution_results[0].summary == (
            "Finished after done event."
        )

    def test_review_command_runs_work_package_and_final_review(self, session):
        session.workflow.start("Implement route bot", ["claude", "codex"])
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="client",
                owner_agent="claude",
                objective="Build client.",
                status=WorkStatus.DONE,
            )
        ]
        session.workflow.session.execution_results = [
            ExecutionResult(
                package_id="WP-001",
                agent_name="claude",
                status=WorkStatus.DONE,
                summary="Implemented client.",
            )
        ]
        target = session.config.project_dir.parent / "route-bot"
        target.mkdir(exist_ok=True)
        session.workflow.set_target_workspace(target)
        session.workflow.set_state(WorkflowState.REVIEWING, reason="test review")
        session.workflow.ensure_review_packages()

        class FakeReviewOrchestrator:
            def __init__(self, *args, **kwargs):
                self.bus = None

            def set_event_bus(self, bus):
                self.bus = bus

            async def review_work_packages(self, review_packages, work_packages, execution_results):
                assert self.bus is not None
                review = review_packages[0]
                self.bus.emit(
                    TUIEvent(
                        type=TUIEventType.WORK_PACKAGE_REVIEW_STARTED,
                        data={
                            "package_id": review.package_id,
                            "reviewer": review.reviewer_agent,
                        },
                    )
                )
                self.bus.emit(
                    TUIEvent(
                        type=TUIEventType.WORK_PACKAGE_REVIEW_COMPLETED,
                        data={
                            "package_id": review.package_id,
                            "reviewer": review.reviewer_agent,
                            "status": ReviewStatus.APPROVED.value,
                        },
                    )
                )
                return [
                    ReviewResult(
                        review_package_id=review.id,
                        package_id=review.package_id,
                        reviewer_agent=review.reviewer_agent,
                        target_agent=review.target_agent,
                        status=ReviewStatus.APPROVED,
                        severity="low",
                        summary="WP approved.",
                    )
                ]

            async def review_final_execution(
                self,
                work_packages,
                execution_results,
                review_results,
            ):
                return ReviewResult(
                    review_package_id="RP-FINAL-claude",
                    package_id="FINAL",
                    reviewer_agent="claude",
                    target_agent="project",
                    status=ReviewStatus.APPROVED,
                    severity="low",
                    scope="final",
                    summary="Final approved.",
                )

        with patch("trinity.orchestrator.TrinityOrchestrator", FakeReviewOrchestrator):
            session._handle_command("/review all")

        assert session.workflow.state == WorkflowState.POST_REVIEW_READY
        assert [result.status for result in session.workflow.review_results] == [
            ReviewStatus.APPROVED,
            ReviewStatus.APPROVED,
        ]

    def test_final_review_changes_auto_queue_post_review_work_package(self, session):
        session.workflow.start("Implement route bot", ["claude", "codex"])
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="client",
                owner_agent="claude",
                objective="Build client.",
                status=WorkStatus.DONE,
                last_executor="claude",
            )
        ]
        target = session.config.project_dir.parent / "route-bot"
        target.mkdir(exist_ok=True)
        session.workflow.set_target_workspace(target)
        session.workflow.set_state(WorkflowState.REVIEWING, reason="test final review")
        session.workflow.record_review_results(
            [
                ReviewResult(
                    review_package_id="RP-FINAL-claude",
                    package_id="FINAL",
                    reviewer_agent="claude",
                    target_agent="project",
                    status=ReviewStatus.CHANGES_REQUESTED,
                    severity="high",
                    scope="final",
                    summary="Needs regression coverage.",
                    required_changes=["Add review regression tests."],
                )
            ]
        )

        assert session.workflow.state == WorkflowState.BLUEPRINT_READY
        assert session.workflow.session.work_packages[-1].id == "WP-S001"
        assert session.workflow.session.work_packages[-1].origin == "post_review_followup"
        assert session.workflow.post_review_items[0].status.value == "queued"
        assert session.workflow.session.execution_run["state"] == "supplemental_queued"
        assert (
            session.workflow.session.execution_run["source"]
            == "final_review_auto_replan"
        )

    def test_execute_auto_runs_review_after_completion(self, session):
        session.workflow.start("Implement route bot", ["claude", "codex"])
        session.workflow.session.blueprint = Blueprint(
            title="Route Bot",
            summary="Find bridge routes.",
            acceptance_criteria=["rank paths"],
        )
        session.workflow.session.work_packages = [
            WorkPackage(
                id="WP-001",
                title="client",
                owner_agent="claude",
                objective="Build client.",
                requires_execution=True,
            )
        ]
        target = session.config.project_dir.parent / "route-bot"
        target.mkdir(exist_ok=True)
        session.workflow.set_target_workspace(target)
        session.workflow.set_state(WorkflowState.BLUEPRINT_READY, reason="test blueprint")

        class FakeExecutionReviewOrchestrator:
            def __init__(self, *args, **kwargs):
                self.bus = None

            def set_event_bus(self, bus):
                self.bus = bus

            async def execute_work_packages(
                self,
                work_packages,
                decisions=None,
                result_callback=None,
            ):
                result = ExecutionResult(
                    package_id="WP-001",
                    agent_name="claude",
                    status=WorkStatus.DONE,
                    summary="Implemented client.",
                )
                if result_callback:
                    result_callback(result)
                return [result]

            async def review_work_packages(self, review_packages, work_packages, execution_results):
                review = review_packages[0]
                return [
                    ReviewResult(
                        review_package_id=review.id,
                        package_id=review.package_id,
                        reviewer_agent=review.reviewer_agent,
                        target_agent=review.target_agent,
                        status=ReviewStatus.APPROVED,
                        severity="low",
                        summary="WP approved.",
                    )
                ]

            async def review_final_execution(
                self,
                work_packages,
                execution_results,
                review_results,
            ):
                return ReviewResult(
                    review_package_id="RP-FINAL-claude",
                    package_id="FINAL",
                    reviewer_agent="claude",
                    target_agent="project",
                    status=ReviewStatus.APPROVED,
                    severity="low",
                    scope="final",
                    summary="Final approved.",
                )

        with patch("trinity.orchestrator.TrinityOrchestrator", FakeExecutionReviewOrchestrator):
            session._handle_command("/execute")

        assert session.workflow.state == WorkflowState.POST_REVIEW_READY
        assert [result.status for result in session.workflow.review_results] == [
            ReviewStatus.APPROVED,
            ReviewStatus.APPROVED,
        ]

    def test_questions_select_answers_next_option(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.add_open_question(
            OpenQuestion(
                id="q-001",
                question="Which API?",
                options=["LI.FI", "Socket"],
            )
        )

        with patch("trinity.tui.session.sys.stdin.isatty", return_value=True):
            with patch("trinity.tui.session.sys.stdout.isatty", return_value=True):
                with patch.object(
                    session._prompt_session,
                    "select_option",
                    return_value="2",
                ):
                    with patch.object(session, "_run_deliberation") as run_deliberation:
                        session._cmd_questions(["--select"])

        assert session.workflow.decisions[0].decision == "Socket"
        run_deliberation.assert_called_once()

    def test_questions_select_all_answers_all_option_questions(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.add_open_question(
            OpenQuestion(
                id="q-001",
                question="Which API?",
                options=["LI.FI", "Socket"],
            )
        )
        session.workflow.add_open_question(
            OpenQuestion(
                id="q-002",
                question="Which framework?",
                options=["TypeScript", "Python"],
            )
        )

        with patch("trinity.tui.session.sys.stdin.isatty", return_value=True):
            with patch("trinity.tui.session.sys.stdout.isatty", return_value=True):
                with patch.object(
                    session._prompt_session,
                    "select_option",
                    side_effect=["1", "2"],
                ) as select_option:
                    with patch.object(session, "_run_deliberation") as run_deliberation:
                        session._cmd_questions(["--select", "--all"])

        assert [decision.decision for decision in session.workflow.decisions] == [
            "LI.FI",
            "Python",
        ]
        assert select_option.call_count == 2
        run_deliberation.assert_called_once()

    def test_questions_select_all_accepts_free_text_question(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.add_open_question(
            OpenQuestion(id="q-001", question="Which platform?")
        )

        with patch("trinity.tui.session.sys.stdin.isatty", return_value=True):
            with patch("trinity.tui.session.sys.stdout.isatty", return_value=True):
                with patch.object(
                    session._prompt_session,
                    "get_answer_input",
                    return_value="Telegram",
                ) as get_answer:
                    with patch.object(session, "_run_deliberation") as run_deliberation:
                        session._cmd_questions(["--select", "--all"])

        assert session.workflow.decisions[0].decision == "Telegram"
        get_answer.assert_called_once_with(question_id="q-001")
        run_deliberation.assert_called_once()

    def test_questions_select_accepts_custom_answer_for_option_question(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.add_open_question(
            OpenQuestion(
                id="q-001",
                question="Which API?",
                options=["LI.FI", "Socket"],
            )
        )

        with patch("trinity.tui.session.sys.stdin.isatty", return_value=True):
            with patch("trinity.tui.session.sys.stdout.isatty", return_value=True):
                with patch.object(
                    session._prompt_session,
                    "select_option",
                    return_value=CUSTOM_OPTION_VALUE,
                ) as select_option:
                    with patch.object(
                        session._prompt_session,
                        "get_answer_input",
                        return_value="Across first",
                    ) as get_answer:
                        with patch.object(
                            session, "_run_deliberation"
                        ) as run_deliberation:
                            session._cmd_questions(["--select"])

        assert session.workflow.decisions[0].decision == "Across first"
        select_option.assert_called_once()
        assert select_option.call_args.kwargs["allow_custom"] is True
        get_answer.assert_called_once_with(question_id="q-001")
        run_deliberation.assert_called_once()

    def test_offer_pending_questions_runs_all_questions_as_wizard(self, session):
        session.workflow.start("Original goal", ["claude"])
        session.workflow.add_open_question(
            OpenQuestion(
                id="q-001",
                question="Which API?",
                options=["LI.FI", "Socket"],
            )
        )
        session.workflow.add_open_question(
            OpenQuestion(id="q-002", question="Which platform?")
        )

        with patch("trinity.tui.session.sys.stdin.isatty", return_value=True):
            with patch("trinity.tui.session.sys.stdout.isatty", return_value=True):
                with patch.object(
                    session._prompt_session,
                    "select_option",
                    return_value="1",
                ) as select_option:
                    with patch.object(
                        session._prompt_session,
                        "get_answer_input",
                        return_value="Telegram",
                    ) as get_answer:
                        with patch.object(
                            session, "_run_deliberation"
                        ) as run_deliberation:
                            session._offer_pending_questions()

        assert [decision.decision for decision in session.workflow.decisions] == [
            "LI.FI",
            "Telegram",
        ]
        select_option.assert_called_once()
        get_answer.assert_called_once_with(question_id="q-002")
        run_deliberation.assert_called_once()

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
                    with patch.object(session, "_run_review") as run_review:
                        session.workflow.start("Implement route bot", ["claude"])
                        target = session.config.project_dir.parent / "route-bot"
                        target.mkdir(exist_ok=True)
                        session.workflow.set_target_workspace(target)
                        session._run_deliberation("Implement route bot")

        run_execution.assert_called_once()
        run_review.assert_called_once()
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
