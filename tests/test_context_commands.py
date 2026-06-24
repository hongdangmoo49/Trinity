"""Tests for local context memory command helpers."""

import os

from trinity.config import TrinityConfig
from trinity.context.commands import (
    artifact_markdown,
    cleanup_oversized_backups,
    cleanup_oversized_backups_markdown,
    compact_memory_markdown,
    engine_from_config,
    memory_stats_markdown,
    memory_stats_rows,
    parse_oversized_cleanup_options,
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


def test_artifact_markdown_uses_korean_labels(tmp_path):
    config = TrinityConfig.default_config(project_dir=tmp_path)
    engine = engine_from_config(config)
    engine.initialize("Build app", ["codex"])
    engine.append_task_result(
        package_id="WP-001",
        agent="codex",
        status="done",
        summary="Implemented endpoint.",
    )

    record_id = engine.memory_store.recent(limit=1)[0].id if engine.memory_store else ""
    artifact = artifact_markdown(engine, record_id, lang="ko")
    missing = artifact_markdown(engine, "missing-record", lang="ko")

    assert "## 아티팩트" in artifact
    assert "- 종류:" in artifact
    assert "- 작업 패키지:" in artifact
    assert "### 요약" in artifact
    assert "메모리 레코드를 찾을 수 없습니다: `missing-record`." == missing


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


def test_parse_oversized_cleanup_options_defaults_to_dry_run():
    apply, keep_latest, error = parse_oversized_cleanup_options(
        ["--oversized-backups"]
    )

    assert apply is False
    assert keep_latest == 1
    assert error is None


def test_parse_oversized_cleanup_options_accepts_apply_and_keep_latest():
    apply, keep_latest, error = parse_oversized_cleanup_options(
        ["--oversized-backups", "--apply", "--keep-latest", "2"]
    )

    assert apply is True
    assert keep_latest == 2
    assert error is None


def test_cleanup_oversized_backups_dry_run_keeps_files(tmp_path):
    config = TrinityConfig.default_config(project_dir=tmp_path)
    engine = engine_from_config(config)
    first, second, third = _write_oversized_backups(engine)

    body = cleanup_oversized_backups_markdown(
        engine,
        apply=False,
        keep_latest=1,
    )

    assert "Memory Cleanup" in body
    assert "- mode: dry-run" in body
    assert "- backups_found: 3" in body
    assert "- cleanup_candidates: 2" in body
    assert "- deleted: 0" in body
    assert first.exists()
    assert second.exists()
    assert third.exists()


def test_cleanup_oversized_backups_apply_deletes_candidates(tmp_path):
    config = TrinityConfig.default_config(project_dir=tmp_path)
    engine = engine_from_config(config)
    first, second, third = _write_oversized_backups(engine)

    result = cleanup_oversized_backups(
        engine,
        apply=True,
        keep_latest=1,
    )

    assert [entry.path for entry in result.retained] == [third]
    assert len(result.deleted) == 2
    assert not first.exists()
    assert not second.exists()
    assert third.exists()


def _write_oversized_backups(engine):
    engine.path.parent.mkdir(parents=True, exist_ok=True)
    backups = [
        engine.path.with_name(f"{engine.path.name}.oversized-20260613-000001"),
        engine.path.with_name(f"{engine.path.name}.oversized-20260613-000002"),
        engine.path.with_name(f"{engine.path.name}.oversized-20260613-000003"),
    ]
    for index, path in enumerate(backups, start=1):
        path.write_text("x" * index, encoding="utf-8")
        os.utime(path, (index, index))
    return tuple(backups)
