"""Shared render helpers for local context memory commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine


ARTIFACT_LABELS = {
    "en": {
        "agent": "agent",
        "artifact": "Artifact",
        "artifact_path": "artifact_path",
        "compressed_path": "compressed_path",
        "estimated_tokens": "estimated_tokens",
        "kind": "kind",
        "memory_disabled": "Memory index is disabled.",
        "none": "(none)",
        "not_found": "No memory record found for",
        "summary": "Summary",
        "title": "title",
        "unknown": "(unknown)",
        "work_package": "work_package",
    },
    "ko": {
        "agent": "에이전트",
        "artifact": "아티팩트",
        "artifact_path": "아티팩트 경로",
        "compressed_path": "압축 경로",
        "estimated_tokens": "예상 토큰",
        "kind": "종류",
        "memory_disabled": "메모리 인덱스가 비활성화되어 있습니다.",
        "none": "(없음)",
        "not_found": "메모리 레코드를 찾을 수 없습니다",
        "summary": "요약",
        "title": "제목",
        "unknown": "(알 수 없음)",
        "work_package": "작업 패키지",
    },
}


def _artifact_label(lang: str, key: str) -> str:
    labels = ARTIFACT_LABELS.get(lang, ARTIFACT_LABELS["en"])
    return labels.get(key, ARTIFACT_LABELS["en"].get(key, key))


@dataclass(frozen=True)
class OversizedBackupEntry:
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class OversizedBackupCleanupResult:
    shared_path: Path
    backup_dir: Path
    apply: bool
    keep_latest: int
    retained: tuple[OversizedBackupEntry, ...]
    candidates: tuple[OversizedBackupEntry, ...]
    deleted: tuple[OversizedBackupEntry, ...]
    skipped: tuple[tuple[Path, str], ...]

    @property
    def found_count(self) -> int:
        return len(self.retained) + len(self.candidates)

    @property
    def candidate_bytes(self) -> int:
        return sum(entry.size_bytes for entry in self.candidates)

    @property
    def deleted_bytes(self) -> int:
        return sum(entry.size_bytes for entry in self.deleted)


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


def parse_oversized_cleanup_options(args: list[str]) -> tuple[bool, int, str | None]:
    apply = False
    keep_latest = 1
    saw_target = False
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--oversized-backups":
            saw_target = True
        elif token == "--apply":
            apply = True
        elif token == "--dry-run":
            apply = False
        elif token == "--keep-latest":
            index += 1
            if index >= len(args):
                return apply, keep_latest, "--keep-latest requires a number."
            try:
                keep_latest = int(args[index])
            except ValueError:
                return apply, keep_latest, "--keep-latest requires a number."
        elif token.startswith("--keep-latest="):
            try:
                keep_latest = int(token.split("=", 1)[1])
            except ValueError:
                return apply, keep_latest, "--keep-latest requires a number."
        else:
            return apply, keep_latest, f"Unknown cleanup option: `{token}`"
        index += 1

    if not saw_target:
        return (
            apply,
            keep_latest,
            "Usage: `/memory cleanup --oversized-backups [--apply] [--keep-latest N]`",
        )
    if keep_latest < 0:
        return apply, keep_latest, "--keep-latest must be 0 or greater."
    return apply, keep_latest, None


def cleanup_oversized_backups(
    engine: SharedContextEngine,
    *,
    apply: bool = False,
    keep_latest: int = 1,
) -> OversizedBackupCleanupResult:
    backup_dir = engine.path.parent
    backup_dir_resolved = backup_dir.resolve()
    keep_latest = max(0, keep_latest)
    entries: list[tuple[int, str, OversizedBackupEntry]] = []
    skipped: list[tuple[Path, str]] = []

    for path in backup_dir.glob(f"{engine.path.name}.oversized-*"):
        if path.is_symlink():
            skipped.append((path, "symlink"))
            continue
        try:
            resolved = path.resolve()
        except OSError as exc:
            skipped.append((path, f"resolve failed: {exc}"))
            continue
        if resolved.parent != backup_dir_resolved:
            skipped.append((path, "outside shared context directory"))
            continue
        try:
            stat = path.stat()
        except OSError as exc:
            skipped.append((path, f"stat failed: {exc}"))
            continue
        if not path.is_file():
            skipped.append((path, "not a file"))
            continue
        entries.append(
            (
                stat.st_mtime_ns,
                path.name,
                OversizedBackupEntry(path=path, size_bytes=stat.st_size),
            )
        )

    sorted_entries = tuple(
        entry
        for _, _, entry in sorted(
            entries,
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )
    )
    retained = sorted_entries[:keep_latest]
    candidates = sorted_entries[keep_latest:]
    deleted: list[OversizedBackupEntry] = []
    if apply:
        for entry in candidates:
            try:
                entry.path.unlink()
            except OSError as exc:
                skipped.append((entry.path, f"delete failed: {exc}"))
                continue
            deleted.append(entry)

    return OversizedBackupCleanupResult(
        shared_path=engine.path,
        backup_dir=backup_dir,
        apply=apply,
        keep_latest=keep_latest,
        retained=retained,
        candidates=candidates,
        deleted=tuple(deleted),
        skipped=tuple(skipped),
    )


def cleanup_oversized_backups_markdown(
    engine: SharedContextEngine,
    *,
    apply: bool = False,
    keep_latest: int = 1,
) -> str:
    result = cleanup_oversized_backups(
        engine,
        apply=apply,
        keep_latest=keep_latest,
    )
    mode = "apply" if apply else "dry-run"
    lines = [
        "## Memory Cleanup",
        "- target: oversized shared context backups",
        f"- mode: {mode}",
        f"- shared_path: `{result.shared_path}`",
        f"- backup_dir: `{result.backup_dir}`",
        f"- keep_latest: {result.keep_latest}",
        f"- backups_found: {result.found_count}",
        f"- cleanup_candidates: {len(result.candidates)}",
        f"- cleanup_candidate_bytes: {result.candidate_bytes}",
        f"- deleted: {len(result.deleted)}",
        f"- deleted_bytes: {result.deleted_bytes}",
    ]
    if not apply and result.candidates:
        lines.append(
            "- next_step: rerun `/memory cleanup --oversized-backups --apply` to delete candidates."
        )
    elif not result.candidates:
        lines.append("- next_step: no oversized backup cleanup is needed.")

    lines.extend(_backup_entries_markdown("Retained", result.retained))
    lines.extend(_backup_entries_markdown("Cleanup Candidates", result.candidates))
    if result.skipped:
        lines.extend(["", "### Skipped"])
        for path, reason in result.skipped[:20]:
            lines.append(f"- `{path}` ({reason})")
        if len(result.skipped) > 20:
            lines.append(f"- ... {len(result.skipped) - 20} more")
    return "\n".join(lines)


def artifact_markdown(
    engine: SharedContextEngine,
    record_id: str,
    *,
    lang: str = "en",
) -> str:
    if engine.memory_store is None:
        return _artifact_label(lang, "memory_disabled")
    record = engine.memory_store.get(record_id)
    if record is None:
        if lang != "ko":
            return f"No memory record found for `{record_id}`."
        return f"{_artifact_label(lang, 'not_found')}: `{record_id}`."
    lines = [
        f"## {_artifact_label(lang, 'artifact')} {record.id}",
        f"- {_artifact_label(lang, 'kind')}: {record.kind}",
        f"- {_artifact_label(lang, 'title')}: {record.title}",
        f"- {_artifact_label(lang, 'agent')}: {record.agent or _artifact_label(lang, 'unknown')}",
        (
            f"- {_artifact_label(lang, 'work_package')}: "
            f"`{record.work_package_id or _artifact_label(lang, 'none')}`"
        ),
        (
            f"- {_artifact_label(lang, 'artifact_path')}: "
            f"`{record.artifact_path or _artifact_label(lang, 'none')}`"
        ),
        (
            f"- {_artifact_label(lang, 'compressed_path')}: "
            f"`{record.compressed_path or _artifact_label(lang, 'none')}`"
        ),
        f"- {_artifact_label(lang, 'estimated_tokens')}: {record.token_estimate}",
        "",
        f"### {_artifact_label(lang, 'summary')}",
        record.summary or _artifact_label(lang, "none"),
    ]
    return "\n".join(lines)


def _backup_entries_markdown(
    title: str,
    entries: tuple[OversizedBackupEntry, ...],
) -> list[str]:
    if not entries:
        return []
    lines = ["", f"### {title}"]
    for entry in entries[:20]:
        lines.append(f"- `{entry.path}` ({entry.size_bytes} bytes)")
    if len(entries) > 20:
        lines.append(f"- ... {len(entries) - 20} more")
    return lines
