"""Post-review action item selection helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from trinity.workflow.models import PostReviewActionItem, PostReviewActionStatus

_SELECTOR_WORDS = {
    "all",
    "*",
    "전체",
    "critical",
    "긴급",
    "high",
    "높음",
    "important",
    "중요",
}


def select_post_review_items(
    instruction: str,
    items: Iterable[PostReviewActionItem],
) -> list[str]:
    """Return action item ids selected by a post-review instruction."""
    tokens = _post_review_selector_tokens(instruction)
    if not tokens:
        return []
    selectable = [
        item
        for item in items
        if item.status
        in {PostReviewActionStatus.PROPOSED, PostReviewActionStatus.ACCEPTED}
    ]
    normalized_tokens = [token.lower() for token in tokens]
    if any(token in {"all", "*", "전체"} for token in normalized_tokens):
        return [item.id for item in selectable]
    if any(token in {"critical", "긴급"} for token in normalized_tokens):
        return [item.id for item in selectable if item.severity == "critical"]
    if any(token in {"high", "높음", "important", "중요"} for token in normalized_tokens):
        return [
            item.id
            for item in selectable
            if item.severity in {"critical", "high"}
        ]
    requested = {token.upper() for token in tokens}
    return [item.id for item in selectable if item.id.upper() in requested]


def looks_like_post_review_selector(instruction: str) -> bool:
    """Return whether an instruction appears to be an item selector."""
    tokens = [token.lower() for token in _post_review_selector_tokens(instruction)]
    if not tokens:
        return True
    return all(token in _SELECTOR_WORDS or re.fullmatch(r"ai-\d+", token) for token in tokens)


def _post_review_selector_tokens(instruction: str) -> list[str]:
    return [token for token in re.split(r"[\s,]+", instruction.strip()) if token]
