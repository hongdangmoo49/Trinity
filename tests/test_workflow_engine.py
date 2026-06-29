"""Tests for stateful workflow engine."""

import json

from trinity.models import ConsensusResult, DeliberationResult, TaskAssignment
from trinity.context.shared import SharedContextEngine
from trinity.workflow import (
    Blueprint,
    ExecutionResult,
    OpenQuestion,
    ReviewDepth,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
    SubtaskResult,
    WorkPackage,
    WorkStatus,
    WorkflowEngine,
    WorkflowState,
    classify_blueprint_followup_action,
    classify_execution_intent,
)
from trinity.workflow.structured import StructuredConsensusSynthesizer
from trinity.workflow.intent import requires_execution_for_deliberation


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


def test_workflow_engine_records_target_agents_and_model_overrides(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")

    action = engine.handle_user_input(
        "Ask codex",
        ["claude", "codex"],
        target_agents=("codex",),
        agent_model_overrides={"claude": "ignored-sonnet", "codex": "gpt-5"},
    )

    assert action.should_deliberate is True
    assert action.target_agents == ("codex",)
    assert action.agent_selection_mode == "targeted"
    assert action.agent_model_overrides == {"codex": "gpt-5"}
    assert engine.session.active_agents == ["claude", "codex"]
    assert engine.session.last_target_agents == ["codex"]
    assert engine.session.agent_model_overrides == {"codex": "gpt-5"}

    data = json.loads(engine.state_file.read_text(encoding="utf-8"))
    assert data["last_target_agents"] == ["codex"]
    assert data["agent_model_overrides"] == {"codex": "gpt-5"}


def test_workflow_engine_loads_existing_session(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Keep this goal", ["claude"])

    loaded = WorkflowEngine(tmp_path / ".trinity")

    assert loaded.session.id == engine.session.id
    assert loaded.session.goal == "Keep this goal"
    assert loaded.state == WorkflowState.DELIBERATING


def test_pending_question_plain_text_answers_next_question(tmp_path):
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
    assert action.should_deliberate is True
    assert action.decision_record is not None
    assert action.decision_record.question_id == "q-001"
    assert action.decision_record.decision == "Use mixed score"
    assert engine.session.pending_questions[0].status == "answered"
    assert engine.state == WorkflowState.DELIBERATING


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
    assert "executable work packages" in action.prompt
    assert "expected files" in action.prompt


def test_answer_question_preserves_target_agents_and_model_overrides(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start(
        "Design a bridge bot",
        ["claude", "codex"],
        target_agents=("codex",),
        agent_model_overrides={"codex": "gpt-5", "claude": "ignored"},
    )
    engine.add_open_question(
        OpenQuestion(
            id="q-001",
            question="Optimize for cost or latency?",
            options=["cost", "latency"],
        )
    )

    action = engine.answer_question("q-001", "Use mixed score")

    assert action.should_deliberate is True
    assert action.target_agents == ("codex",)
    assert action.agent_selection_mode == "targeted"
    assert action.agent_model_overrides == {"codex": "gpt-5"}
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
    transcript_events = [
        event
        for event in engine.persistence.load_events()
        if event["event"] == "central_conversation_recorded"
    ]
    assert transcript_events
    assert transcript_events[-1]["data"]["title"] == "Central Agent Response"
    assert "Blueprint summary" in transcript_events[-1]["data"]["body"]


def test_mark_deliberation_result_records_provider_metadata(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["codex"])
    result = DeliberationResult(
        user_prompt="Design",
        rounds_completed=1,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=1,
            total_agents=1,
            opinions={"codex": "yes"},
            summary="Blueprint summary",
        ),
        metadata={
            "provider_sessions": {
                "codex:key": {
                    "provider": "codex",
                    "agent_name": "codex",
                    "session_key": "codex:key",
                    "provider_session_id": "thread-1",
                    "session_kind": "codex_thread",
                    "access": "read-only",
                },
                "central:key": {
                    "provider": "codex",
                    "agent_name": "central:codex",
                    "session_key": "central:key",
                    "provider_session_id": "central-thread-1",
                    "session_kind": "codex_thread",
                    "access": "read-only",
                }
            },
            "runtime_models": {
                "codex": {
                    "provider": "codex",
                    "agent_name": "codex",
                    "configured_model": "default",
                    "actual_model": "gpt-5.5",
                    "context_window": 272000,
                    "budget_source": "local_cli_cache",
                    "confidence": "medium-high",
                },
                "central:codex": {
                    "provider": "codex",
                    "agent_name": "central:codex",
                    "configured_model": "default",
                    "actual_model": "gpt-5.5",
                    "context_window": 272000,
                    "budget_source": "local_cli_cache",
                    "confidence": "medium-high",
                }
            },
        },
    )

    engine.mark_deliberation_result(result)

    assert engine.session.provider_sessions["codex:key"].provider_session_id == "thread-1"
    assert (
        engine.session.provider_sessions["central:key"].provider_session_id
        == "central-thread-1"
    )
    assert engine.session.runtime_models["codex"].actual_model == "gpt-5.5"
    assert engine.session.runtime_models["central:codex"].actual_model == "gpt-5.5"
    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.session.provider_sessions["codex:key"].provider_session_id == "thread-1"
    assert (
        loaded.session.provider_sessions["central:key"].provider_session_id
        == "central-thread-1"
    )
    assert loaded.session.runtime_models["codex"].context_window == 272000
    assert loaded.session.runtime_models["central:codex"].context_window == 272000


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


def test_mark_deliberation_result_gates_retryable_provider_failures(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude", "antigravity"])
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
            },
            "provider_failures": [
                {
                    "agent": "antigravity",
                    "status": "auth_required",
                    "classification": "auth_wait",
                    "reasons": ["login required"],
                    "retryable": True,
                }
            ],
        },
    )

    engine.mark_deliberation_result(result)

    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    assert engine.session.blueprint is None
    assert engine.session.provider_error_gate["failed_agents"] == ["antigravity"]
    assert engine.session.provider_error_gate["successful_opinions"] == {"claude": "yes"}
    assert engine.pending_questions[0].id == "q-provider-error-retry"
    assert engine.pending_questions[0].options == [
        "Retry failed providers",
        "Continue without failed providers",
        "Stop workflow",
    ]


def test_provider_error_gate_continue_applies_pending_deliberation_result(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude", "antigravity"])
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
            },
            "provider_failures": [
                {
                    "agent": "antigravity",
                    "status": "auth_required",
                    "classification": "auth_wait",
                    "reasons": [],
                    "retryable": True,
                }
            ],
        },
    )
    engine.mark_deliberation_result(result)

    action = engine.answer_question(
        "q-provider-error-retry",
        "Continue without failed providers",
    )

    assert action.should_deliberate is False
    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert engine.session.provider_error_gate == {}
    assert engine.session.blueprint is not None
    assert engine.session.blueprint.title == "Route Bot"


