from __future__ import annotations

import asyncio
import time

from trinity.config import TrinityConfig
from trinity.models import ConsensusResult, DeliberationResult
from trinity.textual_app.workflow_controller import TextualWorkflowController
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import WorkflowEngine, WorkflowState
from trinity.workflow.models import (
    Blueprint,
    OpenQuestion,
    WorkPackage,
    WorkflowSession,
    WorkStatus,
)


class FakeOrchestrator:
    def __init__(self, *args, **kwargs) -> None:
        self.bus = None

    def set_event_bus(self, bus) -> None:
        self.bus = bus

    async def ask(self, prompt: str) -> DeliberationResult:
        assert self.bus is not None
        self.bus.emit(
            TUIEvent(
                type=TUIEventType.ROUND_START,
                data={"round_num": 1},
            )
        )
        self.bus.emit(
            TUIEvent(
                type=TUIEventType.AGENT_THINKING,
                data={"agent": "claude", "round_num": 1},
            )
        )
        self.bus.emit(
            TUIEvent(
                type=TUIEventType.AGENT_RESPONDED,
                data={
                    "agent": "claude",
                    "content": "claude plan",
                    "round_num": 1,
                    "response_status": "ok",
                },
            )
        )
        self.bus.emit(
            TUIEvent(
                type=TUIEventType.CONSENSUS_CHECKING,
                data={"round_num": 1},
            )
        )
        await asyncio.sleep(0.05)
        self.bus.emit(
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={
                    "round_num": 1,
                    "reached": True,
                    "agreement_count": 1,
                    "total_agents": 1,
                    "summary": "Build the requested app.",
                },
            )
        )
        return DeliberationResult(
            user_prompt=prompt,
            rounds_completed=1,
            consensus=ConsensusResult(
                reached=True,
                agreement_count=1,
                total_agents=1,
                opinions={"claude": "agree"},
                summary="Build the requested app.",
            ),
        )


