"""Tests for local context memory command helpers."""

from trinity.config import TrinityConfig
from trinity.context.commands import (
    artifact_markdown,
    compact_memory_markdown,
    engine_from_config,
    memory_stats_markdown,
    memory_stats_rows,
)


def test_memory_command_helpers_render_stats_and_artifact(tmp_path):
    config = TrinityConfig.default_config(project_dir=tmp_path)
    engine = engine_from_config(config)
    engine.initialize("Build app", ["codex"])
    engine.append_task_result(
        package_id="WP-001",
        agent="codex",
        status="done",
        summary="Implemented endpoint.",
    )

    stats = memory_stats_markdown(engine)
    rows = memory_stats_rows(engine)
    record_id = engine.memory_store.recent(limit=1)[0].id if engine.memory_store else ""
    artifact = artifact_markdown(engine, record_id)

    assert "Memory Stats" in stats
    assert ("Records", "1") in rows
    assert "WP-001 / codex" in artifact


def test_compact_memory_command_rebuilds_projection(tmp_path):
    config = TrinityConfig.default_config(project_dir=tmp_path)
    engine = engine_from_config(config)
    engine.initialize("Build app", ["codex"])
    engine.append_task_result(
        package_id="WP-001",
        agent="codex",
        status="done",
        summary="Implemented endpoint.",
    )

    body = compact_memory_markdown(engine, target_bytes=4096, recent_records=10)

    assert "Memory Compact" in body
    assert "shared_size_bytes" in body
    assert "Memory Projection" in engine.read()