def test_provider_error_gate_single_failed_provider_omits_continue(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude"])
    result = DeliberationResult(
        user_prompt="Design",
        rounds_completed=1,
        consensus=None,
        metadata={
            "provider_failures": [
                {
                    "agent": "claude",
                    "status": "invalid",
                    "classification": "agent_error",
                    "reasons": ["exit code 1"],
                    "retryable": True,
                }
            ],
        },
    )

    engine.mark_deliberation_result(result)

    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    assert engine.pending_questions[0].options == [
        "Retry failed providers",
        "Stop workflow",
    ]


def test_provider_error_gate_retry_targets_failed_agents_with_merge_context(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["claude", "antigravity"])
    result = DeliberationResult(
        user_prompt="Design",
        rounds_completed=1,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=1,
            total_agents=1,
            opinions={"claude": "vote rationale"},
            summary="Provisional summary",
        ),
        metadata={
            "provider_successful_opinions": {"claude": "Preserved Claude plan."},
            "provider_error_gate_status": "provisional",
            "provider_failures": [
                {
                    "agent": "antigravity",
                    "status": "auth_required",
                    "classification": "auth_wait",
                    "reasons": ["login required"],
                    "retryable": True,
                }
            ],
        },
    )
    engine.mark_deliberation_result(result)

    action = engine.answer_question(
        "q-provider-error-retry",
        "Retry failed providers",
    )

    assert action.should_deliberate is True
    assert action.target_agents == ("antigravity",)
    assert action.agent_selection_mode == "targeted"
    assert action.provider_retry_merge_context == {
        "successful_opinions": {"claude": "Preserved Claude plan."},
        "retry_agents": ["antigravity"],
        "original_prompt": "Design",
        "source_question_id": "q-provider-error-retry",
    }
    assert "Previously successful providers preserved" in action.prompt
    assert engine.state == WorkflowState.DELIBERATING


def test_structured_followup_with_korean_modified_sections_decomposes_packages(tmp_path):
    synthesizer = StructuredConsensusSynthesizer()
    structured = synthesizer.evaluate(
        {
            "claude": """\
## 수정된 제안: 뱀파이어 서바이벌형 탄막 슈팅 게임 — 설계 확정

### 요약
Godot 기반 싱글 세션 생존 슈팅.

### 확정 아키텍처
- GameLoop: 런 상태와 난이도 곡선을 관리한다.

### 데이터 흐름
```
게임 시작 -> 캐릭터 선택 -> 30분 타이머 시작
매 킬: XP 드롭 -> 레벨업 -> 보상 선택
```

### 외부 의존성 (최종)
- Godot 4.4+
- GodotSteam

### 리스크 (업데이트)
- 대량 적과 탄환 처리 성능 저하

### 수용 기준 (확정)
- 1920x1080에서 6배 정수 배율
- 적 200 + 총알 1000 동시 처리

VOTE: APPROVE
"""
        }
    ).to_dict()
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("뱀파이어 서바이벌형 탄막 슈팅 게임을 개발해라", ["claude", "codex"])
    result = DeliberationResult(
        user_prompt="사용자 결정 반영",
        rounds_completed=2,
        consensus=None,
        metadata={"structured_consensus": structured},
    )

    engine.mark_deliberation_result(result)

    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert engine.session.blueprint is not None
    assert engine.session.blueprint.data_flow == [
        "게임 시작 -> 캐릭터 선택 -> 30분 타이머 시작",
        "매 킬: XP 드롭 -> 레벨업 -> 보상 선택",
    ]
    assert engine.session.blueprint.external_dependencies == ["Godot 4.4+", "GodotSteam"]
    titles = [package.title for package in engine.work_packages]
    assert titles == [
        "GameLoop",
        "External dependency adapters",
        "Risk and validation coverage",
    ]
    game_loop = engine.work_packages[0]
    assert "Integration flow: 게임 시작 -> 캐릭터 선택 -> 30분 타이머 시작" in game_loop.scope
    assert "Integration flow: 매 킬: XP 드롭 -> 레벨업 -> 보상 선택" in game_loop.scope
    assert all("###" not in item for item in engine.session.blueprint.data_flow)
    assert all("VOTE:" not in item for item in engine.session.blueprint.acceptance_criteria)


