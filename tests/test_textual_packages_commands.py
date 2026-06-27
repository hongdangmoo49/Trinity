from trinity.textual_app.packages_commands import packages_command_presentation
from trinity.textual_app.snapshot import WorkflowNexusSnapshot


def test_packages_command_presentation_marks_empty_packages() -> None:
    presentation = packages_command_presentation(WorkflowNexusSnapshot())

    assert presentation.title == "Packages"
    assert presentation.empty is True
    assert presentation.body == (
        "No workflow work packages generated in the current session."
    )
    assert presentation.action_hint == (
        "Finish planning until a blueprint or local WP graph is generated."
    )
    assert presentation.table_columns == ("#", "Source", "Package")
    assert presentation.table_rows == ()


def test_packages_command_presentation_includes_central_and_local_rows() -> None:
    snapshot = WorkflowNexusSnapshot(
        central_work_packages=["WP-001 claude: design"],
        work_packages=["WP-002 codex: build"],
    )

    presentation = packages_command_presentation(snapshot)

    assert presentation.empty is False
    assert presentation.action_hint == ""
    assert presentation.body == (
        "1. **central** WP-001 claude: design\n"
        "2. **local** WP-002 codex: build"
    )
    assert presentation.table_rows == (
        ("1", "central", "WP-001 claude: design"),
        ("2", "local", "WP-002 codex: build"),
    )


def test_packages_command_presentation_uses_korean_labels() -> None:
    snapshot = WorkflowNexusSnapshot(
        central_work_packages=["WP-001 claude: 설계"],
        work_packages=["WP-002 codex: 구현"],
    )

    presentation = packages_command_presentation(snapshot, lang="ko")

    assert presentation.title == "작업 패키지"
    assert presentation.empty is False
    assert presentation.body == (
        "1. **중앙** WP-001 claude: 설계\n"
        "2. **로컬** WP-002 codex: 구현"
    )
    assert presentation.table_columns == ("#", "출처", "작업 패키지")
    assert presentation.table_rows == (
        ("1", "중앙", "WP-001 claude: 설계"),
        ("2", "로컬", "WP-002 codex: 구현"),
    )
