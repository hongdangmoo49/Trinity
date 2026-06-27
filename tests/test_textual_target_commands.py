from pathlib import Path
from types import SimpleNamespace

from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.target_workspace import TargetWorkspacePreparation
from trinity.textual_app.target_commands import (
    target_command_action,
    target_cancelled_snapshot,
    target_cleared_presentation,
    target_current_presentation,
    target_not_directory_presentation,
    target_prepare_result_presentation,
    target_prepare_failed_presentation,
    target_set_presentation,
    target_workspace_apply_effect,
    target_workspace_presentation,
)


def test_target_current_presentation_describes_unset_target() -> None:
    presentation = target_current_presentation(None)

    assert presentation.title == "Target"
    assert presentation.body == "Current target: `(not set)`"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "Use `/target <path>` or Select Workspace before execution."
    )


def test_target_cleared_presentation_describes_cleared_target() -> None:
    presentation = target_cleared_presentation()

    assert presentation.title == "Target"
    assert presentation.body == "Target workspace cleared."
    assert presentation.empty is False
    assert presentation.severity == "info"


def test_target_error_presentations_mark_warning() -> None:
    not_directory = target_not_directory_presentation("/tmp/file")
    prepare_failed = target_prepare_failed_presentation("denied")

    assert not_directory.title == "Target"
    assert not_directory.body == (
        "Target path exists but is not a directory: `/tmp/file`"
    )
    assert not_directory.severity == "warning"
    assert not_directory.empty is True
    assert prepare_failed.body == "Could not prepare target workspace: denied"
    assert prepare_failed.severity == "warning"
    assert prepare_failed.empty is True


def test_target_prepare_result_presentation_maps_errors() -> None:
    not_directory = target_prepare_result_presentation(
        TargetWorkspacePreparation(error="not_directory", message="/tmp/file")
    )
    os_error = target_prepare_result_presentation(
        TargetWorkspacePreparation(error="os_error", message="denied")
    )
    ready = target_prepare_result_presentation(
        TargetWorkspacePreparation(resolved_path=Path("/tmp/app"))
    )

    assert not_directory is not None
    assert not_directory.body == "Target path exists but is not a directory: `/tmp/file`"
    assert os_error is not None
    assert os_error.body == "Could not prepare target workspace: denied"
    assert ready is None


def test_target_workspace_presentation_includes_workspace_rows() -> None:
    presentation = target_workspace_presentation(
        "/tmp/app",
        inside_control_repo=False,
        control_repo_confirmed=True,
    )

    assert presentation.title == "Target"
    assert presentation.body == "Target workspace: `/tmp/app`"
    assert presentation.table_columns == ("Item", "Value")
    assert presentation.table_rows == (
        ("Path", "/tmp/app"),
        ("Inside control repo", "no"),
        ("Control repo confirmed", "yes"),
    )


def test_target_set_presentation_calculates_control_repo_state() -> None:
    path = Path("/repo/app")
    presentation = target_set_presentation(
        path,
        control_repo=Path("/repo"),
        control_repo_confirmed=True,
    )

    path_text = str(path)
    assert presentation.body == f"Target workspace: `{path_text}`"
    assert presentation.table_rows == (
        ("Path", path_text),
        ("Inside control repo", "yes"),
        ("Control repo confirmed", "yes"),
    )


def test_target_workspace_apply_effect_uses_workflow_outcome_snapshot() -> None:
    resolved = Path("/repo/app")
    outcome_snapshot = WorkflowNexusSnapshot(session_id="wf-outcome")
    fallback_snapshot = WorkflowNexusSnapshot(session_id="wf-fallback")
    outcome = SimpleNamespace(snapshot=outcome_snapshot)

    effect = target_workspace_apply_effect(
        resolved,
        outcome,
        fallback_snapshot,
        control_repo=Path("/repo"),
        control_repo_confirmed=True,
    )

    assert effect.resolved == resolved
    assert effect.snapshot is outcome_snapshot
    assert effect.workflow_outcome is outcome
    assert effect.apply_workflow_outcome is True
    assert effect.presentation.body == f"Target workspace: `{resolved}`"