def test_textual_workflow_controller_starts_real_workflow_session(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    controller = TextualWorkflowController(
        config,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.start_prompt("모바일 퍼즐 게임 설계")

    assert outcome.running is True
    assert outcome.snapshot.goal == "모바일 퍼즐 게임 설계"
    assert outcome.snapshot.state == "deliberating"
    assert controller.wait_until_idle(timeout=2.0)

    final = controller.drain_updates()

    assert final is not None
    assert final.snapshot.goal == "모바일 퍼즐 게임 설계"
    assert final.snapshot.state == "blueprint_ready"
    assert final.snapshot.round_num == 1
    assert final.snapshot.synthesis.summary == "Build the requested app."
    provider = next(item for item in final.snapshot.providers if item.name == "claude")
    assert provider.status == "Ready"
    assert provider.raw_output == "claude plan"


def test_textual_workflow_controller_reports_active_synthesis(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    controller = TextualWorkflowController(
        config,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    controller.start_prompt("모바일 퍼즐 게임 설계")
    mid = None
    for _ in range(20):
        mid = controller.drain_updates()
        if mid and mid.snapshot.synthesis.status == "running":
            break
        time.sleep(0.01)

    assert mid is not None
    assert mid.snapshot.round_num == 1
    assert mid.snapshot.synthesis.status == "running"
    assert mid.snapshot.synthesis.consensus_progress == "round 1 synthesizing"
    assert "Central agent is synthesizing round 1" in mid.snapshot.synthesis.summary
    assert controller.wait_until_idle(timeout=2.0)


def test_textual_workflow_controller_routes_question_answers(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 설계", ["claude"])
    workflow.add_open_question(
        OpenQuestion(
            id="q-1",
            question="Which theme?",
            options=["dark", "light"],
        )
    )
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.answer_question("q-1", "dark")

    assert outcome.running is True
    assert controller.wait_until_idle(timeout=2.0)
    final = controller.drain_updates()
    assert final is not None
    assert final.snapshot.state == "blueprint_ready"
    assert final.snapshot.decisions == ["dark"]


def test_textual_workflow_controller_answers_question_options(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 설계", ["claude"])
    workflow.add_open_question(
        OpenQuestion(
            id="q-1",
            question="Which theme?",
            options=["dark", "light"],
        )
    )
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.answer_question_option("2")

    assert outcome.running is True
    assert controller.wait_until_idle(timeout=2.0)
    final = controller.drain_updates()
    assert final is not None
    assert final.snapshot.state == "blueprint_ready"
    assert final.snapshot.decisions == ["light"]


def test_textual_workflow_controller_replaces_question_answer(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 설계", ["claude"])
    workflow.add_open_question(
        OpenQuestion(
            id="q-1",
            question="Which theme?",
            options=["dark", "light"],
        )
    )
    workflow.answer_question("q-1", "dark")
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.answer_question("q-1", "light", replace=True)

    assert outcome.running is True
    assert len(controller.workflow.session.decisions) == 1
    assert controller.workflow.session.decisions[0].decision == "light"
    assert controller.wait_until_idle(timeout=2.0)
    controller.drain_updates()


def test_textual_workflow_controller_resumes_latest_workflow(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    controller = TextualWorkflowController(
        config,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )
    controller.persistence.save(
        WorkflowSession(
            id="wf-archived",
            goal="archived goal",
            state=WorkflowState.BLUEPRINT_READY,
        )
    )
    controller.persistence.archive_active_session(force=True)

    outcome = controller.resume_workflow("latest")

    assert outcome.snapshot.session_id == "wf-archived"
    assert outcome.snapshot.goal == "archived goal"
    assert outcome.snapshot.state == "blueprint_ready"
    assert outcome.message == "Resumed workflow wf-archived."


def test_textual_workflow_controller_lists_resume_options(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    controller = TextualWorkflowController(
        config,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )
    controller.persistence.save(
        WorkflowSession(
            id="wf-archived",
            goal="archived goal",
            state=WorkflowState.BLUEPRINT_READY,
            updated_at=1234.0,
        )
    )
    controller.persistence.archive_active_session(force=True)

    options = controller.list_resume_options()

    assert len(options) == 1
    assert options[0].selector == "1"
    assert options[0].session_id == "wf-archived"
    assert options[0].goal == "archived goal"
    assert options[0].state == "blueprint_ready"
    assert options[0].updated_at == 1234.0


def test_textual_workflow_controller_clears_target_workspace(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.set_target_workspace(tmp_path / "game")
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    controller.clear_target_workspace()

    assert controller.workflow.session.target_workspace is None


def test_textual_workflow_controller_requests_workspace_before_execution(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    controller = TextualWorkflowController(
        config,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )
    controller.start_prompt("설계")
    assert controller.wait_until_idle(timeout=2.0)
    controller.drain_updates()

    outcome = controller.request_execution()

    assert outcome.target_workspace_required is True
    assert controller.workflow.state == WorkflowState.BLUEPRINT_READY


def test_resume_surfaces_execution_recovery(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    controller = TextualWorkflowController(
        config,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )
    target = tmp_path / "game"
    controller.persistence.save(
        WorkflowSession(
            id="wf-interrupted",
            goal="게임 구현",
            state=WorkflowState.EXECUTING,
            active_agents=["claude"],
            target_workspace=target,
            work_packages=[
                WorkPackage(
                    id="WP-001",
                    title="client",
                    owner_agent="claude",
                    objective="Build client.",
                    status=WorkStatus.RUNNING,
                    current_executor="claude",
                )
            ],
            execution_run={
                "run_id": "exec-run-test",
                "state": "running",
                "target_workspace": str(target),
            },
        )
    )
    controller.persistence.archive_active_session(force=True)

    outcome = controller.resume_workflow("latest")

    assert outcome.execution_recovery_required is True
    assert outcome.snapshot.session_id == "wf-interrupted"
    assert outcome.snapshot.execution_recovery is not None
    assert outcome.snapshot.execution_recovery.state == "interrupted"
    assert outcome.snapshot.execution_recovery.retry_candidates == ("WP-001",)


def test_execute_requires_recovery_choice_for_stale_execution(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 구현", ["claude"])
    workflow.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="client",
            owner_agent="claude",
            objective="Build client.",
            status=WorkStatus.RUNNING,
            current_executor="claude",
        )
    ]
    workflow.set_target_workspace(tmp_path / "game")
    workflow.set_state(WorkflowState.EXECUTING, reason="simulate stale execution")
    workflow.session.execution_run = {
        "run_id": "exec-run-test",
        "state": "running",
        "target_workspace": str(tmp_path / "game"),
    }
    workflow.save()
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.request_execution()

    assert outcome.execution_recovery_required is True
    assert outcome.execution_requested is False
    assert outcome.target_workspace_required is False
    assert "Previous execution was interrupted" in outcome.message
    assert controller.is_running is False


def test_textual_workflow_controller_reuses_target_for_review_followup(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 만들기", ["claude"])
    target = tmp_path / "testfolder"
    workflow.session.blueprint = Blueprint(
        title="Game",
        summary="Build the game project.",
        acceptance_criteria=["runs"],
    )
    workflow.set_target_workspace(target)
    workflow.set_state(WorkflowState.REVIEWING, reason="implementation completed")
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.submit_follow_up("테스트를 해라")

    assert outcome.running is True
    assert controller.workflow.session.target_workspace == target.resolve()
    assert controller.wait_until_idle(timeout=2.0)
    final = controller.drain_updates()
    assert final is not None
    assert final.snapshot.state == "blueprint_ready"
    execute = controller.request_execution("테스트 실행")
    assert execute.execution_requested is True
    assert execute.target_workspace_required is False


def test_textual_workflow_controller_persists_work_package_runtime_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 구현", ["claude"])
    workflow.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="client",
            owner_agent="claude",
            objective="Build client.",
        )
    ]
    workflow.set_target_workspace(tmp_path / "game")
    workflow.begin_execution()
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeOrchestrator,
        archive_active_session=False,
    )

    controller._consume_runtime_event(
        TUIEvent(
            type=TUIEventType.EXECUTION_BATCH_PLANNED,
            data={
                "batches": [["WP-001"]],
                "notices": [
                    {
                        "reason": "non-parallelizable package serialized",
                        "serialized_agents": ["claude"],
                    }
                ],
                "occurred_at": 1200.0,
            },
        )
    )
    controller._consume_runtime_event(
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
    controller._consume_runtime_event(
        TUIEvent(
            type=TUIEventType.WORK_PACKAGE_COMPLETED,
            data={
                "package_id": "WP-001",
                "agent": "claude",
                "status": WorkStatus.DONE.value,
                "summary": "Built client.",
                "occurred_at": 1300.25,
            },
        )
    )

    events = controller.workflow.persistence.load_events()
    assert events[-3]["event"] == "execution_batch_planned"
    assert events[-3]["timestamp"] == 1200.0
    assert events[-3]["data"]["batches"] == [["WP-001"]]
    assert events[-3]["data"]["notices"][0]["reason"] == ("non-parallelizable package serialized")
    assert events[-2]["event"] == "work_package_started"
    assert events[-2]["timestamp"] == 1234.5
    assert events[-1]["event"] == "work_package_completed"
    assert events[-1]["timestamp"] == 1300.25
    assert events[-1]["data"]["summary"] == "Built client."
    assert controller.workflow.session.work_packages[0].status == WorkStatus.DONE