def test_blueprint_ready_plain_text_continues_existing_workflow(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design a route bot", ["claude"])
    original_id = engine.session.id
    engine.session.blueprint = Blueprint(
        title="Route Bot",
        summary="Find bridge routes.",
        acceptance_criteria=["rank paths"],
    )
    engine.set_state(WorkflowState.BLUEPRINT_READY, reason="test blueprint ready")

    action = engine.handle_user_input("Add Telegram alerts", ["claude"])

    assert engine.session.id == original_id
    assert action.should_deliberate is True
    assert action.started_new_workflow is False
    assert engine.state == WorkflowState.DELIBERATING
    assert "Continue the existing workflow" in action.prompt
    assert "Add Telegram alerts" in action.prompt


def test_reviewing_followup_keeps_existing_workflow_and_target_workspace(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Build a game", ["claude", "codex"])
    original_id = engine.session.id
    target = tmp_path / "testfolder"
    engine.session.blueprint = Blueprint(
        title="Game",
        summary="Build the game project.",
        acceptance_criteria=["runs"],
    )
    engine.set_target_workspace(target)
    engine.set_state(WorkflowState.REVIEWING, reason="implementation completed")

    action = engine.handle_user_input("테스트를 해라", ["claude", "codex"])

    assert engine.session.id == original_id
    assert engine.session.target_workspace == target.resolve()
    assert action.should_deliberate is True
    assert action.started_new_workflow is False
    assert engine.state == WorkflowState.DELIBERATING
    assert "테스트를 해라" in action.prompt


def test_followup_result_can_execute_without_reselecting_target_workspace(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Build a game", ["claude"])
    target = tmp_path / "testfolder"
    engine.session.blueprint = Blueprint(
        title="Game",
        summary="Build the game project.",
        acceptance_criteria=["runs"],
    )
    engine.set_target_workspace(target)
    engine.set_state(WorkflowState.REVIEWING, reason="implementation completed")
    action = engine.handle_user_input("테스트를 해라", ["claude"])
    assert action.should_deliberate is True
    result = DeliberationResult(
        user_prompt="테스트를 해라",
        rounds_completed=1,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=1,
            total_agents=1,
            opinions={"claude": "agree"},
            summary="Add and run project tests.",
        ),
    )

    engine.mark_deliberation_result(result)
    execute = engine.enable_execution_for_current_blueprint("테스트 실행")

    assert engine.session.target_workspace == target.resolve()
    assert execute.execution_requested is True
    assert execute.target_workspace_required is False


def test_blueprint_ready_execute_text_requests_execution_without_new_deliberation(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design a route bot", ["claude", "codex"])
    original_id = engine.session.id
    engine.session.blueprint = Blueprint(
        title="Route Bot",
        summary="Find bridge routes.",
        acceptance_criteria=["rank paths"],
    )
    engine.session.work_packages = engine.decomposer.decompose(
        engine.session.blueprint,
        ["claude", "codex"],
        requires_execution=False,
    )
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.set_state(WorkflowState.BLUEPRINT_READY, reason="test blueprint ready")

    action = engine.handle_user_input("개발해라", ["claude", "codex"])

    assert engine.session.id == original_id
    assert action.should_deliberate is False
    assert action.execution_requested is True
    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert all(package.requires_execution for package in engine.work_packages)
    assert engine.decisions[0].decision == "개발해라"


def test_enable_execution_regenerates_current_blueprint_packages(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design a route bot", ["claude"])
    engine.session.blueprint = Blueprint(
        title="Route Bot",
        summary="Find bridge routes.",
        acceptance_criteria=["rank paths"],
    )
    engine.session.work_packages = engine.decomposer.decompose(
        engine.session.blueprint,
        ["claude"],
        requires_execution=False,
    )
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.set_state(WorkflowState.BLUEPRINT_READY, reason="test blueprint ready")

    action = engine.enable_execution_for_current_blueprint("Implement in Python")

    assert action.should_deliberate is False
    assert action.execution_requested is True
    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert len(engine.work_packages) == 1
    assert engine.work_packages[0].requires_execution is True
    assert engine.work_packages[0].expected_files != ["docs/"]
    assert engine.decisions[0].decision == "Implement in Python"
    artifact_path = tmp_path / ".trinity" / "workflow" / "blueprints" / f"{engine.session.id}.json"
    assert artifact_path.exists()
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["blueprint"]["title"] == "Route Bot"


def test_enable_execution_requires_target_workspace(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design a route bot", ["claude"])
    engine.session.blueprint = Blueprint(
        title="Route Bot",
        summary="Find bridge routes.",
        acceptance_criteria=["rank paths"],
    )
    engine.session.work_packages = engine.decomposer.decompose(
        engine.session.blueprint,
        ["claude"],
        requires_execution=False,
    )
    engine.set_state(WorkflowState.BLUEPRINT_READY, reason="test blueprint ready")

    action = engine.enable_execution_for_current_blueprint("Implement in Python")

    assert action.should_deliberate is False
    assert action.execution_requested is False
    assert action.target_workspace_required is True
    assert all(not package.requires_execution for package in engine.work_packages)


def test_target_workspace_persists_with_session(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design a route bot", ["claude"])
    target = tmp_path / "route-bot"

    engine.set_target_workspace(target)

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.session.target_workspace == target.resolve()


def test_start_carries_idle_preselected_target_workspace_without_changing_prompt(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    target = tmp_path / "route-bot"
    engine.set_target_workspace(target)

    action = engine.start("Design route bot", ["claude"])

    assert action.prompt == "Design route bot"
    assert engine.session.goal == "Design route bot"
    assert engine.session.target_workspace == target.resolve()


def test_question_answer_continuation_includes_target_workspace(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design route bot", ["claude"])
    target = tmp_path / "route-bot"
    engine.set_target_workspace(target)
    engine.add_open_question(
        OpenQuestion(
            id="q-001",
            question="Optimize for cost or latency?",
        )
    )

    action = engine.answer_question("q-001", "Use a mixed score.")

    assert action.should_deliberate is True
    assert "Target Workspace Context" in action.prompt
    assert str(target.resolve()) in action.prompt
    assert "Use a mixed score." in action.prompt


def test_question_answer_continuation_includes_project_intake(tmp_path):
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "project-intake.md").write_text(
        "# Project Intake\n\n- Mode: existing\n- Target workspace: `/tmp/app`\n",
        encoding="utf-8",
    )
    engine = WorkflowEngine(state)
    engine.start("Design route bot", ["claude"])
    engine.add_open_question(
        OpenQuestion(
            id="q-001",
            question="Optimize for cost or latency?",
        )
    )

    action = engine.answer_question("q-001", "Use a mixed score.")

    assert action.should_deliberate is True
    assert "Project Intake Context" in action.prompt
    assert "- Mode: existing" in action.prompt
    assert "Use a mixed score." in action.prompt


def test_blueprint_followup_continuation_includes_target_workspace(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design route bot", ["claude"])
    target = tmp_path / "route-bot"
    engine.set_target_workspace(target)
    engine.session.blueprint = Blueprint(
        title="Route Bot",
        summary="Finds bridge routes.",
        acceptance_criteria=["returns ranked paths"],
    )
    engine.set_state(WorkflowState.BLUEPRINT_READY, reason="test")

    action = engine.continue_from_blueprint("Add a CLI summary.", ["claude"])

    assert action.should_deliberate is True
    assert "Target Workspace Context" in action.prompt
    assert str(target.resolve()) in action.prompt
    assert "Add a CLI summary." in action.prompt


def test_mark_deliberation_result_waits_on_structured_question(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["antigravity"])
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
                        "id": "q-antigravity-001",
                        "question": "Optimize for cost or latency?",
                        "options": ["cost", "latency", "mixed"],
                        "recommended_option": "mixed",
                        "blocking": True,
                        "raised_by": ["antigravity"],
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


def test_mark_deliberation_result_renumbers_duplicate_question_ids(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Design", ["codex"])
    engine.add_open_question(
        OpenQuestion(
            id="oq-001",
            question="Capital range?",
            options=["small", "medium"],
        )
    )
    engine.answer_question("oq-001", "medium")
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
                        "id": "oq-001",
                        "question": "Broker API style?",
                        "options": ["REST", "COM/OCX"],
                        "recommended_option": "REST",
                        "blocking": True,
                        "raised_by": ["codex"],
                        "rationale": "Execution path depends on the broker API.",
                        "status": "open",
                    }
                ],
            }
        },
    )

    engine.mark_deliberation_result(result)

    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    open_questions = engine.pending_questions
    assert len(open_questions) == 1
    assert open_questions[0].id == "oq-001-2"
    assert open_questions[0].question == "Broker API style?"


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
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.begin_execution()

    engine.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="Implemented route bot.",
                files_changed=["src/routes.py"],
            )
        ]
    )

    assert engine.state == WorkflowState.REVIEWING
    assert engine.session.work_packages[0].status == WorkStatus.DONE
    assert engine.execution_results[0].summary == "Implemented route bot."
    assert len(engine.review_packages) == 1
    assert engine.review_packages[0]["package_id"] == "WP-001"
    assert engine.review_packages[0]["reviewer_agent"] == "codex"
    assert engine.review_packages[0]["self_review"] is True
    assert engine.review_packages[0]["depth"] == ReviewDepth.SELF_CHECK.value
    assert engine.review_packages[0]["required"] is True
    assert engine.review_packages[0]["reason"] == (
        "self-check because no non-owner peer reviewer is active"
    )
    assert [review.id for review in engine.review_packages_for_request("wp")] == [
        "RP-WP-001-codex-self-check"
    ]

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.state == WorkflowState.REVIEWING
    assert loaded.execution_results[0].files_changed == ["src/routes.py"]
    assert loaded.review_packages[0]["package_id"] == "WP-001"


def test_record_execution_results_plans_one_primary_non_owner_review(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["claude", "codex", "antigravity"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            requires_execution=True,
        )
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.begin_execution()

    engine.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="Implemented route bot.",
            )
        ]
    )

    assert [
        (review["package_id"], review["target_agent"], review["reviewer_agent"])
        for review in engine.review_packages
    ] == [
        ("WP-001", "codex", "antigravity"),
    ]
    assert all(review["self_review"] is False for review in engine.review_packages)
    assert all(
        review["depth"] == ReviewDepth.SINGLE_PEER.value
        for review in engine.review_packages
    )


