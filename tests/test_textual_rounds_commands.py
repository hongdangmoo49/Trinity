from trinity.slash_commands import SESSION_ONLY_SETTING_NOTICE
from trinity.textual_app.rounds_commands import (
    rounds_current_presentation,
    rounds_error_presentation,
    rounds_set_presentation,
)


def test_rounds_current_presentation_describes_current_value() -> None:
    presentation = rounds_current_presentation(3)

    assert presentation.title == "Rounds"
    assert presentation.body.startswith("Current max rounds: `3`.")
    assert SESSION_ONLY_SETTING_NOTICE in presentation.body
    assert presentation.action_hint == "Use `/rounds <1..20>` to change it for this session."
    assert presentation.table_columns == ("Item", "Value")
    assert presentation.table_rows == (
        ("Current max rounds", "3"),
        ("Allowed range", "1..20"),
    )


def test_rounds_set_presentation_describes_updated_value() -> None:
    presentation = rounds_set_presentation(7)

    assert presentation.title == "Rounds"
    assert presentation.body.startswith("Max rounds set to `7` for this session only.")
    assert SESSION_ONLY_SETTING_NOTICE in presentation.body
    assert presentation.action_hint == ""
    assert presentation.table_rows == (
        ("Current max rounds", "7"),
        ("Allowed range", "1..20"),
    )


def test_rounds_error_presentation_marks_warning() -> None:
    presentation = rounds_error_presentation(
        "Invalid number.",
        "Use `/rounds <1..20>`.",
    )

    assert presentation.title == "Rounds"
    assert presentation.body == "Invalid number."
    assert presentation.severity == "warning"
    assert presentation.action_hint == "Use `/rounds <1..20>`."
    assert presentation.table_columns == ()
    assert presentation.table_rows == ()


def test_rounds_presentation_uses_korean_labels() -> None:
    current = rounds_current_presentation(3, lang="ko")
    updated = rounds_set_presentation(7, lang="ko")
    error = rounds_error_presentation(
        "숫자가 올바르지 않습니다.",
        "`/rounds <1..20>`를 사용하세요.",
        lang="ko",
    )

    assert current.title == "라운드"
    assert current.body.startswith("현재 최대 라운드: `3`.")
    assert current.table_columns == ("항목", "값")
    assert current.table_rows == (
        ("현재 최대 라운드", "3"),
        ("허용 범위", "1..20"),
    )
    assert updated.body.startswith("이 세션의 최대 라운드를 `7`로 설정했습니다.")
    assert error.title == "라운드"
    assert error.severity == "warning"
