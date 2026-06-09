"""Budgeted prompt context packing over shared projection + memory index."""

from __future__ import annotations

from dataclasses import dataclass, field

from trinity.context.memory import ContentRouter, MemoryRecord, MemoryStore


@dataclass(frozen=True)
class PackedContext:
    """A prompt-ready context bundle with budget metadata."""

    text: str
    estimated_tokens: int
    records: list[MemoryRecord] = field(default_factory=list)
    truncated: bool = False


class ContextPacker:
    """Assemble bounded context from pinned sections and recent memory records."""

    def __init__(
        self,
        memory_store: MemoryStore | None,
        *,
        prompt_budget_tokens: int = 24_000,
        recent_records: int = 30,
    ):
        self.memory_store = memory_store
        self.prompt_budget_tokens = prompt_budget_tokens
        self.recent_records = recent_records

    def pack(
        self,
        *,
        pinned_sections: dict[str, str] | None = None,
        workflow_id: str = "",
        kind: str = "",
    ) -> PackedContext:
        parts: list[str] = []
        records: list[MemoryRecord] = []
        used = 0
        truncated = False

        for heading, body in (pinned_sections or {}).items():
            clean = body.strip()
            if not clean:
                continue
            block = f"## {heading}\n{clean}"
            cost = ContentRouter.estimate_tokens(block)
            if not self._fits(used, cost):
                truncated = True
                continue
            parts.append(block)
            used += cost

        if self.memory_store is not None:
            for record in self.memory_store.recent(
                limit=self.recent_records,
                kind=kind,
                workflow_id=workflow_id,
            ):
                block = self._record_block(record)
                cost = ContentRouter.estimate_tokens(block)
                if not self._fits(used, cost):
                    truncated = True
                    continue
                parts.append(block)
                records.append(record)
                used += cost

        return PackedContext(
            text="\n\n".join(parts).strip(),
            estimated_tokens=used,
            records=records,
            truncated=truncated,
        )

    def _fits(self, used: int, cost: int) -> bool:
        return self.prompt_budget_tokens <= 0 or used + cost <= self.prompt_budget_tokens

    @staticmethod
    def _record_block(record: MemoryRecord) -> str:
        lines = [
            f"## Memory: {record.title or record.id}",
            f"- id: `{record.id}`",
            f"- kind: {record.kind}",
        ]
        if record.agent:
            lines.append(f"- agent: {record.agent}")
        if record.work_package_id:
            lines.append(f"- work_package: `{record.work_package_id}`")
        if record.artifact_path:
            lines.append(f"- artifact_path: `{record.artifact_path}`")
        if record.summary:
            lines.extend(["", record.summary])
        return "\n".join(lines)
