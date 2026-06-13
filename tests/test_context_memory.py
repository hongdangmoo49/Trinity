"""Tests for Trinity context memory index."""

from trinity.context.memory import ContentRouter, MemoryRecord, MemoryStore
from trinity.context.shared import SharedContextEngine


def test_memory_store_upsert_and_recent(tmp_path):
    store = MemoryStore(tmp_path / "memory" / "index.sqlite")
    record = MemoryRecord(
        id="execution_result-WP-001-abc",
        kind="execution_result",
        source="test",
        title="WP-001 / codex",
        summary="Implemented endpoint.",
        agent="codex",
        work_package_id="WP-001",
        artifact_path="/tmp/raw.txt",
        tags=["execution", "done"],
    )

    stored = store.upsert(record)
    records = store.recent(limit=5)
    stats = store.stats()

    assert stored.content_hash
    assert stored.token_estimate > 0
    assert len(records) == 1
    assert records[0].id == "execution_result-WP-001-abc"
    assert records[0].tags == ["execution", "done"]
    assert stats.record_count == 1
    assert stats.artifact_count == 1


def test_content_router_pretty_formats_json():
    summary = ContentRouter.summarize('{"b":2,"a":{"x":1}}')

    assert '{\n  "a": {' in summary
    assert '"b": 2' in summary


def test_content_router_bounds_long_text():
    summary = ContentRouter.summarize("x" * 3000, max_chars=200)

    assert len(summary) < 3000
    assert "[truncated for memory]" in summary


def test_shared_context_pack_context_reuses_cache_until_inputs_change(tmp_path, monkeypatch):
    engine = SharedContextEngine(tmp_path / "shared.md")
    engine.initialize("Build UI", ["codex"])
    engine.memory_store.upsert(
        MemoryRecord(
            id="record-1",
            kind="execution_result",
            source="test",
            title="WP-001",
            summary="Implemented shell.",
            workflow_id="wf-cache",
        )
    )
    parse_calls = 0
    recent_calls = 0
    original_parse = engine._parse_sections
    original_recent = engine.memory_store.recent

    def counted_parse(content: str):
        nonlocal parse_calls
        parse_calls += 1
        return original_parse(content)

    def counted_recent(*args, **kwargs):
        nonlocal recent_calls
        recent_calls += 1
        return original_recent(*args, **kwargs)

    monkeypatch.setattr(engine, "_parse_sections", counted_parse)
    monkeypatch.setattr(engine.memory_store, "recent", counted_recent)

    first = engine.pack_context_for_prompt(workflow_id="wf-cache")
    second = engine.pack_context_for_prompt(workflow_id="wf-cache")

    assert second is first
    assert parse_calls == 1
    assert recent_calls == 1

    engine.memory_store.upsert(
        MemoryRecord(
            id="record-2",
            kind="execution_result",
            source="test",
            title="WP-002",
            summary="Added tests.",
            workflow_id="wf-cache",
        )
    )
    third = engine.pack_context_for_prompt(workflow_id="wf-cache")

    assert third is not first
    assert parse_calls == 2
    assert recent_calls == 2

    engine.write_section("Agreed Conclusion", "Use compact UI.")
    fourth = engine.pack_context_for_prompt(workflow_id="wf-cache")

    assert fourth is not third
    assert parse_calls == 4
    assert recent_calls == 3