def test_review_request_keeps_legacy_multi_review_pending(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["claude", "codex", "antigravity"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            requires_execution=True,
            status=WorkStatus.DONE,
        )
    ]
    engine.session.execution_results = [
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.DONE,
            summary="Implemented route bot.",
        )
    ]
    engine.session.review_packages = [
        ReviewPackage(
            package_id="WP-001",
            reviewer_agent="claude",
            target_agent="codex",
        ).to_dict(),
        ReviewPackage(
            package_id="WP-001",
            reviewer_agent="antigravity",
            target_agent="codex",
        ).to_dict(),
    ]
    planned = engine.review_packages_for_request("wp")

    engine.record_review_results(
        [
            ReviewResult(
                review_package_id=planned[0].id,
                package_id=planned[0].package_id,
                reviewer_agent=planned[0].reviewer_agent,
                target_agent=planned[0].target_agent,
                status=ReviewStatus.APPROVED,
                severity="low",
                summary="Looks good.",
            )
        ]
    )

    pending = engine.review_packages_for_request("wp")

    assert [(review.id, review.reviewer_agent) for review in pending] == [
        (planned[1].id, "antigravity")
    ]
    assert engine._review_flow()._latest_review_is_approved("WP-001") is False


def test_record_review_results_requests_repair_notes(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.DONE,
        )
    ]
    engine.set_state(WorkflowState.REVIEWING, reason="test review")

    engine.record_review_results(
        [
            ReviewResult(
                review_package_id="RP-WP-001-claude",
                package_id="WP-001",
                reviewer_agent="claude",
                target_agent="codex",
                status=ReviewStatus.CHANGES_REQUESTED,
                severity="high",
                summary="Needs test coverage.",
                required_changes=["Add retry regression test."],
            )
        ]
    )

    package = engine.session.work_packages[0]
    assert package.status == WorkStatus.NEEDS_REVIEW
    assert package.repair_notes == [
        "review RP-WP-001-claude: Add retry regression test."
    ]
    assert engine.state == WorkflowState.REVIEWING
    assert engine.review_results[0].status == ReviewStatus.CHANGES_REQUESTED


def test_prepare_review_repairs_queues_changed_package(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.NEEDS_REVIEW,
            last_executor="claude",
        )
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    result = ReviewResult(
        review_package_id="RP-WP-001-claude",
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Add retry regression test."],
    )

    selected = engine.prepare_review_repairs([result])

    assert selected == ("WP-001",)
    assert engine.session.work_packages[0].status == WorkStatus.PENDING
    assert engine.session.work_packages[0].repair_attempt_count == 1
    assert engine.session.work_packages[0].last_repair_review_id == "RP-WP-001-claude"
    assert engine.session.work_packages[0].last_repair_signature
    assert engine.pending_execution_package_ids() == ["WP-001"]
    assert engine.session.execution_run["retry_selector"] == "review-repair"
    assert engine.state == WorkflowState.BLUEPRINT_READY


def test_prepare_review_repairs_blocks_duplicate_required_changes(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.NEEDS_REVIEW,
            last_executor="claude",
        )
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    result = ReviewResult(
        review_package_id="RP-WP-001-claude",
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Add retry regression test."],
    )

    assert engine.prepare_review_repairs([result]) == ("WP-001",)
    package = engine.session.work_packages[0]
    package.status = WorkStatus.NEEDS_REVIEW
    duplicate = ReviewResult(
        review_package_id="RP-WP-001-codex",
        package_id="WP-001",
        reviewer_agent="codex",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["  Add   retry regression test.  "],
    )

    selected = engine.prepare_review_repairs([duplicate])

    assert selected == ()
    assert package.status == WorkStatus.BLOCKED
    assert package.repair_attempt_count == 1
    assert package.repair_blocked_reason == "duplicate_required_changes"
    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    assert engine.session.execution_run["state"] == "repair_blocked"
    assert engine.session.execution_run["repair_blocked_packages"] == ["WP-001"]
    assert engine.persistence.load_events()[-2]["event"] == "work_package_repair_blocked"


def test_prepare_review_repairs_batches_multiple_reviews_per_package(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude", "antigravity"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.NEEDS_REVIEW,
            last_executor="codex",
        )
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    first = ReviewResult(
        review_package_id="RP-WP-001-claude",
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Add retry regression test."],
    )
    duplicate = ReviewResult(
        review_package_id="RP-WP-001-antigravity",
        package_id="WP-001",
        reviewer_agent="antigravity",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["  Add   retry regression test.  "],
    )

    selected = engine.prepare_review_repairs([first, duplicate])

    package = engine.session.work_packages[0]
    repair_events = [
        event
        for event in engine.persistence.load_events()
        if event["event"] == "work_package_repair_requested"
    ]
    assert selected == ("WP-001",)
    assert package.status == WorkStatus.PENDING
    assert package.repair_attempt_count == 1
    assert package.repair_blocked_reason == ""
    assert len(repair_events) == 1
    assert repair_events[0]["data"]["required_changes"] == [
        "Add retry regression test."
    ]
    assert repair_events[0]["data"]["review_package_ids"] == [
        "RP-WP-001-claude",
        "RP-WP-001-antigravity",
    ]


