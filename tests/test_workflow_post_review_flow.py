"""Tests for workflow post-review flow module boundaries."""

from __future__ import annotations

from trinity.workflow.execution_review_flow import (
    WorkflowPostReviewFlow as LegacyWorkflowPostReviewFlow,
)
from trinity.workflow.models import PostReviewActionItem, PostReviewActionStatus
from trinity.workflow.post_review_flow import WorkflowPostReviewFlow
from trinity.workflow.post_review_assignment import (
    build_supplemental_work_package,
    owner_for_post_review_item,
    supplemental_objective,
)
from trinity.workflow.post_review_selection import (
    looks_like_post_review_selector,
    select_post_review_items,
)


def test_legacy_execution_review_flow_reexports_post_review_flow():
    assert LegacyWorkflowPostReviewFlow is WorkflowPostReviewFlow


def test_select_post_review_items_filters_selectable_items():
    items = [
        PostReviewActionItem(
            id="AI-001",
            source="final_review",
            kind="test",
            title="Critical fix",
            summary="Critical fix",
            severity="critical",
            status=PostReviewActionStatus.PROPOSED,
        ),
        PostReviewActionItem(
            id="AI-002",
            source="final_review",
            kind="test",
            title="High fix",
            summary="High fix",
            severity="high",
            status=PostReviewActionStatus.ACCEPTED,
        ),
        PostReviewActionItem(
            id="AI-003",
            source="final_review",
            kind="test",
            title="Queued fix",
            summary="Queued fix",
            severity="high",
            status=PostReviewActionStatus.QUEUED,
        ),
    ]

    assert select_post_review_items("high", items) == ["AI-001", "AI-002"]
    assert select_post_review_items("critical", items) == ["AI-001"]
    assert select_post_review_items("AI-003", items) == []
    assert select_post_review_items("AI-002", items) == ["AI-002"]
    assert select_post_review_items("all", items) == ["AI-001", "AI-002"]


def test_looks_like_post_review_selector_distinguishes_free_text():
    assert looks_like_post_review_selector("")
    assert looks_like_post_review_selector("high AI-001")
    assert looks_like_post_review_selector("전체")
    assert not looks_like_post_review_selector("add another regression test")


def test_owner_for_post_review_item_prefers_suggested_and_related_owner():
    item = PostReviewActionItem(
        id="AI-010",
        source="wp_review",
        kind="bugfix",
        severity="high",
        title="Fix review",
        summary="Fix review",
        related_wp_ids=["WP-001"],
        suggested_owner="claude",
    )

    assert (
        owner_for_post_review_item(
            item,
            ["codex", "claude"],
            0,
            lambda package_id: "codex" if package_id == "WP-001" else "",
        )
        == "claude"
    )

    item.suggested_owner = "missing"
    assert (
        owner_for_post_review_item(
            item,
            ["codex", "claude"],
            0,
            lambda package_id: "codex" if package_id == "WP-001" else "",
        )
        == "codex"
    )


def test_owner_for_post_review_item_falls_back_to_agents_and_codex():
    item = PostReviewActionItem(
        id="AI-011",
        source="final_review",
        kind="validation",
        severity="medium",
        title="Validate",
        summary="Validate",
        suggested_owner="claude",
    )

    assert owner_for_post_review_item(item, ["codex", "agy"], 3, lambda _: "") == "agy"
    assert owner_for_post_review_item(item, [], 0, lambda _: "") == "claude"

    item.suggested_owner = ""
    assert owner_for_post_review_item(item, [], 0, lambda _: "") == "codex"


def test_build_supplemental_work_package_maps_action_item_fields():
    item = PostReviewActionItem(
        id="AI-020",
        source="final_review",
        kind="bugfix",
        severity="high",
        title="Fix regression",
        summary="Add regression coverage.",
        rationale="Reviewer requested tests.",
        related_wp_ids=["WP-001"],
    )

    package = build_supplemental_work_package(
        item,
        package_id="WP-S003",
        owner="codex",
        related_package_ids=["WP-001"],
        supplemental_round=2,
    )

    assert package.id == "WP-S003"
    assert package.title == "Fix regression"
    assert package.owner_agent == "codex"
    assert package.objective == supplemental_objective(item)
    assert package.scope == ["Add regression coverage."]
    assert package.dependencies == ["WP-001"]
    assert package.acceptance_criteria == ["Add regression coverage."]
    assert package.risk == "high"
    assert package.origin == "post_review_followup"
    assert package.origin_action_item_ids == ["AI-020"]
    assert package.parent_package_ids == ["WP-001"]
    assert package.supplemental_round == 2
