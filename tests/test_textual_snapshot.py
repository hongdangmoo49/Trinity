from __future__ import annotations

import os

from trinity.config import TrinityConfig
from trinity.textual_app.snapshot import NexusSnapshotAdapter
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import Blueprint, OpenQuestion, WorkflowPersistence, WorkflowSession, WorkflowState


def test_snapshot_loads_provider_defaults_without_workflow(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.state == "idle"
    assert [provider.name for provider in snapshot.providers] == [
        "claude",
        "codex",
        "antigravity",
    ]
    assert snapshot.providers[0].status == "Queued"
    assert snapshot.providers[1].status == "Disabled"


def test_snapshot_projects_persisted_workflow(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-textual",
            goal="Build UI",
            state=WorkflowState.BLUEPRINT_READY,
            active_agents=["claude"],
            current_round=2,
            pending_questions=[
                OpenQuestion(id="q-1", question="Which theme?", options=["dark"])
            ],
            blueprint=Blueprint(
                title="Workbench",
                summary="Use Textual screens.",
                data_flow=["prompt -> nexus"],
            ),
        )
    )
    persistence.append_event(
        {
            "event": "state_changed",
            "state": "blueprint_ready",
            "workflow_id": "wf-textual",
        }
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    assert snapshot.session_id == "wf-textual"
    assert snapshot.goal == "Build UI"
    assert snapshot.state == "blueprint_ready"
    assert snapshot.synthesis.summary == "Use Textual screens."
    assert [question.question for question in snapshot.questions] == ["Which theme?"]
    assert snapshot.questions[0].options == ["dark"]
    assert snapshot.execution_log == ["state_changed: blueprint_ready"]
    assert snapshot.providers[0].enabled is True
    assert snapshot.providers[1].enabled is False


def test_snapshot_restores_provider_status_from_response_artifacts(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-artifacts",
            goal="Build UI",
            state=WorkflowState.NEEDS_USER_DECISION,
            active_agents=["claude"],
            current_round=1,
            created_at=0,
        )
    )
    response_dir = config.effective_state_dir / "responses" / "round-01"
    response_dir.mkdir(parents=True)
    clean_path = response_dir / "claude-round-1-claude-abc.clean.txt"
    raw_path = response_dir / "claude-round-1-claude-abc.raw.txt"
    clean_path.write_text("Use a compact dashboard.", encoding="utf-8")
    raw_path.write_text("RAW: Use a compact dashboard.", encoding="utf-8")
    os.utime(clean_path, (10, 10))
    os.utime(raw_path, (10, 10))

    snapshot = NexusSnapshotAdapter(config).load_snapshot()

    claude = snapshot.providers[0]
    assert claude.status == "Ready"
    assert claude.summary == "Use a compact dashboard."
    assert claude.raw_output == "RAW: Use a compact dashboard."


def test_snapshot_folds_recent_provider_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.AGENT_RESPONDED,
                data={"agent": "claude", "content": "Use a compact dashboard."},
            )
        ]
    )

    claude = snapshot.providers[0]
    assert claude.status == "Ready"
    assert claude.summary == "Use a compact dashboard."
    assert claude.raw_output == "Use a compact dashboard."


def test_snapshot_projects_active_round_and_synthesis_from_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
            current_round=0,
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(type=TUIEventType.ROUND_START, data={"round_num": 1}),
            TUIEvent(
                type=TUIEventType.AGENT_RESPONDED,
                data={
                    "agent": "claude",
                    "content": "Build a compact game.",
                    "round_num": 1,
                },
            ),
            TUIEvent(
                type=TUIEventType.CONSENSUS_CHECKING,
                data={"round_num": 1},
            ),
        ]
    )

    assert snapshot.round_num == 1
    assert snapshot.synthesis.status == "running"
    assert snapshot.synthesis.consensus_progress == "round 1 synthesizing"
    assert "Central agent is synthesizing round 1" in snapshot.synthesis.summary
    assert snapshot.providers[0].status == "Ready"


def test_snapshot_projects_consensus_result_from_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={
                    "round_num": 1,
                    "reached": False,
                    "agreement_count": 1,
                    "total_agents": 3,
                    "summary": "Need another round to resolve scope.",
                },
            )
        ]
    )

    assert snapshot.round_num == 1
    assert snapshot.synthesis.status == "ready"
    assert snapshot.synthesis.summary == "Need another round to resolve scope."
    assert snapshot.synthesis.consensus_progress == (
        "round 1 consensus not reached (1/3)"
    )


def test_snapshot_projects_synthesis_fallback_reason_from_events(tmp_path) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={
                    "round_num": 1,
                    "reached": False,
                    "agreement_count": 0,
                    "total_agents": 3,
                    "summary": "No consensus yet.",
                    "synthesis_source": "heuristic",
                    "fallback_used": True,
                    "fallback_reason": "model synthesis provider returned timeout",
                },
            )
        ]
    )

    assert snapshot.synthesis.source == "heuristic"
    assert "fallback used" in snapshot.synthesis.consensus_progress
    assert "model synthesis provider returned timeout" in snapshot.synthesis.summary


def test_snapshot_projects_new_round_collection_after_previous_result(
    tmp_path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    persistence = WorkflowPersistence(config.effective_state_dir)
    persistence.save(
        WorkflowSession(
            id="wf-runtime",
            goal="Build game",
            state=WorkflowState.DELIBERATING,
            active_agents=["claude"],
        )
    )

    snapshot = NexusSnapshotAdapter(config).load_snapshot(
        [
            TUIEvent(
                type=TUIEventType.CONSENSUS_RESULT,
                data={
                    "round_num": 1,
                    "reached": False,
                    "agreement_count": 1,
                    "total_agents": 3,
                    "summary": "Need another round to resolve scope.",
                },
            ),
            TUIEvent(
                type=TUIEventType.ROUND_START,
                data={
                    "round_num": 2,
                },
            ),
        ]
    )

    assert snapshot.round_num == 2
    assert snapshot.synthesis.status == "waiting"
    assert snapshot.synthesis.consensus_progress == "round 2 collecting"
    assert snapshot.synthesis.summary == (
        "Collecting provider responses for round 2."
    )
