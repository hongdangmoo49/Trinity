"""Tests for Trinity context memory index."""

from trinity.context.memory import ContentRouter, MemoryRecord, MemoryStore


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
