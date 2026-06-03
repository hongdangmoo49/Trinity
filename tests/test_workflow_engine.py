"""Tests for stateful workflow engine."""

import json

from trinity.models import ConsensusResult, DeliberationResult
from trinity.context.shared import SharedContextEngine
from trinity.workflow import (
    ExecutionResult,
    OpenQuestion,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
    WorkflowEngine,
    WorkflowState,
)


def test_workflow_engine_starts_and_persists_session(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")

    action = engine.handle_user_input("Design a bot", ["claude", "codex"])

    assert action.should_deliberate is True
    assert action.started_new_workflow is True
    assert action.prompt == "Design a bot"
    assert engine.state == WorkflowState.DELIBERATING
    assert engine.session.goal == "Design a bot"
    assert engine.session.active_agents == ["claude", "codex"]
    assert engine.state_file.exists()
    assert engine.events_file.exists()

    data = json.loads(engine.state_file.read_text(encoding="utf-8"))
    assert data["goal"] == "Design a bot"
    assert data["state"] == "deliberating"


def test_workflow_engine_loads_existing_session(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Keep this goal", ["claude"])

    loaded = WorkflowEngine(tmp_path / ".trinity")

    assert loaded.session.id == engine.session.id
    assert loaded.session.goal == "Keep this goal"
    assert loaded.state == WorkflowState.DELIBERATING


def test_pending_question_requires_explicit_answer(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design a bridge bot", ["claude"])
    original_id = engine.session.id
    engine.add_open_question(
        OpenQuestion(
            id="q-001",
            question="Optimize for cost or latency?",
            options=["cost", "latency"],
            recommended_option="cost",
        )
    )

    action = engine.handle_user_input("Use mixed score", ["claude"])

    assert engine.session.id == original_id
    assert action.should_deliberate is False
    assert action.decision_record is None
    assert "explicit answer" in action.message
    assert engine.session.decisions == []
    assert engine.session.pending_questions[0].status == "open"
    assert engine.state == WorkflowState.NEEDS_USER_DECISION


def test_answer_question_records_decision_without_new_workflow(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design a bridge bot", ["claude"])
    original_id = engine.session.id
    engine.add_open_question(
        OpenQuestion(
            id="q-001",
            question="Optimize for cost or latency?",
            options=["cost", "latency"],
            recommended_option="cost",
        )
    )

    action = engine.answer_question("q-001", "Use mixed score")

    assert engine.session.id == original_id
    assert action.should_deliberate is True
    assert action.decision_record is not None
    assert action.decision_record.question_id == "q-001"
    assert engine.session.decisions[0].decision == "Use mixed score"
    assert engine.session.pending_questions[0].status == "answered"
    assert engine.state == WorkflowState.DELIBERATING
    assert "Original goal" in action.prompt
    assert "Use mixed score" in action.prompt


def test_multiple_pending_questions_waits_for_remaining_answers(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude"])
    engine.add_open_question(OpenQuestion(id="q-001", question="First?"))
    engine.add_open_question(OpenQuestion(id="q-002", question="Second?"))

    action = engine.answer_question("1", "First answer")

    assert action.should_deliberate is False
    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    assert len(engine.pending_questions) == 1
    assert engine.pending_questions[0].id == "q-002"


def test_answer_question_option_records_numbered_option(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude"])
    engine.add_open_question(
        OpenQuestion(
            id="q-001",
            question="Which API?",
            options=["LI.FI", "Socket"],
        )
    )

    action = engine.answer_question_option("2")

    assert action.should_deliberate is True
    assert engine.decisions[0].question_id == "q-001"
    assert engine.decisions[0].decision == "Socket"


def test_answer_question_replace_updates_existing_decision(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude"])
    engine.add_open_question(OpenQuestion(id="q-001", question="Which API?"))

    first = engine.answer_question("q-001", "LI.FI")
    updated = engine.answer_question("q-001", "Socket", replace=True)

    assert first.decision_record is not None
    assert updated.decision_record is not None
    assert updated.replaced_decision is True
    assert len(engine.decisions) == 1
    assert engine.decisions[0].id == first.decision_record.id
    assert engine.decisions[0].decision == "Socket"


def test_mark_deliberation_result_updates_state(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude"])
    result = DeliberationResult(
        user_prompt="Design",
        rounds_completed=1,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=1,
            total_agents=1,
            opinions={"claude": "yes"},
            summary="Blueprint summary",
        ),
    )

    engine.mark_deliberation_result(result)

    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert engine.session.current_round == 1
    assert engine.session.blueprint is not None
    assert engine.session.blueprint.title == "Consensus Blueprint"
    assert engine.session.blueprint.summary == "Blueprint summary"


def test_mark_deliberation_result_applies_structured_blueprint(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude"])
    result = DeliberationResult(
        user_prompt="Design",
        rounds_completed=1,
        consensus=None,
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

    engine.mark_deliberation_result(result)

    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert engine.session.blueprint is not None
    assert engine.session.blueprint.title == "Route Bot"
    assert len(engine.work_packages) == 1
    assert engine.work_packages[0].owner_agent == "claude"
    assert engine.work_packages[0].requires_execution is False

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.session.blueprint is not None
    assert loaded.session.blueprint.title == "Route Bot"


def test_mark_deliberation_result_waits_on_structured_question(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["gemini"])
    result = DeliberationResult(
        user_prompt="Design",
        rounds_completed=1,
        consensus=None,
        metadata={
            "structured_consensus": {
                "reached": False,
                "final_blueprint": None,
                "open_questions": [
                    {
                        "id": "q-gemini-001",
                        "question": "Optimize for cost or latency?",
                        "options": ["cost", "latency", "mixed"],
                        "recommended_option": "mixed",
                        "blocking": True,
                        "raised_by": ["gemini"],
                        "rationale": "Scoring depends on this choice.",
                        "status": "open",
                    }
                ],
            }
        },
    )

    engine.mark_deliberation_result(result)

    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    assert len(engine.pending_questions) == 1
    assert engine.pending_questions[0].question == "Optimize for cost or latency?"


def test_record_execution_results_moves_to_reviewing(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            requires_execution=True,
        )
    ]
    engine.begin_execution()

    engine.record_execution_results([
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.DONE,
            summary="Implemented route bot.",
            files_changed=["src/routes.py"],
        )
    ])

    assert engine.state == WorkflowState.REVIEWING
    assert engine.session.work_packages[0].status == WorkStatus.DONE
    assert engine.execution_results[0].summary == "Implemented route bot."
    assert len(engine.review_packages) == 1
    assert engine.review_packages[0]["package_id"] == "WP-001"
    assert engine.review_packages[0]["self_review"] is True

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.state == WorkflowState.REVIEWING
    assert loaded.execution_results[0].files_changed == ["src/routes.py"]
    assert loaded.review_packages[0]["package_id"] == "WP-001"


def test_record_execution_results_persists_subtasks(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement", ["codex"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement.",
        )
    ]

    engine.record_execution_results([
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.DONE,
            summary="Done.",
            subtasks=[
                SubtaskResult(
                    id="ST-001",
                    parent_package_id="WP-001",
                    parent_agent="codex",
                    delegated_to="code-search tool",
                    objective="Find patterns.",
                    result_summary="Found registry.",
                    status=WorkStatus.DONE,
                    files_changed=["src/routes.py"],
                )
            ],
        )
    ])

    assert len(engine.subtask_results) == 1
    assert engine.subtask_results[0].delegated_to == "code-search tool"

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert len(loaded.subtask_results) == 1
    assert loaded.subtask_results[0].files_changed == ["src/routes.py"]


def test_record_execution_results_marks_failure(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement", ["codex"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement.",
        )
    ]

    engine.record_execution_results([
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.FAILED,
            summary="Provider failed.",
        )
    ])

    assert engine.state == WorkflowState.FAILED
    assert engine.session.work_packages[0].status == WorkStatus.FAILED


def test_record_execution_results_marks_blocked_as_user_decision(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement", ["codex"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement.",
        )
    ]

    engine.record_execution_results([
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.BLOCKED,
            summary="Missing credential.",
            blockers=["Missing credential."],
        )
    ])

    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    assert engine.session.work_packages[0].status == WorkStatus.BLOCKED


def test_sync_shared_ledger_restores_from_structured_session(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement shared ledger", ["codex"])
    engine.session.current_round = 2
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="ledger package",
            owner_agent="codex",
            objective="Render workflow state.",
            status=WorkStatus.DONE,
        )
    ]
    engine.session.execution_results = [
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.DONE,
            summary="Rendered ledger.",
        )
    ]
    engine.save()

    shared = SharedContextEngine(tmp_path / ".trinity" / "shared.md")
    shared.write(
        "# Corrupted Shared\n\n"
        "## Round 1 Opinions\n"
        "### codex\n"
        "Keep this freeform opinion.\n\n"
        "## Response Diagnostics\n"
        "Provider note.\n"
    )

    loaded = WorkflowEngine(tmp_path / ".trinity")
    loaded.sync_shared_ledger(shared)

    content = shared.read()
    assert content.startswith("# Shared Context\n")
    assert "## Workflow State" in content
    assert "- id: " in content
    assert "- state: deliberating" in content
    assert "## Work Packages" in content
    assert "### WP-001: ledger package" in content
    assert "## Task Results" in content
    assert "Rendered ledger." in content
    assert "## Round Opinions" in content
    assert "Keep this freeform opinion." in content
    assert "## Response Diagnostics" in content
    assert "Provider note." in content