def test_prepare_review_repairs_batches_distinct_changes_into_one_signature(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude", "antigravity"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.NEEDS_REVIEW,
            last_executor="codex",
        )
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    first = ReviewResult(
        review_package_id="RP-WP-001-claude",
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Add retry regression test."],
    )
    second = ReviewResult(
        review_package_id="RP-WP-001-antigravity",
        package_id="WP-001",
        reviewer_agent="antigravity",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Document retry behavior."],
    )

    assert engine.prepare_review_repairs([first, second]) == ("WP-001",)
    package = engine.session.work_packages[0]
    first_signature = package.last_repair_signature
    package.status = WorkStatus.NEEDS_REVIEW

    selected = engine.prepare_review_repairs([second, first])

    assert selected == ()
    assert package.status == WorkStatus.BLOCKED
    assert package.repair_attempt_count == 1
    assert package.last_repair_signature == first_signature
    assert package.repair_blocked_reason == "duplicate_required_changes"


def test_prepare_review_repairs_honors_max_attempts(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.NEEDS_REVIEW,
            repair_attempt_count=2,
        )
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    result = ReviewResult(
        review_package_id="RP-WP-001-claude",
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Add a different regression test."],
    )

    selected = engine.prepare_review_repairs([result], max_attempts=2)

    package = engine.session.work_packages[0]
    assert selected == ()
    assert package.status == WorkStatus.BLOCKED
    assert package.repair_attempt_count == 2
    assert package.repair_blocked_reason == "max_attempts_exceeded"
    assert engine.state == WorkflowState.NEEDS_USER_DECISION


def test_prepare_review_repairs_records_mixed_selected_and_blocked_packages(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="retryable package",
            owner_agent="codex",
            objective="Repair this package.",
            status=WorkStatus.NEEDS_REVIEW,
            last_executor="codex",
        ),
        WorkPackage(
            id="WP-002",
            title="blocked package",
            owner_agent="claude",
            objective="Already retried.",
            status=WorkStatus.NEEDS_REVIEW,
            repair_attempt_count=3,
            last_executor="claude",
        ),
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    retryable = ReviewResult(
        review_package_id="RP-WP-001-claude",
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Add retry regression test."],
    )
    blocked = ReviewResult(
        review_package_id="RP-WP-002-codex",
        package_id="WP-002",
        reviewer_agent="codex",
        target_agent="claude",
        status=ReviewStatus.CHANGES_REQUESTED,
        required_changes=["Document retry behavior."],
    )

    selected = engine.prepare_review_repairs([retryable, blocked], max_attempts=3)

    assert selected == ("WP-001",)
    assert engine.session.work_packages[0].status == WorkStatus.PENDING
    assert engine.session.work_packages[1].status == WorkStatus.BLOCKED
    assert engine.session.work_packages[1].repair_blocked_reason == "max_attempts_exceeded"
    assert engine.session.execution_run["state"] == "retry_requested"
    assert engine.session.execution_run["retry_packages"] == ["WP-001"]
    assert engine.session.execution_run["repair_blocked_packages"] == ["WP-002"]
    assert engine.state == WorkflowState.BLUEPRINT_READY


def test_work_package_repair_metadata_round_trips():
    package = WorkPackage(
        id="WP-001",
        title="codex package",
        owner_agent="codex",
        objective="Implement route bot.",
        repair_attempt_count=2,
        last_repair_signature="sig-1",
        last_repair_review_id="RP-WP-001-claude",
        repair_blocked_reason="duplicate_required_changes",
        repair_blocked_at=123.5,
    )

    loaded = WorkPackage.from_dict(package.to_dict())

    assert loaded.repair_attempt_count == 2
    assert loaded.last_repair_signature == "sig-1"
    assert loaded.last_repair_review_id == "RP-WP-001-claude"
    assert loaded.repair_blocked_reason == "duplicate_required_changes"
    assert loaded.repair_blocked_at == 123.5


def test_reconcile_review_repair_metadata_blocks_legacy_loop(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.RUNNING,
            current_executor="codex",
        )
    ]
    engine.session.review_results = [
        ReviewResult(
            review_package_id="RP-WP-001-claude",
            package_id="WP-001",
            reviewer_agent="claude",
            target_agent="codex",
            status=ReviewStatus.CHANGES_REQUESTED,
            required_changes=["Add retry regression test."],
        ).to_dict()
    ]
    engine.session.execution_run = {"state": "running", "run_id": "exec-run-test"}
    engine.set_state(WorkflowState.EXECUTING, reason="simulate legacy execution")
    for index in range(3):
        engine.persistence.append_event(
            {
                "timestamp": 1000 + index,
                "workflow_id": engine.session.id,
                "event": "work_package_repair_requested",
                "state": "blueprint_ready",
                "data": {
                    "package_id": "WP-001",
                    "previous_status": "needs_review",
                },
            }
        )

    loaded = WorkflowEngine(tmp_path / ".trinity")
    blocked = loaded.reconcile_review_repair_metadata(max_attempts=3)

    package = loaded.session.work_packages[0]
    assert blocked == ("WP-001",)
    assert package.status == WorkStatus.BLOCKED
    assert package.current_executor == ""
    assert package.repair_attempt_count == 3
    assert package.last_repair_signature
    assert package.repair_blocked_reason == "legacy_repair_loop_detected"
    assert loaded.state == WorkflowState.NEEDS_USER_DECISION
    assert loaded.session.execution_run["state"] == "repair_blocked"
    assert loaded.session.execution_run["repair_blocked_packages"] == ["WP-001"]


def test_reconcile_review_repair_metadata_restores_event_signature(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.NEEDS_REVIEW,
        )
    ]
    engine.save()
    engine.persistence.append_event(
        {
            "timestamp": 1000,
            "workflow_id": engine.session.id,
            "event": "work_package_repair_requested",
            "state": "blueprint_ready",
            "data": {
                "package_id": "WP-001",
                "previous_status": "needs_review",
                "review_package_id": "RP-WP-001-claude",
                "review_package_ids": [
                    "RP-WP-001-claude",
                    "RP-WP-001-antigravity",
                ],
                "required_changes": [
                    "Add retry regression test.",
                    "Document retry behavior.",
                ],
                "repair_signature": "batch-signature",
            },
        }
    )

    loaded = WorkflowEngine(tmp_path / ".trinity")
    blocked = loaded.reconcile_review_repair_metadata(max_attempts=3)

    package = loaded.session.work_packages[0]
    assert blocked == ()
    assert package.status == WorkStatus.NEEDS_REVIEW
    assert package.repair_attempt_count == 1
    assert package.last_repair_signature == "batch-signature"
    assert package.last_repair_review_id == "RP-WP-001-claude"


