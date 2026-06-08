from __future__ import annotations

import asyncio
import time

from trinity.config import TrinityConfig
from trinity.models import ConsensusResult, DeliberationResult
from trinity.textual_app.workflow_controller import TextualWorkflowController
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import ReviewResult, ReviewStatus, WorkflowEngine, WorkflowState
from trinity.workflow.models import (
    Blueprint,
    ExecutionResult,
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


class FakeReviewOrchestrator(FakeOrchestrator):
    async def review_work_packages(
        self,
        review_packages,
        work_packages,
        execution_results,
    ) -> list[ReviewResult]:
        assert self.bus is not None
        return [
            ReviewResult(
                review_package_id=review_packages[0].id,
                package_id=review_packages[0].package_id,
                reviewer_agent=review_packages[0].reviewer_agent,
                target_agent=review_packages[0].target_agent,
                status=ReviewStatus.APPROVED,
                severity="low",
                summary="WP review approved.",
            )
        ]

    async def review_final_execution(
        self,
        work_packages,
        execution_results,
        review_results,
    ) -> ReviewResult:
        return ReviewResult(
            review_package_id="RP-FINAL-codex",
            package_id="FINAL",
            reviewer_agent="codex",
            target_agent="project",
            status=ReviewStatus.APPROVED,
            severity="low",
            scope="final",
            summary="Final review approved.",
        )


class FakeExecutionReviewOrchestrator(FakeReviewOrchestrator):
    async def execute_work_packages(
        self,
        work_packages,
        decisions=None,
        result_callback=None,
    ) -> list[ExecutionResult]:
        return [
            ExecutionResult(
                package_id=work_packages[0].id,
                agent_name=work_packages[0].owner_agent,
                status=WorkStatus.DONE,
                summary="Implemented work package.",
            )
        ]


class FakeRepairReviewOrchestrator(FakeReviewOrchestrator):
    review_calls = 0

    async def review_work_packages(
        self,
        review_packages,
        work_packages,
        execution_results,
    ) -> list[ReviewResult]:
        type(self).review_calls += 1
        if type(self).review_calls == 1:
            return [
                ReviewResult(
                    review_package_id=review_packages[0].id,
                    package_id=review_packages[0].package_id,
                    reviewer_agent=review_packages[0].reviewer_agent,
                    target_agent=review_packages[0].target_agent,
                    status=ReviewStatus.CHANGES_REQUESTED,
                    severity="high",
                    summary="Needs repair.",
                    required_changes=["Add retry regression test."],
                )
            ]
        return await super().review_work_packages(
            review_packages,
            work_packages,
            execution_results,
        )

    async def execute_work_packages(
        self,
        work_packages,
        decisions=None,
        result_callback=None,
    ) -> list[ExecutionResult]:
        return [
            ExecutionResult(
                package_id=work_packages[0].id,
                agent_name=work_packages[0].last_executor or work_packages[0].owner_agent,
                status=WorkStatus.DONE,
                summary="Repaired work package.",
            )
        ]


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


def test_textual_workflow_controller_runs_review_all(tmp_path) -> None:
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
        )
    ]
    workflow.set_target_workspace(tmp_path / "game")
    workflow.begin_execution()
    workflow.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="claude",
                status=WorkStatus.DONE,
                summary="Implemented client.",
            )
        ]
    )
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeReviewOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.request_review(["all"])

    assert outcome.running is True
    assert controller.wait_until_idle(timeout=2.0)
    final = controller.drain_updates()
    assert final is not None
    assert final.snapshot.state == "done"
    assert [result.status for result in controller.workflow.review_results] == [
        ReviewStatus.APPROVED,
        ReviewStatus.APPROVED,
    ]


def test_textual_workflow_controller_auto_reviews_after_execution(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 구현", ["claude"])
    workflow.session.blueprint = Blueprint(
        title="Game",
        summary="Build a game.",
        acceptance_criteria=["runs"],
    )
    workflow.set_target_workspace(tmp_path / "game")
    workflow.set_state(WorkflowState.BLUEPRINT_READY, reason="test blueprint ready")
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeExecutionReviewOrchestrator,
        archive_active_session=False,
    )

    execution = controller.request_execution()

    assert execution.running is True
    assert controller.wait_until_idle(timeout=2.0)
    review_started = controller.drain_updates()
    assert review_started is not None
    assert review_started.running is True
    assert review_started.message == "Review started after execution."
    assert controller.wait_until_idle(timeout=2.0)
    final = controller.drain_updates()
    assert final is not None
    assert final.snapshot.state == "done"
    assert [result.status for result in controller.workflow.review_results] == [
        ReviewStatus.APPROVED,
        ReviewStatus.APPROVED,
    ]


