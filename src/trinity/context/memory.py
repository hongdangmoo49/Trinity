"""Workflow memory index for bounded shared context projections."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class MemoryRecord:
    """A compact, indexed reference to a Trinity workflow artifact or result."""

    id: str
    kind: str
    source: str
    title: str
    summary: str
    workflow_id: str = ""
    trinity_session_id: str = ""
    provider_session_id: str = ""
    agent: str = ""
    provider: str = ""
    model: str = ""
    round_num: int | None = None
    work_package_id: str = ""
    review_package_id: str = ""
    artifact_path: str = ""
    compressed_path: str = ""
    content_hash: str = ""
    token_estimate: int = 0
    importance: int = 0
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def normalized(self) -> "MemoryRecord":
        content_hash = self.content_hash or MemoryStore.hash_text(
            "\n".join(
                (
                    self.kind,
                    self.source,
                    self.title,
                    self.summary,
                    self.artifact_path,
                )
            )
        )
        token_estimate = self.token_estimate or ContentRouter.estimate_tokens(
            self.summary
        )
        return MemoryRecord(
            id=self.id,
            kind=self.kind,
            source=self.source,
            title=self.title,
            summary=self.summary,
            workflow_id=self.workflow_id,
            trinity_session_id=self.trinity_session_id,
            provider_session_id=self.provider_session_id,
            agent=self.agent,
            provider=self.provider,
            model=self.model,
            round_num=self.round_num,
            work_package_id=self.work_package_id,
            review_package_id=self.review_package_id,
            artifact_path=self.artifact_path,
            compressed_path=self.compressed_path,
            content_hash=content_hash,
            token_estimate=token_estimate,
            importance=self.importance,
            tags=list(self.tags),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class MemoryStats:
    """Aggregate memory index health for UI and diagnostics."""

    record_count: int
    artifact_count: int
    total_token_estimate: int
    latest_updated_at: float


class ContentRouter:
    """Small deterministic content summarizer used before prompt packing."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, int(len(text) / 4))

    @staticmethod
    def summarize(content: str, *, max_chars: int = 1200) -> str:
        text = content.strip()
        if not text:
            return ""

        pretty_json = ContentRouter.try_pretty_json(text)
        if pretty_json is not None:
            text = pretty_json

        if len(text) <= max_chars:
            return text
        head = max_chars // 2
        tail = max_chars - head - 32
        return (
            text[:head].rstrip()
            + "\n...[truncated for memory]...\n"
            + text[-tail:].lstrip()
        )

    @staticmethod
    def try_pretty_json(content: str) -> str | None:
        text = content.strip()
        if not (
            (text.startswith("{") and text.endswith("}"))
            or (text.startswith("[") and text.endswith("]"))
        ):
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return json.dumps(parsed, ensure_ascii=False, indent=2, sort_keys=True)


