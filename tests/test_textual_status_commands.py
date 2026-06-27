from trinity.textual_app.snapshot import ProviderSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.status_commands import status_command_result


def test_status_command_result_builds_local_command_snapshot() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-status",
        goal="Check status",
        state="executing",
    )

    result = status_command_result("/status", snapshot)

    assert result.command == "/status"
    assert result.title == "Status"
    assert "- Workflow: `wf-status`" in result.body
    assert result.table_columns == ("Item", "Value")
    assert ("State", "executing") in result.table_rows


def test_status_command_result_includes_provider_rows() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-status",
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status="ready",
                readiness="ready",
            )
        ],
    )

    result = status_command_result("/status", snapshot)

    assert "| claude | yes | ready | ready |" in result.body
    assert ("Provider: claude", "ready; enabled=yes; readiness=ready") in (
        result.table_rows
    )


def test_status_command_result_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        session_id="wf-ko",
        goal="상태 확인",
        state="executing",
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status="ready",
                readiness="ready",
            )
        ],
    )

    result = status_command_result("/status", snapshot, lang="ko")

    assert result.title == "상태"
    assert "- 워크플로우: `wf-ko`" in result.body
    assert "| claude | 예 | 준비됨 | 준비됨 |" in result.body
    assert result.table_columns == ("항목", "값")
    assert ("상태", "실행 중") in result.table_rows
    assert ("프로바이더: claude", "준비됨; 활성화=예; 준비 상태=준비됨") in (
        result.table_rows
    )