def test_textual_workflow_controller_restarts_execution_for_review_repairs(tmp_path) -> None:
    FakeRepairReviewOrchestrator.review_calls = 0
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
            last_executor="claude",
        )
    ]
    workflow.set_target_workspace(tmp_path / "game")
    workflow.begin_execution()
    workflow.record_execution_results(
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="claude",
                status=WorkStatus.DONE,
                summary="Implemented client.",
            )
        ]
    )
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeRepairReviewOrchestrator,
        archive_active_session=False,
    )

    review = controller.request_review(["wp"])

    assert review.running is True
    assert controller.wait_until_idle(timeout=2.0)
    repair = controller.drain_updates()
    assert repair is not None
    assert repair.running is True
    assert "Review requested repairs" in repair.message
    assert controller.workflow.pending_execution_package_ids() == ["WP-001"]
    assert controller.wait_until_idle(timeout=2.0)
    auto_review = controller.drain_updates()
    assert auto_review is not None
    assert auto_review.running is True
    assert auto_review.message == "Review started after execution."
    assert controller.wait_until_idle(timeout=2.0)
    final = controller.drain_updates()
    assert final is not None
    assert final.snapshot.state == "done"
    assert FakeRepairReviewOrchestrator.review_calls == 2


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


class FakeExecutionOrchestrator(FakeOrchestrator):
    executed_packages: list[list[str]] = []

    async def execute_work_packages(self, work_packages, decisions=()):
        self.__class__.executed_packages.append([package.id for package in work_packages])
        return [
            ExecutionResult(
                package_id=package.id,
                agent_name=package.owner_agent,
                status=WorkStatus.DONE,
                summary=f"Retried {package.id}.",
            )
            for package in work_packages
        ]


def test_textual_workflow_controller_retries_selected_failed_packages_only(tmp_path) -> None:
    FakeExecutionOrchestrator.executed_packages = []
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 구현", ["claude", "codex"])
    workflow.session.work_packages = [
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
        WorkPackage(
            id="WP-003",
            title="docs",
            owner_agent="codex",
            objective="Write docs.",
            status=WorkStatus.DONE,
        ),
    ]
    workflow.set_target_workspace(tmp_path / "game")
    workflow.set_state(WorkflowState.FAILED, reason="simulate failed execution")
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeExecutionOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.confirm_execution_retry("custom", ["WP-002"])

    assert outcome.execution_requested is True
    assert controller.workflow.session.work_packages[0].status == WorkStatus.FAILED
    assert controller.workflow.session.work_packages[1].status == WorkStatus.PENDING
    assert controller.workflow.session.execution_run["retry_packages"] == ["WP-002"]
    assert controller.wait_until_idle(timeout=2.0)
    assert FakeExecutionOrchestrator.executed_packages == [["WP-002"]]
    final = controller.drain_updates()
    assert final is not None
    assert controller.workflow.session.work_packages[0].status == WorkStatus.FAILED
    assert controller.workflow.session.work_packages[1].status == WorkStatus.DONE


def test_textual_workflow_controller_retry_requires_target_workspace(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    workflow = WorkflowEngine(config.effective_state_dir)
    workflow.start("게임 구현", ["claude"])
    workflow.session.work_packages = [
        WorkPackage(
            id="WP-001",
            title="client",
            owner_agent="claude",
            objective="Build client.",
            status=WorkStatus.FAILED,
        )
    ]
    workflow.set_state(WorkflowState.FAILED, reason="simulate failed execution")
    controller = TextualWorkflowController(
        config,
        workflow=workflow,
        orchestrator_factory=FakeExecutionOrchestrator,
        archive_active_session=False,
    )

    outcome = controller.confirm_execution_retry("failed")

    assert outcome.target_workspace_required is True
    assert outcome.execution_requested is False
    assert controller.workflow.session.work_packages[0].status == WorkStatus.FAILED
