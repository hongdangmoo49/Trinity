from trinity.slash_commands import SESSION_ONLY_SETTING_NOTICE
from trinity.textual_app.caveman_commands import (
    caveman_current_presentation,
    caveman_error_presentation,
    caveman_set_presentation,
)


def test_caveman_current_presentation_describes_current_settings() -> None:
    presentation = caveman_current_presentation("on", "full")

    assert presentation.title == "Caveman"
    assert presentation.body.startswith("Caveman: `on` (`full`).")
    assert SESSION_ONLY_SETTING_NOTICE in presentation.body
    assert presentation.action_hint == (
        "Use `/caveman <mode>` to change it for this session."
    )
    assert presentation.table_columns == ("Item", "Value")
    assert presentation.table_rows == (
        ("Mode", "on"),
        ("Intensity", "full"),
        ("Allowed", "on, off, lite, full, ultra"),
    )


def test_caveman_set_presentation_describes_updated_settings() -> None:
    presentation = caveman_set_presentation("on", "lite")

    assert presentation.title == "Caveman"
    assert presentation.body.startswith(
        "Caveman set to `on` (`lite`) for this session only."
    )
    assert SESSION_ONLY_SETTING_NOTICE in presentation.body
    assert presentation.action_hint == ""
    assert presentation.table_rows == (
        ("Mode", "on"),
        ("Intensity", "lite"),
        ("Allowed", "on, off, lite, full, ultra"),
    )


def test_caveman_error_presentation_marks_warning() -> None:
    presentation = caveman_error_presentation(
        "Use: /caveman [on|off|lite|full|ultra]",
        "Allowed modes: on, off, lite, full, ultra.",
    )

    assert presentation.title == "Caveman"
    assert presentation.body == "Use: /caveman [on|off|lite|full|ultra]"
    assert presentation.severity == "warning"
    assert presentation.action_hint == "Allowed modes: on, off, lite, full, ultra."
    assert presentation.table_columns == ()
    assert presentation.table_rows == ()


def test_caveman_presentation_uses_korean_labels() -> None:
    current = caveman_current_presentation("off", "full", lang="ko")
    updated = caveman_set_presentation("on", "ultra", lang="ko")
    error = caveman_error_presentation(
        "사용법: /caveman [on|off|lite|full|ultra]",
        "허용 모드: on, off, lite, full, ultra.",
        lang="ko",
    )

    assert current.title == "간결 모드"
    assert current.body.startswith("간결 모드: `off` (`full`).")
    assert current.table_columns == ("항목", "값")
    assert current.table_rows == (
        ("모드", "off"),
        ("강도", "full"),
        ("허용값", "on, off, lite, full, ultra"),
    )
    assert updated.body.startswith(
        "이 세션의 간결 모드를 `on` (`ultra`)로 설정했습니다."
    )
    assert error.title == "간결 모드"
    assert error.severity == "warning"