def test_reconcile_review_repair_metadata_uses_event_attempt_count(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.RUNNING,
            current_executor="codex",
        )
    ]
    engine.save()
    engine.persistence.append_event(
        {
            "timestamp": 1000,
            "workflow_id": engine.session.id,
            "event": "work_package_repair_requested",
            "state": "blueprint_ready",
            "data": {
                "package_id": "WP-001",
                "previous_status": "needs_review",
                "review_package_ids": [
                    "RP-WP-001-claude",
                    "RP-WP-001-antigravity",
                ],
                "repair_attempt_count": 3,
                "repair_signature": "batch-signature-3",
            },
        }
    )

    loaded = WorkflowEngine(tmp_path / ".trinity")
    blocked = loaded.reconcile_review_repair_metadata(max_attempts=3)

    package = loaded.session.work_packages[0]
    assert blocked == ("WP-001",)
    assert package.status == WorkStatus.BLOCKED
    assert package.repair_attempt_count == 3
    assert package.last_repair_signature == "batch-signature-3"
    assert package.last_repair_review_id == "RP-WP-001-antigravity"
    assert package.repair_blocked_reason == "legacy_repair_loop_detected"


def test_accept_review_repair_blocks_marks_packages_done(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.BLOCKED,
            repair_attempt_count=3,
            repair_blocked_reason="duplicate_required_changes",
        )
    ]
    engine.set_state(WorkflowState.NEEDS_USER_DECISION, reason="test repair blocked")

    accepted = engine.accept_review_repair_blocks()

    package = engine.session.work_packages[0]
    assert accepted == ("WP-001",)
    assert package.status == WorkStatus.DONE
    assert package.repair_blocked_reason == ""
    assert package.repair_notes == [
        "user accepted blocked repair: duplicate_required_changes"
    ]
    assert engine.state == WorkflowState.REVIEWING
    assert engine.session.execution_run["state"] == "repair_accepted"


def test_stop_review_repair_blocks_marks_workflow_failed(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            status=WorkStatus.BLOCKED,
            repair_attempt_count=3,
            repair_blocked_reason="duplicate_required_changes",
        )
    ]
    engine.set_state(WorkflowState.NEEDS_USER_DECISION, reason="test repair blocked")

    stopped = engine.stop_review_repair_blocks()

    assert stopped == ("WP-001",)
    assert engine.session.work_packages[0].status == WorkStatus.BLOCKED
    assert engine.state == WorkflowState.FAILED
    assert engine.session.execution_run["state"] == "repair_stopped"
    assert engine.persistence.load_events()[-2]["event"] == "work_package_repair_stopped"


def test_record_final_review_approved_moves_to_post_review_ready(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.set_state(WorkflowState.REVIEWING, reason="test final review")

    engine.record_review_results(
        [
            ReviewResult(
                review_package_id="RP-FINAL-codex",
                package_id="FINAL",
                reviewer_agent="codex",
                target_agent="project",
                status=ReviewStatus.APPROVED,
                severity="low",
                scope="final",
                summary="Project is coherent.",
            )
        ]
    )

    assert engine.state == WorkflowState.POST_REVIEW_READY
    assert engine.post_review_items == []

    action = engine.handle_post_review_input("/improve done", ["codex", "claude"])

    assert action.should_deliberate is False
    assert engine.state == WorkflowState.DONE


def test_final_review_changes_auto_queue_supplemental_wp_without_clearing_evidence(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="client",
            owner_agent="codex",
            objective="Build client.",
            status=WorkStatus.DONE,
            last_executor="codex",
        )
    ]
    engine.session.execution_results = [
        ExecutionResult(
            package_id="WP-001",
            agent_name="codex",
            status=WorkStatus.DONE,
            summary="Implemented client.",
        )
    ]
    engine.set_state(WorkflowState.REVIEWING, reason="test final review")
    engine.record_review_results(
        [
            ReviewResult(
                review_package_id="RP-FINAL-codex",
                package_id="FINAL",
                reviewer_agent="codex",
                target_agent="project",
                status=ReviewStatus.CHANGES_REQUESTED,
                severity="high",
                scope="final",
                summary="Needs regression coverage.",
                required_changes=["Add execution retry regression tests."],
            )
        ]
    )

    assert engine.state == WorkflowState.BLUEPRINT_READY
    assert [item.id for item in engine.post_review_items] == ["AI-001"]
    assert engine.post_review_items[0].status.value == "queued"
    assert [package.id for package in engine.session.work_packages] == ["WP-001", "WP-S001"]
    supplemental = engine.session.work_packages[-1]
    assert supplemental.origin == "post_review_followup"
    assert supplemental.origin_action_item_ids == ["AI-001"]
    assert supplemental.status == WorkStatus.PENDING
    assert supplemental.objective.startswith(
        "Post-review action item AI-001: Add execution retry regression tests."
    )
    assert engine.session.execution_run["state"] == "supplemental_queued"
    assert engine.session.execution_run["source"] == "final_review_auto_replan"
    assert engine.session.execution_run["auto_replanned_from_review"] == "RP-FINAL-codex"
    assert engine.session.execution_run["auto_replanned_action_item_ids"] == ["AI-001"]
    assert engine.execution_results[0].summary == "Implemented client."
    assert engine.review_results[0].summary == "Needs regression coverage."
    events = engine.persistence.load_events()
    assert events[-1]["event"] == "post_review_auto_replan_queued"


