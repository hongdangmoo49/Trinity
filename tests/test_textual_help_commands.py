from trinity.textual_app.help_commands import help_command_presentation


def test_help_command_presentation_describes_registry_commands() -> None:
    presentation = help_command_presentation()

    assert presentation.title == "Trinity Commands"
    assert "handled before provider prompts" in presentation.body
    assert "### Categories" in presentation.body
    assert presentation.table_columns == (
        "Command",
        "Category",
        "Agent Call",
        "Summary",
    )
    assert any(row[0] == "/status" for row in presentation.table_rows)


def test_help_command_presentation_uses_korean_labels() -> None:
    presentation = help_command_presentation(lang="ko")

    assert presentation.title == "Trinity 명령"
    assert "Trinity 소유 슬래시 명령" in presentation.body
    assert "### 카테고리" in presentation.body
    assert presentation.table_columns == (
        "명령",
        "카테고리",
        "에이전트 호출",
        "요약",
    )
    assert any(row[0] == "/status" for row in presentation.table_rows)
