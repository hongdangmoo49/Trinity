"""Tests for v0.7.0 workflow engine data models."""

import json
import time

import pytest

from trinity.models import (
    ArchitectureComponent,
    Blueprint,
    DecisionRecord,
    ExecutionResult,
    OpenQuestion,
    ProviderState,
    ReadinessResult,
    StructuredConsensusResult,
    VoteType,
    WorkflowEvent,
    WorkflowSession,
    WorkflowState,
    WorkPackage,
    WorkStatus,
)


# -- Enum value tests --------------------------------------------------------


class TestWorkflowState:
    def test_all_values_exist(self):
        expected = [
            "idle", "preflight", "deliberating", "needs_user_decision",
            "blueprint_ready", "executing", "reviewing", "done", "failed",
        ]
        values = [s.value for s in WorkflowState]
        for v in expected:
            assert v in values


class TestProviderState:
    def test_all_values_exist(self):
        expected = [
            "ready", "auth_required", "model_loading",
            "workspace_trust_required", "cli_banner_only",
            "prompt_not_sent", "process_dead", "unknown_not_ready",
        ]
        values = [s.value for s in ProviderState]
        for v in expected:
            assert v in values


class TestVoteType:
    def test_all_values_exist(self):
        expected = [
            "approve", "approve_with_changes",
            "blocked_by_question", "reject",
        ]
        values = [v.value for v in VoteType]
        for v in expected:
            assert v in values


class TestWorkStatus:
    def test_all_values_exist(self):
        expected = [
            "pending", "running", "waiting_on_decision",
            "blocked", "done", "failed", "needs_review",
        ]
        values = [s.value for s in WorkStatus]
        for v in expected:
            assert v in values


# -- Dataclass tests ---------------------------------------------------------


class TestReadinessResult:
    def test_ready(self):
        r = ReadinessResult(
            agent_name="claude",
            ready=True,
            state=ProviderState.READY,
            reason="CLI responding",
            action_hint="",
        )
        assert r.ready
        assert r.state == ProviderState.READY
        assert r.excerpt == ""

    def test_auth_required(self):
        r = ReadinessResult(
            agent_name="codex",
            ready=False,
            state=ProviderState.AUTH_REQUIRED,
            reason="No API key found",
            action_hint="Run: codex auth login",
        )
        assert not r.ready
        assert r.state == ProviderState.AUTH_REQUIRED


class TestOpenQuestion:
    def test_blocking_default(self):
        q = OpenQuestion(id="q1", question="Which DB?")
        assert q.blocking is True
        assert q.options == []
        assert q.raised_by == []

    def test_non_blocking(self):
        q = OpenQuestion(id="q2", question="Color theme?", blocking=False)
        assert not q.blocking

    def test_to_dict_from_dict_roundtrip(self):
        q = OpenQuestion(
            id="q3",
            question="Framework?",
            options=["FastAPI", "Flask"],
            recommended_option="FastAPI",
            blocking=True,
            raised_by=["claude", "codex"],
            rationale="Core decision",
        )
        d = q.to_dict()
        q2 = OpenQuestion.from_dict(d)
        assert q2.id == q.id
        assert q2.options == q.options
        assert q2.recommended_option == q.recommended_option
        assert q2.raised_by == q.raised_by

    def test_from_dict_ignores_extra_fields(self):
        q = OpenQuestion.from_dict({
            "id": "q4",
            "question": "test",
            "unknown_field": "should be ignored",
        })
        assert q.id == "q4"


class TestDecisionRecord:
    def test_user_decision(self):
        d = DecisionRecord(
            id="d1",
            decision="Use FastAPI",
            decided_by="user",
            rationale="Team familiarity",
            question_id="q3",
        )
        assert d.decided_by == "user"
        assert d.timestamp > 0

    def test_to_dict_from_dict_roundtrip(self):
        d = DecisionRecord(
            id="d2",
            decision="Use SQLite",
            decided_by="codex",
            rationale="Simplicity",
        )
        d2 = DecisionRecord.from_dict(d.to_dict())
        assert d2.id == d.id
        assert d2.decided_by == d.decided_by


class TestBlueprint:
    def test_to_dict_from_dict_reconstructs_nested(self):
        bp = Blueprint(
            title="Test Blueprint",
            summary="A test",
            architecture=[
                ArchitectureComponent(
                    name="API",
                    responsibility="Serve REST endpoints",
                    owner_agent="claude",
                    dependencies=["DB"],
                ),
            ],
            data_flow=["Client -> API -> DB"],
            open_questions=[
                OpenQuestion(id="q1", question="Auth method?"),
            ],
        )
        d = bp.to_dict()
        bp2 = Blueprint.from_dict(d)
        assert bp2.title == bp.title
        assert len(bp2.architecture) == 1
        assert bp2.architecture[0].name == "API"
        assert bp2.architecture[0].dependencies == ["DB"]
        assert len(bp2.open_questions) == 1
        assert bp2.open_questions[0].id == "q1"


class TestStructuredConsensusResult:
    def test_with_blueprint(self):
        bp = Blueprint(title="T", summary="S", architecture=[])
        result = StructuredConsensusResult(
            reached=True,
            vote_count={"approve": 2, "reject": 1},
            final_blueprint=bp,
            open_questions=[],
        )
        assert result.reached
        assert result.final_blueprint is not None
        assert result.blockers == []

    def test_without_blueprint(self):
        result = StructuredConsensusResult(
            reached=False,
            vote_count={"approve": 1, "reject": 2},
            final_blueprint=None,
            open_questions=[OpenQuestion(id="q1", question="What?")],
            blockers=["Agent codex rejected"],
        )
        assert not result.reached
        assert result.final_blueprint is None
        assert len(result.blockers) == 1


