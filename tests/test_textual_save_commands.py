from trinity.textual_app.save_commands import save_command_presentation


def test_save_command_presentation_uses_auto_persist_message() -> None:
    presentation = save_command_presentation()

    assert presentation.title == "Save"
    assert presentation.body == (
        "Textual workflows are persisted automatically. "
        "Use /report save for Markdown export."
    )


def test_save_command_presentation_uses_korean_message() -> None:
    presentation = save_command_presentation(lang="ko")

    assert presentation.title == "저장"
    assert presentation.body == (
        "Trinity 워크플로우는 자동으로 저장됩니다. "
        "마크다운 리포트 내보내기는 /report save를 사용하세요."
    )
