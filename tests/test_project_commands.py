from __future__ import annotations

from trinity.textual_app.project_commands import project_command_presentation


def test_project_command_presentation_uses_selected_workspace(tmp_path) -> None:
    target = tmp_path / "target-app"
    target.mkdir()

    presentation = project_command_presentation(
        tmp_path,
        {},
        lang="ko",
        target_workspace=target,
    )

    assert presentation.title == "프로젝트 진단"
    assert f"대상 워크스페이스: {target}" in presentation.body
    assert "시작 준비:" in presentation.body
    assert (
        "프로젝트 인테이크: 기록 없음 | 다음: 작업을 입력하거나 /project analyze"
        in presentation.body
    )
    assert "trinity project new" not in presentation.body
    assert "프로젝트 시작:" not in presentation.body
    assert "프로젝트 모드:" not in presentation.body
    assert presentation.action_hint == (
        "작업 폴더는 /workspace, 프로젝트 도구는 /project analyze 또는 "
        "/project brief에서 엽니다."
    )


def test_project_command_presentation_marks_missing_target(tmp_path) -> None:
    presentation = project_command_presentation(tmp_path, {}, target_workspace=None)

    assert presentation.title == "Project Diagnostics"
    assert "Target workspace: not selected" in presentation.body
    assert (
        "Project intake: not recorded | next: type the task or /project analyze"
        in presentation.body
    )
    assert "trinity project new" not in presentation.body
    assert "Project start:" not in presentation.body
    assert "Project mode:" not in presentation.body
    assert presentation.action_hint == (
        "Use /workspace to select a target; open project tools with "
        "/project analyze or /project brief."
    )
