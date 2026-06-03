"""Tests for WorkflowEngine state machine and WorkflowPersistence."""

import json
import time

import pytest

from trinity.models import (
    ArchitectureComponent,
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    WorkflowEvent,
    WorkflowSession,
    WorkflowState,
    WorkPackage,
    WorkStatus,
)
from trinity.workflow.engine import WorkflowEngine, _VALID_TRANSITIONS
from trinity.workflow.persistence import WorkflowPersistence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine_at(state: WorkflowState) -> WorkflowEngine:
    """Build an engine whose session is already at *state* via valid path."""
    engine = WorkflowEngine()

    if state == WorkflowState.IDLE:
        # Create a session at IDLE without transitioning
        engine._session = WorkflowSession(
            id="testidle",
            goal="test",
            state=WorkflowState.IDLE,
            active_agents=["agent-a"],
        )
        return engine

    engine.start("test goal", ["agent-a", "agent-b"])

    # Find a shortest path to the target state from PREFLIGHT
    if state == WorkflowState.PREFLIGHT:
        return engine

    # Build paths manually for each reachable state
    if state == WorkflowState.DELIBERATING:
        engine.transition_preflight(["agent-a"])
        return engine

    if state == WorkflowState.NEEDS_USER_DECISION:
        engine.transition_preflight(["agent-a"])
        engine.transition_needs_user_decision(
            [OpenQuestion(id="q1", question="Q?")]
        )
        return engine

    if state == WorkflowState.BLUEPRINT_READY:
        engine.transition_preflight(["agent-a"])
        engine.transition_blueprint_ready(
            Blueprint(title="T", summary="S", architecture=[])
        )
        return engine

    if state == WorkflowState.EXECUTING:
        engine.transition_preflight(["agent-a"])
        engine.transition_blueprint_ready(
            Blueprint(title="T", summary="S", architecture=[])
        )
        engine.transition_executing([])
        return engine

    if state == WorkflowState.REVIEWING:
        engine.transition_preflight(["agent-a"])
        engine.transition_blueprint_ready(
            Blueprint(title="T", summary="S", architecture=[])
        )
        engine.transition_executing([])
        # REVIEWING is reachable from EXECUTING
        engine._transition(WorkflowState.REVIEWING)
        return engine

    if state == WorkflowState.DONE:
        engine.transition_preflight(["agent-a"])
        engine.transition_blueprint_ready(
            Blueprint(title="T", summary="S", architecture=[])
        )
        engine.transition_done([])
        return engine

    if state == WorkflowState.FAILED:
        engine.transition_failed("test")
        return engine

    raise ValueError(f"Unsupported test state: {state}")


# ---------------------------------------------------------------------------
# TestWorkflowEngineStateTransitions
# ---------------------------------------------------------------------------


