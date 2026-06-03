"""Tests for workflow peer review planning."""

import pytest

from trinity.workflow.models import ExecutionResult, WorkPackage, WorkStatus
from trinity.workflow.review import (
    PeerReviewPlanner,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
)


def _package(
    package_id: str = "WP-001",
    owner_agent: str = "codex",
    acceptance_criteria: list[str] | None = None,
) -> WorkPackage:
    return WorkPackage(
        id=package_id,
        title=f"{owner_agent} package",
        owner_agent=owner_agent,
        objective="Implement a workflow slice.",
        acceptance_criteria=acceptance_criteria or [],
    )


def test_peer_review_planner_assigns_non_owner_reviewer_per_work_package():
    packages = [
        _package("WP-001", "claude", ["Tests pass"]),
        _package("WP-002", "codex"),
        _package("WP-003", "gemini"),
    ]

    reviews = PeerReviewPlanner().plan_reviews(
        packages,
        active_agents=["claude", "codex", "gemini"],
    )

    assert [review.package_id for review in reviews] == ["WP-001", "WP-002", "WP-003"]
    assert [review.target_agent for review in reviews] == ["claude", "codex", "gemini"]
    assert all(review.reviewer_agent != review.target_agent for review in reviews)
    assert all(review.self_review is False for review in reviews)
    assert "Tests pass" in reviews[0].criteria


def test_peer_review_planner_uses_self_review_for_single_active_agent():
    reviews = PeerReviewPlanner().plan_reviews(
        [_package("WP-001", "codex")],
        active_agents=["codex"],
    )

    assert len(reviews) == 1
    review = reviews[0]
    assert review.package_id == "WP-001"
    assert review.reviewer_agent == "codex"
    assert review.target_agent == "codex"
    assert review.self_review is True


def test_peer_review_planner_uses_execution_result_target_and_status():
    package = _package("WP-001", "claude")
    result = ExecutionResult(
        package_id="WP-001",
        agent_name="codex",
        status=WorkStatus.DONE,
        summary="Implemented by delegated owner.",
    )

    reviews = PeerReviewPlanner().plan_reviews(
        [package],
        active_agents=["claude", "codex"],
        execution_results=[result],
    )

    review = reviews[0]
    assert review.target_agent == "codex"
    assert review.reviewer_agent == "claude"
    assert review.execution_status == WorkStatus.DONE


def test_peer_review_planner_requires_active_reviewer_for_packages():
    with pytest.raises(ValueError, match="active_agents"):
        PeerReviewPlanner().plan_reviews([_package()], active_agents=[])


def test_review_package_round_trips_to_dict():
    review = ReviewPackage(
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        criteria=["Verify tests"],
        execution_status=WorkStatus.DONE,
    )

    restored = ReviewPackage.from_dict(review.to_dict())

    assert restored.id == "RP-WP-001-claude"
    assert restored.package_id == "WP-001"
    assert restored.reviewer_agent == "claude"
    assert restored.target_agent == "codex"
    assert restored.criteria == ["Verify tests"]
    assert restored.self_review is False
    assert restored.execution_status == WorkStatus.DONE


def test_review_result_round_trips_to_dict(tmp_path):
    result = ReviewResult(
        review_package_id="RP-WP-001-claude",
        package_id="WP-001",
        reviewer_agent="claude",
        target_agent="codex",
        status=ReviewStatus.CHANGES_REQUESTED,
        summary="Needs stronger tests.",
        findings=["Missing edge-case coverage"],
        required_changes=["Add retry failure test"],
        follow_up=["Re-run focused pytest"],
        raw_response_path=tmp_path / "review.raw.txt",
    )

    restored = ReviewResult.from_dict(result.to_dict())

    assert restored.review_package_id == "RP-WP-001-claude"
    assert restored.status == ReviewStatus.CHANGES_REQUESTED
    assert restored.summary == "Needs stronger tests."
    assert restored.findings == ["Missing edge-case coverage"]
    assert restored.required_changes == ["Add retry failure test"]
    assert restored.follow_up == ["Re-run focused pytest"]
    assert restored.raw_response_path == tmp_path / "review.raw.txt"