def test_target_workspace_apply_effect_uses_fallback_without_outcome_snapshot() -> None:
    resolved = Path("/workspace/app")
    fallback_snapshot = WorkflowNexusSnapshot(session_id="wf-fallback")

    effect = target_workspace_apply_effect(
        resolved,
        object(),
        fallback_snapshot,
        control_repo=Path("/repo"),
        control_repo_confirmed=False,
        lang="ko",
    )

    assert effect.snapshot is fallback_snapshot
    assert effect.workflow_outcome is None
    assert effect.apply_workflow_outcome is False
    assert effect.presentation.title == "대상"
    assert effect.presentation.body == f"대상 작업 폴더: `{resolved}`"


def test_target_command_action_records_current_target() -> None:
    current = Path("/tmp/app")
    action = target_command_action(
        [],
        current=current,
        project_dir=Path("/repo"),
    )

    assert action.action == "record"
    assert action.path is None
    assert action.presentation is not None
    assert action.presentation.body == f"Current target: `{current}`"


def test_target_command_action_routes_clear() -> None:
    action = target_command_action(
        ["clear"],
        current=Path("/tmp/app"),
        project_dir=Path("/repo"),
    )

    assert action.action == "clear"
    assert action.path is None
    assert action.presentation is None


def test_target_command_action_routes_control_repo_confirmation() -> None:
    action = target_command_action(
        ["nested"],
        current=None,
        project_dir=Path("/repo"),
    )

    assert action.action == "confirm"
    assert action.path == Path("/repo/nested")
    assert action.presentation is None


def test_target_command_action_routes_external_set() -> None:
    action = target_command_action(
        ["/workspace/app"],
        current=None,
        project_dir=Path("/repo"),
    )

    assert action.action == "set"
    assert action.path == Path("/workspace/app")
    assert action.presentation is None


def test_target_cancelled_snapshot_describes_selection_cancel() -> None:
    snapshot = target_cancelled_snapshot()

    assert snapshot.command == "/target"
    assert snapshot.title == "Target"
    assert snapshot.body == "Target workspace selection cancelled."
    assert snapshot.severity == "warning"
    assert snapshot.empty is True
    assert snapshot.action_hint == (
        "Choose a workspace outside the Trinity control repo."
    )


def test_target_cancelled_snapshot_describes_preflight_cancel() -> None:
    snapshot = target_cancelled_snapshot("/execute", kind="preflight")

    assert snapshot.command == "/execute"
    assert snapshot.title == "Target"
    assert snapshot.body == "Workspace preflight cancelled."
    assert snapshot.severity == "warning"
    assert snapshot.empty is True


def test_target_presentations_use_korean_labels() -> None:
    current = target_current_presentation(None, lang="ko")
    cleared = target_cleared_presentation(lang="ko")
    not_directory = target_not_directory_presentation("/tmp/file", lang="ko")
    prepare_failed = target_prepare_failed_presentation("denied", lang="ko")
    workspace = target_workspace_presentation(
        "/tmp/app",
        inside_control_repo=False,
        control_repo_confirmed=True,
        lang="ko",
    )
    cancelled = target_cancelled_snapshot(lang="ko")

    assert current.title == "대상"
    assert current.body == "현재 대상: `(미설정)`"
    assert current.empty is True
    assert current.action_hint.startswith("실행 전에 `/target <path>`")
    assert cleared.body == "대상 작업 폴더를 초기화했습니다."
    assert not_directory.body == (
        "대상 경로가 이미 존재하지만 디렉터리가 아닙니다: `/tmp/file`"
    )
    assert prepare_failed.body == "대상 작업 폴더를 준비할 수 없습니다: denied"
    assert workspace.body == "대상 작업 폴더: `/tmp/app`"
    assert workspace.table_columns == ("항목", "값")
    assert workspace.table_rows == (
        ("경로", "/tmp/app"),
        ("제어 저장소 내부", "아니오"),
        ("제어 저장소 확인", "예"),
    )
    assert cancelled.title == "대상"
    assert cancelled.body == "대상 작업 폴더 선택을 취소했습니다."