class TestWorkflowEngineStateTransitions:
    """Test every valid state transition and that invalid ones raise ValueError."""

    # -- start / basic lifecycle ---------------------------------------------

    def test_start_creates_session_in_preflight(self):
        engine = WorkflowEngine()
        session = engine.start("build feature X", ["a1", "a2"])
        assert session.state == WorkflowState.PREFLIGHT
        assert session.goal == "build feature X"
        assert session.active_agents == ["a1", "a2"]
        assert len(session.id) == 8

    def test_start_raises_if_session_already_active(self):
        engine = WorkflowEngine()
        engine.start("goal", ["a1"])
        with pytest.raises(RuntimeError, match="Session already active"):
            engine.start("other goal", ["a2"])

    def test_restore_replaces_session(self):
        engine = WorkflowEngine()
        engine.start("goal", ["a1"])
        new_session = WorkflowSession(id="abcd1234", goal="restored", state=WorkflowState.DONE)
        engine.restore(new_session)
        # The engine should now use the restored session
        assert engine._session.id == "abcd1234"

    # -- PREFLIGHT transitions -----------------------------------------------

    def test_preflight_to_deliberating(self):
        engine = _make_engine_at(WorkflowState.PREFLIGHT)
        session = engine.transition_preflight(["agent-a"])
        assert session.state == WorkflowState.DELIBERATING
        assert session.active_agents == ["agent-a"]

    def test_preflight_filters_agents(self):
        engine = _make_engine_at(WorkflowState.PREFLIGHT)
        session = engine.transition_preflight(["agent-a", "agent-z"])
        # agent-z was not in the original active_agents, so only agent-a kept
        assert session.active_agents == ["agent-a"]

    def test_preflight_to_failed_when_no_ready_agents(self):
        engine = _make_engine_at(WorkflowState.PREFLIGHT)
        session = engine.transition_preflight([])
        assert session.state == WorkflowState.FAILED

    # -- DELIBERATING transitions --------------------------------------------

    def test_deliberating_to_needs_user_decision(self):
        engine = _make_engine_at(WorkflowState.DELIBERATING)
        questions = [OpenQuestion(id="q1", question="Which DB?")]
        session = engine.transition_needs_user_decision(questions)
        assert session.state == WorkflowState.NEEDS_USER_DECISION
        assert len(session.pending_questions) == 1

    def test_deliberating_to_blueprint_ready(self):
        engine = _make_engine_at(WorkflowState.DELIBERATING)
        bp = Blueprint(title="Plan", summary="A plan", architecture=[])
        session = engine.transition_blueprint_ready(bp)
        assert session.state == WorkflowState.BLUEPRINT_READY
        assert session.blueprint is not None
        assert session.blueprint.title == "Plan"

    def test_deliberating_to_failed(self):
        engine = _make_engine_at(WorkflowState.DELIBERATING)
        session = engine.transition_failed("agents disagree")
        assert session.state == WorkflowState.FAILED

    # -- NEEDS_USER_DECISION transitions -------------------------------------

    def test_needs_user_decision_to_deliberating(self):
        engine = _make_engine_at(WorkflowState.NEEDS_USER_DECISION)
        decision = DecisionRecord(
            id="d1", decision="Use PostgreSQL", decided_by="user", question_id="q1"
        )
        session = engine.transition_user_answered(decision)
        assert session.state == WorkflowState.DELIBERATING
        assert len(session.pending_questions) == 0
        assert len(session.decisions) == 1

    # -- BLUEPRINT_READY transitions -----------------------------------------

    def test_blueprint_ready_to_executing(self):
        engine = _make_engine_at(WorkflowState.BLUEPRINT_READY)
        wps = [WorkPackage(id="wp1", title="Task", owner_agent="a", objective="Do it")]
        session = engine.transition_executing(wps)
        assert session.state == WorkflowState.EXECUTING
        assert len(session.work_packages) == 1

    def test_blueprint_ready_to_done(self):
        engine = _make_engine_at(WorkflowState.BLUEPRINT_READY)
        session = engine.transition_done([])
        assert session.state == WorkflowState.DONE

    # -- EXECUTING transitions -----------------------------------------------

    def test_executing_to_reviewing(self):
        engine = _make_engine_at(WorkflowState.EXECUTING)
        engine._transition(WorkflowState.REVIEWING)
        assert engine._session.state == WorkflowState.REVIEWING

    def test_executing_to_done(self):
        engine = _make_engine_at(WorkflowState.EXECUTING)
        session = engine.transition_done([])
        assert session.state == WorkflowState.DONE

    def test_executing_to_failed(self):
        engine = _make_engine_at(WorkflowState.EXECUTING)
        session = engine.transition_failed("execution error")
        assert session.state == WorkflowState.FAILED

    # -- REVIEWING transitions -----------------------------------------------

    def test_reviewing_to_needs_user_decision(self):
        engine = _make_engine_at(WorkflowState.REVIEWING)
        session = engine.transition_needs_user_decision(
            [OpenQuestion(id="q2", question="Approve?")]
        )
        assert session.state == WorkflowState.NEEDS_USER_DECISION

    def test_reviewing_to_done(self):
        engine = _make_engine_at(WorkflowState.REVIEWING)
        session = engine.transition_done([])
        assert session.state == WorkflowState.DONE

    def test_reviewing_to_failed(self):
        engine = _make_engine_at(WorkflowState.REVIEWING)
        session = engine.transition_failed("review failure")
        assert session.state == WorkflowState.FAILED

    # -- terminal states -----------------------------------------------------

    def test_done_is_terminal(self):
        engine = _make_engine_at(WorkflowState.DONE)
        with pytest.raises(ValueError, match="Invalid transition"):
            engine.transition_failed("can't")

    def test_failed_is_terminal(self):
        engine = _make_engine_at(WorkflowState.FAILED)
        with pytest.raises(ValueError, match="Invalid transition"):
            engine._transition(WorkflowState.DONE)

    # -- invalid transitions from every state --------------------------------

    @pytest.mark.parametrize(
        "from_state",
        [s for s in WorkflowState],
    )
    def test_invalid_transitions_raise(self, from_state: WorkflowState):
        """Every transition NOT in the allowed set must raise ValueError."""
        allowed = _VALID_TRANSITIONS[from_state]
        disallowed = set(WorkflowState) - allowed - {from_state}
        if not disallowed:
            return  # terminal states have no allowed targets; tested above

        engine = _make_engine_at(from_state)
        for target in disallowed:
            # Reset engine for each target
            engine = _make_engine_at(from_state)
            with pytest.raises(ValueError, match="Invalid transition"):
                engine._transition(target)

    # -- no session error ----------------------------------------------------

    def test_ensure_session_raises_without_session(self):
        engine = WorkflowEngine()
        with pytest.raises(RuntimeError, match="No active workflow session"):
            engine.transition_failed("oops")