def test_final_review_changes_without_target_workspace_waits_for_user(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.set_state(WorkflowState.REVIEWING, reason="test final review")

    engine.record_review_results(
        [
            ReviewResult(
                review_package_id="RP-FINAL-codex",
                package_id="FINAL",
                reviewer_agent="codex",
                target_agent="project",
                status=ReviewStatus.CHANGES_REQUESTED,
                severity="high",
                scope="final",
                summary="Needs regression coverage.",
                required_changes=["Add execution retry regression tests."],
            )
        ]
    )

    assert engine.state == WorkflowState.POST_REVIEW_READY
    assert [item.id for item in engine.post_review_items] == ["AI-001"]
    assert engine.post_review_items[0].status.value == "proposed"
    assert [package.id for package in engine.session.work_packages] == []
    events = engine.persistence.load_events()
    assert any(
        event["event"] == "post_review_auto_replan_skipped"
        and event["data"]["reason"] == "target_workspace_missing"
        for event in events
    )


def test_record_work_package_started_persists_running_status(tmp_path):
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
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.begin_execution()

    engine.record_work_package_started("WP-001", "codex", occurred_at=1234.5)

    assert engine.session.work_packages[0].status == WorkStatus.RUNNING
    events = engine.persistence.load_events()
    assert events[-1]["event"] == "work_package_started"
    assert events[-1]["timestamp"] == 1234.5
    assert events[-1]["data"]["package_id"] == "WP-001"

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.session.work_packages[0].status == WorkStatus.RUNNING
    assert loaded.session.work_packages[0].current_executor == "codex"
    assert loaded.session.execution_run["state"] == "running"


def test_detect_interrupted_execution_when_running_without_worker(tmp_path):
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
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.begin_execution()
    engine.record_work_package_started("WP-001", "codex", occurred_at=1234.5)

    loaded = WorkflowEngine(tmp_path / ".trinity")
    recovery = loaded.detect_interrupted_execution(worker_running=False)

    assert recovery is not None
    assert recovery["state"] == "interrupted"
    assert recovery["running_packages"] == ["WP-001"]
    assert recovery["retry_candidates"] == ["WP-001"]
    assert loaded.session.execution_run["state"] == "interrupted"
    events = loaded.persistence.load_events()
    assert events[-1]["event"] == "execution_interrupted_detected"


def test_retry_interrupted_packages_excludes_done_packages(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="done package",
            owner_agent="codex",
            objective="Done.",
            status=WorkStatus.DONE,
        ),
        WorkPackage(
            id="WP-002",
            title="running package",
            owner_agent="claude",
            objective="Running.",
            status=WorkStatus.RUNNING,
            current_executor="claude",
        ),
        WorkPackage(
            id="WP-003",
            title="blocked package",
            owner_agent="codex",
            objective="Blocked.",
            status=WorkStatus.BLOCKED,
        ),
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.set_state(WorkflowState.EXECUTING, reason="simulate stale execution")
    engine.session.execution_run = {
        "run_id": "exec-run-test",
        "state": "running",
        "target_workspace": str(tmp_path / "route-bot"),
    }
    engine.save()

    recovery = engine.retry_interrupted_execution()

    assert recovery is not None
    assert set(recovery["retry_candidates"]) == {"WP-002", "WP-003"}
    assert [package.status for package in engine.session.work_packages] == [
        WorkStatus.DONE,
        WorkStatus.PENDING,
        WorkStatus.PENDING,
    ]
    assert engine.session.work_packages[0].status == WorkStatus.DONE
    events = engine.persistence.load_events()
    retry_events = [event for event in events if event["event"] == "work_package_retry_requested"]
    assert [event["data"]["package_id"] for event in retry_events] == [
        "WP-002",
        "WP-003",
    ]


def test_build_execution_retry_plan_selects_failed_blocked_and_interrupted(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="done package",
            owner_agent="codex",
            objective="Done.",
            status=WorkStatus.DONE,
        ),
        WorkPackage(
            id="WP-002",
            title="running package",
            owner_agent="claude",
            objective="Running.",
            status=WorkStatus.RUNNING,
            current_executor="claude",
        ),
        WorkPackage(
            id="WP-003",
            title="blocked package",
            owner_agent="codex",
            objective="Blocked.",
            status=WorkStatus.BLOCKED,
        ),
        WorkPackage(
            id="WP-004",
            title="failed package",
            owner_agent="codex",
            objective="Failed.",
            status=WorkStatus.FAILED,
        ),
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.set_state(WorkflowState.EXECUTING, reason="simulate stale execution")
    engine.session.execution_run = {
        "run_id": "exec-run-test",
        "state": "running",
        "target_workspace": str(tmp_path / "route-bot"),
    }
    engine.save()

    plan = engine.build_execution_retry_plan("all")

    assert plan.selector == "all"
    assert plan.selected == ("WP-002", "WP-003", "WP-004")
    assert plan.target_workspace == (tmp_path / "route-bot").resolve()
    assert engine.session.execution_run["state"] == "running"
    assert not [
        event
        for event in engine.persistence.load_events()
        if event["event"] == "execution_interrupted_detected"
    ]


def test_prepare_execution_retry_detects_stale_running_before_retry(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="running package",
            owner_agent="claude",
            objective="Running.",
            status=WorkStatus.RUNNING,
            current_executor="claude",
        ),
        WorkPackage(
            id="WP-002",
            title="failed package",
            owner_agent="codex",
            objective="Failed.",
            status=WorkStatus.FAILED,
        ),
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.set_state(WorkflowState.EXECUTING, reason="simulate stale execution")
    engine.session.execution_run = {
        "run_id": "exec-run-test",
        "state": "running",
        "target_workspace": str(tmp_path / "route-bot"),
    }
    engine.save()

    plan = engine.prepare_execution_retry("all")

    assert plan.selected == ("WP-001", "WP-002")
    assert engine.session.execution_run["state"] == "retry_requested"
    assert engine.session.execution_run["retry_packages"] == ["WP-001", "WP-002"]
    assert [
        event
        for event in engine.persistence.load_events()
        if event["event"] == "execution_interrupted_detected"
    ]


def test_prepare_execution_retry_keeps_unselected_failed_packages_out_of_dispatch(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="first failed",
            owner_agent="codex",
            objective="Failed.",
            status=WorkStatus.FAILED,
        ),
        WorkPackage(
            id="WP-002",
            title="second failed",
            owner_agent="claude",
            objective="Failed.",
            status=WorkStatus.FAILED,
        ),
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.set_state(WorkflowState.FAILED, reason="simulate failed execution")

    plan = engine.prepare_execution_retry("custom", ["WP-002"])

    assert plan.selected == ("WP-002",)
    assert engine.pending_execution_package_ids() == ["WP-002"]
    assert [package.status for package in engine.session.work_packages] == [
        WorkStatus.FAILED,
        WorkStatus.PENDING,
    ]


def test_prepare_execution_retry_clears_selected_repair_block_marker(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex", "claude"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="repair blocked package",
            owner_agent="codex",
            objective="Repair.",
            status=WorkStatus.BLOCKED,
            repair_attempt_count=3,
            last_repair_signature="sig-1",
            repair_blocked_reason="duplicate_required_changes",
            repair_blocked_at=123.5,
        )
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.set_state(WorkflowState.NEEDS_USER_DECISION, reason="repair blocked")
    engine.session.execution_run = {
        "run_id": "exec-run-test",
        "state": "repair_blocked",
        "repair_blocked_packages": ["WP-001"],
    }

    plan = engine.prepare_execution_retry("custom", ["WP-001"])

    package = engine.session.work_packages[0]
    assert plan.selected == ("WP-001",)
    assert package.status == WorkStatus.PENDING
    assert package.current_executor == ""
    assert package.repair_blocked_reason == ""
    assert package.repair_blocked_at == 0.0
    assert package.repair_attempt_count == 3
    assert package.last_repair_signature == "sig-1"
    assert engine.pending_execution_package_ids() == ["WP-001"]


def test_record_work_package_completed_persists_finished_event(tmp_path):
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
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.begin_execution()

    engine.record_work_package_completed(
        "WP-001",
        "codex",
        "done",
        "Implemented route bot.",
        occurred_at=1300.25,
    )

    assert engine.session.work_packages[0].status == WorkStatus.DONE
    events = engine.persistence.load_events()
    assert events[-1]["event"] == "work_package_completed"
    assert events[-1]["timestamp"] == 1300.25
    assert events[-1]["data"] == {
        "package_id": "WP-001",
        "agent": "codex",
        "status": "done",
        "summary": "Implemented route bot.",
    }

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.session.work_packages[0].status == WorkStatus.DONE


def test_record_execution_results_can_persist_progress_without_finalizing(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement route bot", ["codex"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="codex package",
            owner_agent="codex",
            objective="Implement route bot.",
            requires_execution=True,
        ),
        WorkPackage(
            id="WP-002",
            title="review package",
            owner_agent="codex",
            objective="Review route bot.",
            requires_execution=True,
        ),
    ]
    engine.set_target_workspace(tmp_path / "route-bot")
    engine.begin_execution()

    engine.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.DONE,
                summary="Implemented route bot.",
                files_changed=["src/routes.py"],
            )
        ],
        finalize=False,
    )

    assert engine.state == WorkflowState.EXECUTING
    assert engine.session.work_packages[0].status == WorkStatus.DONE
    assert engine.session.work_packages[1].status == WorkStatus.PENDING
    assert engine.execution_results[0].summary == "Implemented route bot."
    events = engine.persistence.load_events()
    assert events[-1]["event"] == "execution_result_recorded"

    loaded = WorkflowEngine(tmp_path / ".trinity")
    assert loaded.state == WorkflowState.EXECUTING
    assert loaded.session.work_packages[0].status == WorkStatus.DONE
    assert loaded.execution_results[0].files_changed == ["src/routes.py"]


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

    engine.record_execution_results(
        [
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
        ]
    )

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

    engine.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.FAILED,
                summary="Provider failed.",
            )
        ]
    )

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

    engine.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="codex",
                status=WorkStatus.BLOCKED,
                summary="Missing credential.",
                blockers=["Missing credential."],
            )
        ]
    )

    assert engine.state == WorkflowState.NEEDS_USER_DECISION
    assert engine.session.work_packages[0].status == WorkStatus.BLOCKED