class MemoryStore:
    """SQLite-backed index for compact workflow memory records."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    def upsert(self, record: MemoryRecord) -> MemoryRecord:
        item = record.normalized()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_records (
                    id, kind, source, workflow_id, trinity_session_id,
                    provider_session_id, agent, provider, model, round_num,
                    work_package_id, review_package_id, title, summary,
                    artifact_path, compressed_path, content_hash, token_estimate,
                    importance, tags_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    kind=excluded.kind,
                    source=excluded.source,
                    workflow_id=excluded.workflow_id,
                    trinity_session_id=excluded.trinity_session_id,
                    provider_session_id=excluded.provider_session_id,
                    agent=excluded.agent,
                    provider=excluded.provider,
                    model=excluded.model,
                    round_num=excluded.round_num,
                    work_package_id=excluded.work_package_id,
                    review_package_id=excluded.review_package_id,
                    title=excluded.title,
                    summary=excluded.summary,
                    artifact_path=excluded.artifact_path,
                    compressed_path=excluded.compressed_path,
                    content_hash=excluded.content_hash,
                    token_estimate=excluded.token_estimate,
                    importance=excluded.importance,
                    tags_json=excluded.tags_json,
                    updated_at=excluded.updated_at
                """,
                self._record_values(item),
            )
        return item

    def recent(
        self,
        *,
        limit: int = 20,
        kind: str = "",
        workflow_id: str = "",
    ) -> list[MemoryRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if workflow_id:
            clauses.append("workflow_id = ?")
            params.append(workflow_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM memory_records
                {where}
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, record_id: str) -> MemoryRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memory_records WHERE id = ?",
                (record_id,),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def stats(self) -> MemoryStats:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS record_count,
                    SUM(CASE WHEN artifact_path != '' THEN 1 ELSE 0 END) AS artifact_count,
                    COALESCE(SUM(token_estimate), 0) AS total_token_estimate,
                    COALESCE(MAX(updated_at), 0) AS latest_updated_at
                FROM memory_records
                """
            ).fetchone()
        return MemoryStats(
            record_count=int(row["record_count"] or 0),
            artifact_count=int(row["artifact_count"] or 0),
            total_token_estimate=int(row["total_token_estimate"] or 0),
            latest_updated_at=float(row["latest_updated_at"] or 0),
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_records (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    source TEXT NOT NULL,
                    workflow_id TEXT NOT NULL DEFAULT '',
                    trinity_session_id TEXT NOT NULL DEFAULT '',
                    provider_session_id TEXT NOT NULL DEFAULT '',
                    agent TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    round_num INTEGER,
                    work_package_id TEXT NOT NULL DEFAULT '',
                    review_package_id TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    artifact_path TEXT NOT NULL DEFAULT '',
                    compressed_path TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    token_estimate INTEGER NOT NULL DEFAULT 0,
                    importance INTEGER NOT NULL DEFAULT 0,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_records_lookup
                ON memory_records (workflow_id, kind, work_package_id, updated_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_records_content_hash
                ON memory_records (content_hash)
                """
            )

    def _record_values(self, record: MemoryRecord) -> tuple[Any, ...]:
        return (
            record.id,
            record.kind,
            record.source,
            record.workflow_id,
            record.trinity_session_id,
            record.provider_session_id,
            record.agent,
            record.provider,
            record.model,
            record.round_num,
            record.work_package_id,
            record.review_package_id,
            record.title,
            record.summary,
            record.artifact_path,
            record.compressed_path,
            record.content_hash,
            record.token_estimate,
            record.importance,
            json.dumps(list(record.tags), ensure_ascii=False),
            record.created_at,
            record.updated_at,
        )

    def _from_row(self, row: sqlite3.Row) -> MemoryRecord:
        try:
            tags = json.loads(str(row["tags_json"] or "[]"))
        except json.JSONDecodeError:
            tags = []
        if not isinstance(tags, list):
            tags = []
        return MemoryRecord(
            id=str(row["id"]),
            kind=str(row["kind"]),
            source=str(row["source"]),
            workflow_id=str(row["workflow_id"]),
            trinity_session_id=str(row["trinity_session_id"]),
            provider_session_id=str(row["provider_session_id"]),
            agent=str(row["agent"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            round_num=(
                int(row["round_num"]) if row["round_num"] is not None else None
            ),
            work_package_id=str(row["work_package_id"]),
            review_package_id=str(row["review_package_id"]),
            title=str(row["title"]),
            summary=str(row["summary"]),
            artifact_path=str(row["artifact_path"]),
            compressed_path=str(row["compressed_path"]),
            content_hash=str(row["content_hash"]),
            token_estimate=int(row["token_estimate"]),
            importance=int(row["importance"]),
            tags=[str(item) for item in tags],
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
        )


def summarize_lines(items: Iterable[str], *, max_items: int = 8) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return ""
    shown = values[:max_items]
    suffix = f"\n... {len(values) - max_items} more" if len(values) > max_items else ""
    return "\n".join(f"- {item}" for item in shown) + suffix
