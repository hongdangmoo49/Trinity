from trinity.context.shared import SharedContextEngine
from trinity.textual_app.memory_commands import memory_command_presentation


def _engine(tmp_path):
    shared = tmp_path / "shared.md"
    shared.write_text("# Shared\n", encoding="utf-8")
    return SharedContextEngine(shared, memory_index_enabled=False)


def test_memory_command_presentation_defaults_to_stats(tmp_path) -> None:
    presentation = memory_command_presentation(
        _engine(tmp_path),
        [],
        target_bytes=1024,
        recent_records=3,
    )

    assert presentation.title == "Memory Stats"
    assert "Memory index is disabled" in presentation.body
    assert presentation.severity == "info"
    assert presentation.table_columns == ("Item", "Value")
    assert ("Memory index", "disabled") in presentation.table_rows


def test_memory_command_presentation_builds_cleanup_error(tmp_path) -> None:
    presentation = memory_command_presentation(
        _engine(tmp_path),
        ["cleanup"],
        target_bytes=1024,
        recent_records=3,
    )

    assert presentation.title == "Memory Cleanup"
    assert presentation.severity == "warning"
    assert "Usage:" in presentation.body
    assert presentation.table_columns == ()
    assert presentation.table_rows == ()


def test_memory_command_presentation_builds_compact_result(tmp_path) -> None:
    presentation = memory_command_presentation(
        _engine(tmp_path),
        ["compact"],
        target_bytes=1024,
        recent_records=3,
    )

    assert presentation.title == "Memory Compact"
    assert "- target_bytes: 1024" in presentation.body
    assert "- recent_records: 3" in presentation.body
    assert presentation.table_columns == ("Item", "Value")
    assert presentation.table_rows