# ---------------------------------------------------------------------------
# TestWorkflowPersistence
# ---------------------------------------------------------------------------


class TestWorkflowPersistence:
    """Test save/load round-trips, event logging, and edge cases."""

    def test_save_and_load_round_trip(self, tmp_path):
        persistence = WorkflowPersistence(tmp_path)
        session = WorkflowSession(
            id="abcd1234",
            goal="Test goal",
            state=WorkflowState.DELIBERATING,
            active_agents=["agent-a", "agent-b"],
            current_round=3,
        )
        persistence.save(session)
        loaded = persistence.load()
        assert loaded is not None
        assert loaded.id == "abcd1234"
        assert loaded.goal == "Test goal"
        assert loaded.state == WorkflowState.DELIBERATING
        assert loaded.active_agents == ["agent-a", "agent-b"]
        assert loaded.current_round == 3

    def test_load_returns_none_when_missing(self, tmp_path):
        persistence = WorkflowPersistence(tmp_path)
        assert persistence.load() is None

    def test_load_returns_none_on_corrupt_file(self, tmp_path):
        persistence = WorkflowPersistence(tmp_path)
        persistence.workflow_dir.mkdir(parents=True, exist_ok=True)
        persistence.session_path.write_text("{invalid json", encoding="utf-8")
        assert persistence.load() is None

    def test_append_and_load_events(self, tmp_path):
        persistence = WorkflowPersistence(tmp_path)
        events = [
            WorkflowEvent(event_type="started", data={"goal": "test"}),
            WorkflowEvent(event_type="transition", data={"from": "idle", "to": "preflight"}),
        ]
        for e in events:
            persistence.append_event(e)

        loaded = persistence.load_events()
        assert len(loaded) == 2
        assert loaded[0].event_type == "started"
        assert loaded[0].data == {"goal": "test"}
        assert loaded[1].event_type == "transition"
        assert loaded[1].data == {"from": "idle", "to": "preflight"}

    def test_load_events_returns_empty_when_missing(self, tmp_path):
        persistence = WorkflowPersistence(tmp_path)
        assert persistence.load_events() == []

    def test_clear_removes_files(self, tmp_path):
        persistence = WorkflowPersistence(tmp_path)
        session = WorkflowSession(id="abc", goal="g", state=WorkflowState.IDLE)
        persistence.save(session)
        persistence.append_event(WorkflowEvent(event_type="test"))
        assert persistence.session_path.exists()
        assert persistence.events_path.exists()

        persistence.clear()
        assert not persistence.session_path.exists()
        assert not persistence.events_path.exists()

    def test_round_trip_with_nested_data(self, tmp_path):
        """Full round-trip with blueprint, questions, decisions, work packages, results."""
        persistence = WorkflowPersistence(tmp_path)

        questions = [
            OpenQuestion(
                id="q1",
                question="Which framework?",
                options=["React", "Vue"],
                recommended_option="React",
                blocking=True,
                raised_by=["agent-a"],
            )
        ]
        decisions = [
            DecisionRecord(
                id="d1",
                decision="Use React",
                decided_by="user",
                question_id="q1",
            )
        ]
        blueprint = Blueprint(
            title="Full Plan",
            summary="A comprehensive plan",
            architecture=[
                ArchitectureComponent(
                    name="Frontend",
                    responsibility="UI layer",
                    owner_agent="agent-a",
                    dependencies=["API"],
                )
            ],
            data_flow=["Client -> API -> DB"],
            external_dependencies=["React"],
            risks=["Timeline"],
            acceptance_criteria=["All tests pass"],
            open_questions=questions,
        )
        work_packages = [
            WorkPackage(
                id="wp1",
                title="Build frontend",
                owner_agent="agent-a",
                objective="Create UI",
                scope=["components", "pages"],
                out_of_scope=["backend"],
                dependencies=[],
                expected_files=["src/App.tsx"],
                acceptance_criteria=["Renders correctly"],
                status=WorkStatus.PENDING,
            )
        ]
        results = [
            ExecutionResult(
                package_id="wp1",
                agent_name="agent-a",
                status=WorkStatus.DONE,
                summary="Completed",
                files_changed=["src/App.tsx"],
                decisions_made=decisions,
                blockers=[],
            )
        ]

        session = WorkflowSession(
            id="full1234",
            goal="Build the thing",
            state=WorkflowState.DONE,
            active_agents=["agent-a"],
            current_round=5,
            pending_questions=[],
            blueprint=blueprint,
            work_packages=work_packages,
            decisions=decisions,
            execution_results=results,
            events=[WorkflowEvent(event_type="done", data={"result": "success"})],
        )

        persistence.save(session)
        loaded = persistence.load()

        assert loaded is not None
        assert loaded.id == "full1234"
        assert loaded.state == WorkflowState.DONE
        assert loaded.blueprint is not None
        assert loaded.blueprint.title == "Full Plan"
        assert len(loaded.blueprint.architecture) == 1
        assert loaded.blueprint.architecture[0].name == "Frontend"
        assert loaded.blueprint.data_flow == ["Client -> API -> DB"]
        assert len(loaded.work_packages) == 1
        assert loaded.work_packages[0].status == WorkStatus.PENDING
        assert len(loaded.execution_results) == 1
        assert loaded.execution_results[0].status == WorkStatus.DONE
        assert loaded.execution_results[0].decisions_made[0].decision == "Use React"
        assert len(loaded.events) == 1
        assert loaded.events[0].event_type == "done"
        assert len(loaded.decisions) == 1
        assert loaded.decisions[0].question_id == "q1"

    def test_session_json_is_human_readable(self, tmp_path):
        """Verify the saved JSON uses indent=2 and non-ASCII characters are preserved."""
        persistence = WorkflowPersistence(tmp_path)
        session = WorkflowSession(
            id="test1234",
            goal="Probar la integración",
            state=WorkflowState.PREFLIGHT,
            active_agents=["agente-á"],
        )
        persistence.save(session)

        raw = persistence.session_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["goal"] == "Probar la integración"
        assert data["active_agents"] == ["agente-á"]
        # Check that it's indented (has newlines)
        assert "\n" in raw
