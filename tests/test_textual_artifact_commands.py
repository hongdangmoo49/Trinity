from trinity.context.shared import SharedContextEngine
from trinity.textual_app.artifact_commands import artifact_command_presentation


def _engine(tmp_path):
    shared = tmp_path / "shared.md"
    shared.write_text("# Shared\n", encoding="utf-8")
    return SharedContextEngine(shared, memory_index_enabled=False)


def test_artifact_command_presentation_requires_record_id(tmp_path) -> None:
    presentation = artifact_command_presentation(_engine(tmp_path), [], lang="ko")

    assert presentation.title == "아티팩트"
    assert presentation.body == "사용법: `/artifact <memory-id>`"
    assert presentation.severity == "warning"


def test_artifact_command_presentation_renders_lookup_result(tmp_path) -> None:
    presentation = artifact_command_presentation(
        _engine(tmp_path),
        ["memory-1"],
    )

    assert presentation.title == "Artifact"
    assert "Memory index is disabled" in presentation.body
    assert presentation.severity == "info"
