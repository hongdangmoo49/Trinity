from trinity.textual_app.slash_error_commands import (
    slash_syntax_error_presentation,
    unknown_slash_command_presentation,
)


def test_slash_syntax_error_presentation_marks_warning() -> None:
    presentation = slash_syntax_error_presentation("No closing quotation")

    assert presentation.title == "Syntax Error"
    assert presentation.body == "No closing quotation"
    assert presentation.severity == "warning"
    assert presentation.table_columns == ()
    assert presentation.table_rows == ()


def test_unknown_slash_command_presentation_includes_suggestions() -> None:
    presentation = unknown_slash_command_presentation("/stats")

    assert presentation.title == "Unknown Command"
    assert "`/stats` is not a Trinity slash command." in presentation.body
    assert "Did you mean:" in presentation.body
    assert presentation.severity == "warning"
    assert presentation.table_columns == ("Suggestion", "Summary")
    assert any(row[0] == "/status" for row in presentation.table_rows)


def test_slash_error_presentations_use_korean_labels() -> None:
    syntax = slash_syntax_error_presentation("따옴표가 닫히지 않았습니다.", lang="ko")
    unknown = unknown_slash_command_presentation("/stats", lang="ko")

    assert syntax.title == "구문 오류"
    assert syntax.body == "따옴표가 닫히지 않았습니다."
    assert syntax.severity == "warning"
    assert unknown.title == "알 수 없는 명령"
    assert "`/stats`은 Trinity 슬래시 명령이 아닙니다." in unknown.body
    assert "다음 명령을 찾으셨나요:" in unknown.body
    assert unknown.table_columns == ("추천", "요약")
    assert any(row[0] == "/status" for row in unknown.table_rows)
