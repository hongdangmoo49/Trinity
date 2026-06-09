"""Shared render helpers for local context memory commands."""

from __future__ import annotations

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine


def engine_from_config(config: TrinityConfig) -> SharedContextEngine:
    return SharedContextEngine(
        path=config.shared_context_path,
        keep_sections=config.keep_sections,
        max_read_bytes=config.shared_max_bytes,
        section_entry_max_chars=config.shared_section_entry_max_chars,
        memory_index_enabled=config.memory_index_enabled,
    )


def memory_stats_markdown(engine: SharedContextEngine) -> str:
    stats = engine.memory_stats()
    shared_size = engine.path.stat().st_size if engine.path.exists() else 0
    if stats is None:
        return (
            "Memory index is disabled.\n\n"
            f"- shared_path: `{engine.path}`\n"
            f"- shared_size_bytes: {shared_size}"
        )
    return "\n".join(
        (
            "## Memory Stats",
            f"- shared_path: `{engine.path}`",
            f"- shared_size_bytes: {shared_size}",
            f"- max_read_bytes: {engine.max_read_bytes}",
            f"- records: {stats.record_count}",
            f"- artifacts: {stats.artifact_count}",
            f"- estimated_tokens: {stats.total_token_estimate}",
            f"- latest_updated_at: {stats.latest_updated_at:.3f}",
        )
    )


def memory_stats_rows(engine: SharedContextEngine) -> tuple[tuple[str, str], ...]:
    stats = engine.memory_stats()
    shared_size = engine.path.stat().st_size if engine.path.exists() else 0
    rows = [
        ("Shared path", str(engine.path)),
        ("Shared size bytes", str(shared_size)),
        ("Max read bytes", str(engine.max_read_bytes)),
    ]
    if stats is None:
        rows.append(("Memory index", "disabled"))
    else:
        rows.extend(
            [
                ("Records", str(stats.record_count)),
                ("Artifacts", str(stats.artifact_count)),
                ("Estimated tokens", str(stats.total_token_estimate)),
                ("Latest updated at", f"{stats.latest_updated_at:.3f}"),
            ]
        )
    return tuple(rows)


def compact_memory_markdown(
    engine: SharedContextEngine,
    *,
    target_bytes: int,
    recent_records: int,
) -> str:
    backup = engine.compact_projection_from_memory(
        target_bytes=target_bytes,
        recent_records=recent_records,
    )
    lines = [
        "## Memory Compact",
        f"- shared_path: `{engine.path}`",
        f"- target_bytes: {target_bytes}",
        f"- recent_records: {recent_records}",
    ]
    if backup is not None:
        lines.append(f"- oversized_backup: `{backup}`")
    lines.append(f"- shared_size_bytes: {engine.path.stat().st_size if engine.path.exists() else 0}")
    return "\n".join(lines)


def artifact_markdown(engine: SharedContextEngine, record_id: str) -> str:
    if engine.memory_store is None:
        return "Memory index is disabled."
    record = engine.memory_store.get(record_id)
    if record is None:
        return f"No memory record found for `{record_id}`."
    lines = [
        f"## Artifact {record.id}",
        f"- kind: {record.kind}",
        f"- title: {record.title}",
        f"- agent: {record.agent or '(unknown)'}",
        f"- work_package: `{record.work_package_id or '(none)'}`",
        f"- artifact_path: `{record.artifact_path or '(none)'}`",
        f"- compressed_path: `{record.compressed_path or '(none)'}`",
        f"- estimated_tokens: {record.token_estimate}",
        "",
        "### Summary",
        record.summary or "(none)",
    ]
    return "\n".join(lines)