def test_plan_parallel_groups_respects_dependencies_and_file_ownership(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement", ["claude", "codex", "antigravity"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="config",
            owner_agent="codex",
            objective="Config.",
            expected_files=["src/trinity/config.py"],
            estimated_weight=2,
        ),
        WorkPackage(
            id="WP-002",
            title="config tests",
            owner_agent="claude",
            objective="Tests.",
            expected_files=["src/trinity/config.py"],
            estimated_weight=1,
        ),
        WorkPackage(
            id="WP-003",
            title="docs",
            owner_agent="antigravity",
            objective="Docs.",
            expected_files=["docs/"],
            dependencies=["WP-001"],
        ),
    ]

    groups = engine.plan_parallel_groups()

    assert [[package.id for package in group] for group in groups] == [
        ["WP-001"],
        ["WP-002", "WP-003"],
    ]


def test_plan_parallel_groups_serializes_high_risk_work(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement", ["claude", "codex"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="risky config",
            owner_agent="claude",
            objective="Risky change.",
            expected_files=["src/risky.py"],
            risk="high",
        ),
        WorkPackage(
            id="WP-002",
            title="independent tests",
            owner_agent="codex",
            objective="Independent change.",
            expected_files=["tests/test_risky.py"],
        ),
    ]

    groups = engine.plan_parallel_groups()

    assert [[package.id for package in group] for group in groups] == [
        ["WP-001"],
        ["WP-002"],
    ]


def test_plan_parallel_groups_respects_path_prefix_collisions(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement", ["claude", "codex"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="module",
            owner_agent="claude",
            objective="Change module.",
            expected_files=["src/trinity/"],
        ),
        WorkPackage(
            id="WP-002",
            title="module file",
            owner_agent="codex",
            objective="Change module file.",
            expected_files=["src/trinity/config.py"],
        ),
    ]

    groups = engine.plan_parallel_groups()

    assert [[package.id for package in group] for group in groups] == [
        ["WP-001"],
        ["WP-002"],
    ]


def test_plan_parallel_groups_prefers_central_parallel_group_order(tmp_path):
    engine = WorkflowEngine(tmp_path / ".trinity")
    engine.start("Implement", ["claude", "codex", "antigravity"])
    engine.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="later",
            owner_agent="claude",
            objective="Later group.",
            expected_files=["src/later.py"],
            parallel_group=2,
        ),
        WorkPackage(
            id="WP-002",
            title="first",
            owner_agent="codex",
            objective="First group.",
            expected_files=["src/first.py"],
            parallel_group=1,
        ),
        WorkPackage(
            id="WP-003",
            title="first tests",
            owner_agent="antigravity",
            objective="First group tests.",
            expected_files=["tests/first.py"],
            parallel_group=1,
        ),
    ]

    groups = engine.plan_parallel_groups()

    assert [[package.id for package in group] for group in groups] == [
        ["WP-002", "WP-003"],
        ["WP-001"],
    ]


def test_blueprint_followup_classifier_uses_execute_only_for_clear_intent():
    assert classify_execution_intent("개발해라") is True
    assert classify_execution_intent("개발하고 싶다. 설계해라") is False
    assert classify_execution_intent("만들고 싶다. 구조를 잡아라") is False
    assert classify_execution_intent("구현하지 말고 설계만 해라") is False
    assert classify_execution_intent("이 설계대로 구현해라") is True
    assert classify_blueprint_followup_action("이대로 만들어라") == "execute"
    assert classify_blueprint_followup_action("개발하고 싶다. 설계해라") == "continue"
    assert classify_blueprint_followup_action("설계를 더 다듬어라") == "continue"
    assert classify_blueprint_followup_action("새 요청으로 시작") == "new"
    assert classify_blueprint_followup_action("취소") == "cancel"
    assert classify_blueprint_followup_action("텔레그램 알림은?") is None


def test_requires_execution_for_deliberation_uses_task_marker():
    result = DeliberationResult(
        user_prompt="설계해라",
        rounds_completed=1,
        consensus=None,
        tasks=[
            TaskAssignment(
                agent_name="codex",
                task_description="Implement change",
                requires_execution=True,
            )
        ],
    )

    assert requires_execution_for_deliberation("설계만 해라", result) is True


def test_requires_execution_for_deliberation_uses_combined_text():
    result = DeliberationResult(
        user_prompt="이 설계대로 구현해라",
        rounds_completed=1,
        consensus=ConsensusResult(
            reached=True,
            agreement_count=1,
            total_agents=1,
            opinions={"codex": "yes"},
            summary="Build the implementation.",
        ),
    )

    assert requires_execution_for_deliberation("Route bot", result) is True


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
