"""Post-review supplemental work assignment helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from trinity.workflow.models import PostReviewActionItem, WorkPackage, WorkStatus

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


def build_supplemental_work_package(
    item: PostReviewActionItem,
    *,
    package_id: str,
    owner: str,
    related_package_ids: Sequence[str],
    supplemental_round: int,
) -> WorkPackage:
    """Build a supplemental work package for a post-review action item."""
    related = list(related_package_ids)
    return WorkPackage(
        id=package_id,
        title=item.title or f"Post-review follow-up {item.id}",
        owner_agent=owner,
        objective=supplemental_objective(item),
        scope=[item.summary] if item.summary else [],
        dependencies=related,
        acceptance_criteria=[
            item.summary or item.title or f"Complete action item {item.id}."
        ],
        status=WorkStatus.PENDING,
        requires_execution=True,
        risk=item.severity or "medium",
        origin="post_review_followup",
        origin_action_item_ids=[item.id],
        parent_package_ids=related,
        supplemental_round=supplemental_round,
    )


def supplemental_objective(item: PostReviewActionItem) -> str:
    """Return the objective text for a supplemental work package."""
    parts = [
        f"Post-review action item {item.id}: {item.summary}",
        f"Source: {item.source}",
        f"Kind: {item.kind}",
        f"Severity: {item.severity}",
    ]
    if item.rationale:
        parts.append(f"Rationale: {item.rationale}")
    if item.related_wp_ids:
        parts.append(f"Related work packages: {', '.join(item.related_wp_ids)}")
    return "\n".join(parts)
