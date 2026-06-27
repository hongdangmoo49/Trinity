"""Review repair event metadata projection helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReviewRepairEventMetadata:
    """Repair metadata reconstructed from persisted workflow events."""

    attempt_count: int = 0
    repair_signature: str = ""
    review_package_id: str = ""


def review_repair_metadata_from_events(
    events: Iterable[Mapping[str, Any]],
) -> dict[str, ReviewRepairEventMetadata]:
    """Collapse repair-request events into package-level metadata."""
    metadata_by_package: dict[str, dict[str, Any]] = {}
    for event in events:
        data = event.get("data", {})
        if not isinstance(data, Mapping):
            continue
        package_id = str(data.get("package_id", "")).strip()
        if not package_id:
            continue
        metadata = metadata_by_package.setdefault(
            package_id,
            {
                "attempt_count": 0,
                "repair_signature": "",
                "review_package_id": "",
            },
        )
        next_count = int(metadata["attempt_count"]) + 1
        try:
            event_count = int(data.get("repair_attempt_count", 0) or 0)
        except (TypeError, ValueError):
            event_count = 0
        metadata["attempt_count"] = max(next_count, event_count)
        repair_signature = str(data.get("repair_signature", "") or "")
        if repair_signature:
            metadata["repair_signature"] = repair_signature
        review_package_id = str(data.get("review_package_id", "") or "")
        if not review_package_id:
            review_package_ids = data.get("review_package_ids", [])
            if isinstance(review_package_ids, list) and review_package_ids:
                review_package_id = str(review_package_ids[-1])
        if review_package_id:
            metadata["review_package_id"] = review_package_id
    return {
        package_id: ReviewRepairEventMetadata(
            attempt_count=int(metadata["attempt_count"]),
            repair_signature=str(metadata["repair_signature"]),
            review_package_id=str(metadata["review_package_id"]),
        )
        for package_id, metadata in metadata_by_package.items()
    }
