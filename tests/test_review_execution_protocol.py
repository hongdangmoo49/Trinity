"""Tests for provider-backed workflow review execution."""

from unittest.mock import AsyncMock

import pytest

from trinity.context.shared import SharedContextEngine
from trinity.models import DeliberationMessage, MessageRole, ResponseStatus
from trinity.providers.policy import InvocationAccess
from trinity.tui.events import TUIEventType
from trinity.workflow import (
    ExecutionResult,
    ReviewExecutionProtocol,
    ReviewPackage,
    ReviewStatus,
    WorkPackage,
    WorkStatus,
)


def _message(content: str, metadata: dict | None = None) -> DeliberationMessage:
    return DeliberationMessage(
        source="reviewer",
        target="all",
        round_num=0,
        role=MessageRole.TASK,
        content=content,
        metadata={"raw_output": content, **(metadata or {})},
    )


@pytest.mark.asyncio
async def test_review_execution_protocol_reviews_work_package(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    agent.send_and_wait.return_value = _message(
        "REVIEW STATUS: CHANGES_REQUESTED\n"
        "SEVERITY: HIGH\n\n"
        "SUMMARY:\n"
        "Needs safer terminal handling.\n\n"
        "FINDINGS:\n"
        "- Resize event is not covered.\n\n"
        "REQUIRED CHANGES:\n"
        "- Add resize regression test.\n\n"
        "REVIEWED FILES:\n"
        "- src/ui.py\n\n"
        "EXECUTION RISKS:\n"
        "- Layout can break on small terminals.\n\n"
        "ANTI PATTERNS:\n"
        "- Broad exception handling.\n\n"
        "PERFORMANCE NOTES:\n"
        "- Rendering remains bounded.\n\n"
        "FOLLOW UP:\n"
        "- Re-run textual tests.\n"
    )
    events = []
    protocol = ReviewExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "reviews",
        event_callback=events.append,
        target_workspace=tmp_path / "route-bot",
    )

    results = await protocol.review_work_packages(
        [
            ReviewPackage(
                package_id="WP-001",
                reviewer_agent="codex",
                target_agent="claude",
                criteria=["Check runtime errors"],
            )
        ],
        [
            WorkPackage(
                id="WP-001",
                title="UI shell",
                owner_agent="claude",
                objective="Build shell.",
                expected_files=["src/ui.py"],
            )
        ],
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="claude",
                status=WorkStatus.DONE,
                summary="Implemented shell.",
                files_changed=["src/ui.py"],
            )
        ],
    )

    assert len(results) == 1
    result = results[0]
    assert result.status == ReviewStatus.CHANGES_REQUESTED
    assert result.severity == "high"
    assert result.summary == "Needs safer terminal handling."
    assert result.required_changes == ["Add resize regression test."]
    assert result.reviewed_files == ["src/ui.py"]
    assert result.execution_risks == ["Layout can break on small terminals."]
    assert result.anti_patterns == ["Broad exception handling."]
    assert result.performance_notes == ["Rendering remains bounded."]
    assert result.raw_response_path is not None
    assert result.raw_response_path.exists()
    assert agent.send_and_wait.call_args.kwargs["access"] == InvocationAccess.READ_ONLY
    prompt = agent.send_and_wait.call_args.args[0]
    assert "Target Workspace Context" in prompt
    assert str((tmp_path / "route-bot").resolve()) in prompt
    assert [event.type for event in events] == [
        TUIEventType.REVIEW_START,
        TUIEventType.REVIEW_PACKAGE_QUEUED,
        TUIEventType.REVIEW_PACKAGE_STARTED,
        TUIEventType.WORK_PACKAGE_REVIEW_STARTED,
        TUIEventType.REVIEW_PACKAGE_COMPLETED,
        TUIEventType.WORK_PACKAGE_REVIEW_COMPLETED,
        TUIEventType.REVIEW_DONE,
    ]
    queued = events[1]
    assert queued.data["review_package_id"] == "RP-WP-001-codex"
    assert queued.data["package_id"] == "WP-001"
    assert queued.data["reviewer_agent"] == "codex"
    assert queued.data["target_agent"] == "claude"
    completed = events[4]
    assert completed.data["status"] == ReviewStatus.CHANGES_REQUESTED.value
    assert completed.data["summary"] == "Needs safer terminal handling."


@pytest.mark.asyncio
async def test_review_permission_failure_becomes_blocked_result(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    agent = AsyncMock()
    agent.send_and_wait.return_value = _message(
        "Sandbox denied: approval required.",
        metadata={"response_status": ResponseStatus.PERMISSION_REQUIRED.value},
    )
    protocol = ReviewExecutionProtocol(
        agents={"codex": agent},
        shared=shared,
        artifact_dir=tmp_path / "reviews",
    )

    results = await protocol.review_work_packages(
        [
            ReviewPackage(
                package_id="WP-001",
                reviewer_agent="codex",
                target_agent="claude",
                criteria=["Check runtime errors"],
            )
        ],
        [
            WorkPackage(
                id="WP-001",
                title="UI shell",
                owner_agent="claude",
                objective="Build shell.",
            )
        ],
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="claude",
                status=WorkStatus.DONE,
                summary="Implemented shell.",
            )
        ],
    )

    assert len(results) == 1
    assert results[0].status == ReviewStatus.BLOCKED
    assert "approval required" in results[0].summary
    assert agent.send_and_wait.call_args.kwargs["access"] == InvocationAccess.READ_ONLY


@pytest.mark.asyncio
async def test_final_review_falls_back_from_codex_to_claude(tmp_path):
    shared = SharedContextEngine(tmp_path / "shared.md")
    codex = AsyncMock()
    codex.send_and_wait.return_value = _message(
        "provider failed",
        {"response_status": "timeout", "error": "timeout"},
    )
    claude = AsyncMock()
    claude.send_and_wait.return_value = _message(
        "FINAL REVIEW STATUS: APPROVED\n"
        "SEVERITY: LOW\n\n"
        "PROJECT OVERVIEW:\n"
        "Project is coherent and runnable.\n\n"
        "COMPATIBILITY:\n"
        "- Textual UI remains compatible.\n\n"
        "RUN INSTRUCTIONS:\n"
        "- uv run trinity\n"
    )
    protocol = ReviewExecutionProtocol(
        agents={"codex": codex, "claude": claude},
        shared=shared,
        artifact_dir=tmp_path / "reviews",
        target_workspace=tmp_path / "route-bot",
    )

    result = await protocol.review_final_execution(
        [
            WorkPackage(
                id="WP-001",
                title="UI shell",
                owner_agent="claude",
                objective="Build shell.",
                status=WorkStatus.DONE,
            )
        ],
        [
            ExecutionResult(
                package_id="WP-001",
                agent_name="claude",
                status=WorkStatus.DONE,
                summary="Implemented shell.",
            )
        ],
        [],
    )

    assert result.status == ReviewStatus.APPROVED
    assert result.scope == "final"
    assert result.reviewer_agent == "claude"
    assert result.compatibility_notes == ["Textual UI remains compatible."]
    assert result.follow_up == ["uv run trinity"]
    codex.send_and_wait.assert_called_once()
    claude.send_and_wait.assert_called_once()
    prompt = claude.send_and_wait.call_args.args[0]
    assert "Target Workspace Context" in prompt
    assert str((tmp_path / "route-bot").resolve()) in prompt
