"""Tests for budgeted context packing."""

from trinity.context.memory import MemoryRecord, MemoryStore
from trinity.context.packing import ContextPacker


def test_context_packer_includes_pinned_sections_and_memory(tmp_path):
    store = MemoryStore(tmp_path / "memory" / "index.sqlite")
    store.upsert(
        MemoryRecord(
            id="execution_result-WP-001-abc",
            kind="execution_result",
            source="test",
            title="WP-001 / codex",
            summary="Implemented endpoint.",
            agent="codex",
            work_package_id="WP-001",
        )
    )

    packed = ContextPacker(store, prompt_budget_tokens=1000).pack(
        pinned_sections={"Current Goal": "Build app"}
    )

    assert "## Current Goal" in packed.text
    assert "Build app" in packed.text
    assert "WP-001 / codex" in packed.text
    assert packed.estimated_tokens > 0
    assert packed.records
    assert not packed.truncated


def test_context_packer_respects_budget(tmp_path):
    store = MemoryStore(tmp_path / "memory" / "index.sqlite")
    store.upsert(
        MemoryRecord(
            id="huge",
            kind="execution_result",
            source="test",
            title="huge",
            summary="x" * 2000,
        )
    )

    packed = ContextPacker(store, prompt_budget_tokens=10).pack()

    assert packed.text == ""
    assert packed.records == []
    assert packed.truncated
