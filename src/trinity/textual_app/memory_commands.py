"""Pure helpers for Textual memory command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.context.commands import (
    cleanup_oversized_backups_markdown,
    compact_memory_markdown,
    memory_stats_markdown,
    memory_stats_rows,
    parse_oversized_cleanup_options,
)
from trinity.context.shared import SharedContextEngine
from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.command_parsers import parse_memory_args


MemorySeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class MemoryCommandPresentation:
    """Prepared local command result for `/memory`."""

    title: str
    body: str
    severity: MemorySeverity = "info"
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


def memory_command_presentation(
    engine: SharedContextEngine,
    args: list[str],
    *,
    target_bytes: int,
    recent_records: int,
    lang: str = "en",
) -> MemoryCommandPresentation:
    """Return the presentation payload for a Textual `/memory` command."""
    parsed = parse_memory_args(args)
    if parsed.action == "compact":
        return MemoryCommandPresentation(
            title=textual_presenters.memory_title("compact", lang=lang),
            body=compact_memory_markdown(
                engine,
                target_bytes=target_bytes,
                recent_records=recent_records,
            ),
            table_columns=textual_presenters.status_table_columns(lang=lang),
            table_rows=memory_stats_rows(engine),
        )

    if parsed.action == "cleanup":
        apply, keep_latest, error = parse_oversized_cleanup_options(
            list(parsed.action_args)
        )
        title = textual_presenters.memory_title("cleanup", lang=lang)
        if error:
            return MemoryCommandPresentation(
                title=title,
                body=textual_presenters.memory_cleanup_error_markdown(
                    error,
                    lang=lang,
                ),
                severity="warning",
            )
        return MemoryCommandPresentation(
            title=title,
            body=cleanup_oversized_backups_markdown(
                engine,
                apply=apply,
                keep_latest=keep_latest,
            ),
            table_columns=textual_presenters.status_table_columns(lang=lang),
        )

    return MemoryCommandPresentation(
        title=textual_presenters.memory_title("stats", lang=lang),
        body=memory_stats_markdown(engine),
        table_columns=textual_presenters.status_table_columns(lang=lang),
        table_rows=memory_stats_rows(engine),
    )
