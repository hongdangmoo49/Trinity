from __future__ import annotations

import asyncio
import time

import pytest

from trinity.config import TrinityConfig
from trinity.models import ConsensusResult, DeliberationResult
from trinity.textual_app.workflow_controller import TextualWorkflowController
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import WorkflowEngine, WorkflowState
from trinity.workflow.models import OpenQuestion


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