class TestWorkPackage:
    def test_creation(self):
        wp = WorkPackage(
            id="wp1",
            title="Implement auth",
            owner_agent="claude",
            objective="Add JWT authentication",
        )
        assert wp.status == WorkStatus.PENDING
        assert wp.scope == []
        assert wp.dependencies == []

    def test_to_dict_converts_status_enum(self):
        wp = WorkPackage(
            id="wp1",
            title="Test",
            owner_agent="codex",
            objective="Do stuff",
            status=WorkStatus.RUNNING,
        )
        d = wp.to_dict()
        assert d["status"] == "running"

    def test_from_dict_roundtrip(self):
        wp = WorkPackage(
            id="wp1",
            title="Test",
            owner_agent="codex",
            objective="Do stuff",
            scope=["a.py", "b.py"],
            status=WorkStatus.RUNNING,
        )
        wp2 = WorkPackage.from_dict(wp.to_dict())
        assert wp2.id == wp.id
        assert wp2.status == WorkStatus.RUNNING
        assert wp2.scope == ["a.py", "b.py"]


class TestExecutionResult:
    def test_successful(self):
        er = ExecutionResult(
            package_id="wp1",
            agent_name="claude",
            status=WorkStatus.DONE,
            summary="Completed auth module",
            files_changed=["auth.py", "tests/test_auth.py"],
        )
        assert er.status == WorkStatus.DONE
        assert len(er.files_changed) == 2
        assert er.blockers == []


class TestWorkflowEvent:
    def test_state_change(self):
        ev = WorkflowEvent(
            event_type="state_change",
            data={"from": "idle", "to": "preflight"},
        )
        assert ev.event_type == "state_change"
        assert ev.data["from"] == "idle"
        assert ev.timestamp > 0

    def test_to_dict_from_dict_roundtrip(self):
        ev = WorkflowEvent(
            event_type="round_complete",
            data={"round": 3},
        )
        ev2 = WorkflowEvent.from_dict(ev.to_dict())
        assert ev2.event_type == ev.event_type
        assert ev2.data["round"] == 3


class TestWorkflowSession:
    def test_minimal_creation(self):
        session = WorkflowSession(id="s1", goal="Build API")
        assert session.state == WorkflowState.IDLE
        assert session.active_agents == []
        assert session.current_round == 0
        assert session.blueprint is None
        assert session.created_at > 0

    def test_to_dict_from_dict_json_roundtrip(self):
        session = WorkflowSession(
            id="s1",
            goal="Build API",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude", "codex"],
            current_round=2,
            pending_questions=[
                OpenQuestion(id="q1", question="Framework?", options=["FastAPI", "Flask"]),
            ],
            blueprint=Blueprint(
                title="API Blueprint",
                summary="REST API design",
                architecture=[
                    ArchitectureComponent(name="Router", responsibility="Route requests"),
                ],
                data_flow=["Client -> Router -> Handler"],
            ),
            work_packages=[
                WorkPackage(
                    id="wp1",
                    title="Auth",
                    owner_agent="claude",
                    objective="Implement JWT",
                    status=WorkStatus.RUNNING,
                ),
            ],
            decisions=[
                DecisionRecord(id="d1", decision="Use FastAPI", decided_by="user"),
            ],
            execution_results=[
                ExecutionResult(
                    package_id="wp0",
                    agent_name="codex",
                    status=WorkStatus.DONE,
                    summary="Setup project",
                    files_changed=["pyproject.toml"],
                    decisions_made=[
                        DecisionRecord(id="d0", decision="Use src layout", decided_by="codex"),
                    ],
                ),
            ],
            events=[
                WorkflowEvent(event_type="state_change", data={"from": "idle", "to": "preflight"}),
            ],
        )

        # Serialize to JSON and back
        json_str = json.dumps(session.to_dict())
        restored = WorkflowSession.from_dict(json.loads(json_str))

        # Verify top-level fields
        assert restored.id == "s1"
        assert restored.goal == "Build API"
        assert restored.state == WorkflowState.DELIBERATING
        assert restored.active_agents == ["claude", "codex"]
        assert restored.current_round == 2

        # Verify nested pending_questions
        assert len(restored.pending_questions) == 1
        assert restored.pending_questions[0].question == "Framework?"
        assert restored.pending_questions[0].options == ["FastAPI", "Flask"]

        # Verify nested blueprint
        assert restored.blueprint is not None
        assert restored.blueprint.title == "API Blueprint"
        assert len(restored.blueprint.architecture) == 1
        assert restored.blueprint.architecture[0].name == "Router"

        # Verify nested work_packages
        assert len(restored.work_packages) == 1
        assert restored.work_packages[0].status == WorkStatus.RUNNING

        # Verify nested decisions
        assert len(restored.decisions) == 1
        assert restored.decisions[0].decision == "Use FastAPI"

        # Verify nested execution_results
        assert len(restored.execution_results) == 1
        assert restored.execution_results[0].status == WorkStatus.DONE
        assert restored.execution_results[0].files_changed == ["pyproject.toml"]
        assert len(restored.execution_results[0].decisions_made) == 1
        assert restored.execution_results[0].decisions_made[0].decision == "Use src layout"

        # Verify nested events
        assert len(restored.events) == 1
        assert restored.events[0].event_type == "state_change"

    def test_from_dict_ignores_extra_fields(self):
        data = {
            "id": "s2",
            "goal": "Test",
            "state": "idle",
            "future_field": "should be ignored",
        }
        session = WorkflowSession.from_dict(data)
        assert session.id == "s2"
        assert session.state == WorkflowState.IDLE
