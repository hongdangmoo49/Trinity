"""Post-review supplemental work assignment helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from trinity.workflow.models import PostReviewActionItem

RelatedOwnerLookup = Callable[[str], str]


def owner_for_post_review_item(
    item: PostReviewActionItem,
    active_agents: Sequence[str],
    index: int,
    related_owner: RelatedOwnerLookup,
) -> str:
    """Choose the owner agent for a supplemental post-review work package."""
    agents = [agent for agent in active_agents if agent]
    if item.suggested_owner and (not agents or item.suggested_owner in agents):
        return item.suggested_owner
    for package_id in item.related_wp_ids:
        owner = related_owner(package_id)
        if owner and (not agents or owner in agents):
            return owner
    if agents:
        return agents[index % len(agents)]
    return item.suggested_owner or "codex"
