"""Tests for workflow peer review planning."""

import pytest

from trinity.models import AgentProfile, AgentSpec, Provider
from trinity.workflow.models import ExecutionResult, WorkPackage, WorkStatus
from trinity.workflow.review import (
    FINAL_REVIEW_FALLBACK_PRIORITY,
    FINAL_REVIEW_PACKAGE_ID,
    PeerReviewPlanner,
    ReviewDepth,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
    final_review_criteria,
    final_review_package,
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


def test_peer_review_planner_assigns_one_primary_non_owner_reviewer_by_default():
    packages = [
        _package("WP-001", "claude", ["Tests pass"]),
        _package("WP-002", "codex"),
        _package("WP-003", "antigravity"),
    ]

    reviews = PeerReviewPlanner().plan_reviews(
        packages,
        active_agents=["claude", "codex", "antigravity"],
    )

    assert [
        (review.package_id, review.target_agent, review.reviewer_agent)
        for review in reviews
    ] == [
        ("WP-001", "claude", "antigravity"),
        ("WP-002", "codex", "antigravity"),
        ("WP-003", "antigravity", "claude"),
    ]
    assert all(review.reviewer_agent != review.target_agent for review in reviews)
    assert all(review.self_review is False for review in reviews)
    assert all(review.depth == ReviewDepth.SINGLE_PEER for review in reviews)
    assert all(review.required is True for review in reviews)
    assert "Tests pass" in reviews[0].criteria


def test_peer_review_planner_assigns_self_check_for_single_active_agent():
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
    assert review.depth == ReviewDepth.SELF_CHECK
    assert review.required is True
    assert review.reason == "self-check because no non-owner peer reviewer is active"
    assert "Verify the work package acceptance criteria" in review.criteria[0]


def test_peer_review_planner_uses_only_non_owner_for_two_active_agents():
    reviews = PeerReviewPlanner().plan_reviews(
        [_package("WP-001", "codex")],
        active_agents=["claude", "codex"],
    )

    assert len(reviews) == 1
    review = reviews[0]
    assert review.reviewer_agent == "claude"
    assert review.target_agent == "codex"
    assert review.depth == ReviewDepth.SINGLE_PEER
    assert review.reason == "single available non-owner reviewer"


def test_peer_review_planner_uses_deterministic_primary_priority():
    planner = PeerReviewPlanner()

    assert [
        planner.plan_reviews([_package("WP-001", target)], agents)[0].reviewer_agent
        for target, agents in [
            ("codex", ["claude", "codex", "antigravity"]),
            ("antigravity", ["claude", "codex", "antigravity"]),
            ("claude", ["codex", "claude", "antigravity"]),
        ]
    ] == ["antigravity", "claude", "antigravity"]


def test_peer_review_planner_uses_profile_review_fit():
    agents = {
        "claude": AgentSpec(
            name="claude",
            provider=Provider.CLAUDE_CODE,
            cli_command="claude",
            profile=AgentProfile(
                mission="Review specialist",
                strengths={"review": 1.0},
                supported_turn_modes=["review"],
                routing_priority=1,
            ),
        ),
        "codex": AgentSpec(
            name="codex",
            provider=Provider.CODEX,
            cli_command="codex",
        ),
        "antigravity": AgentSpec(
            name="antigravity",
            provider=Provider.ANTIGRAVITY_CLI,
            cli_command="agy",
            profile=AgentProfile(
                mission="Implementation specialist",
                strengths={"review": 0.1},
                supported_turn_modes=["review"],
                routing_priority=10,
            ),
        ),
    }

    reviews = PeerReviewPlanner().plan_reviews(
        [_package("WP-001", "codex")],
        active_agents=agents,
    )

    assert reviews[0].reviewer_agent == "claude"
    assert reviews[0].reason == "selected claude by profile review fit"


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
    assert restored.scope == "work_package"
    assert restored.attempt == 1
    assert restored.depth == ReviewDepth.SINGLE_PEER
    assert restored.required is True
    assert restored.created_at > 0


def test_review_package_round_trips_skip_and_escalation_metadata():
    review = ReviewPackage(
        package_id="WP-001",
        reviewer_agent="",
        target_agent="codex",
        depth=ReviewDepth.NONE,
        required=False,
        reason="peer review skipped because no peer reviewer is active",
        skipped_reason="only codex is active; no non-owner peer reviewer is available",
    )

    restored = ReviewPackage.from_dict(review.to_dict())

    assert restored.id == "RP-WP-001-skipped"
    assert restored.depth == ReviewDepth.NONE
    assert restored.required is False
    assert restored.self_review is False
    assert restored.skipped_reason.startswith("only codex")


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
        severity="high",
        reviewed_files=["src/retry.py"],
        performance_notes=["Retry loop has bounded backoff."],
        anti_patterns=["Broad exception handling hides root cause."],
        execution_risks=["Retry may fail under missing workspace."],
        skipped=True,
        skipped_reason="no peer reviewer",
        confidence="low",
    )

    restored = ReviewResult.from_dict(result.to_dict())

    assert restored.review_package_id == "RP-WP-001-claude"
    assert restored.status == ReviewStatus.CHANGES_REQUESTED
    assert restored.summary == "Needs stronger tests."
    assert restored.findings == ["Missing edge-case coverage"]
    assert restored.required_changes == ["Add retry failure test"]
    assert restored.follow_up == ["Re-run focused pytest"]
    assert restored.raw_response_path == tmp_path / "review.raw.txt"
    assert restored.severity == "high"
    assert restored.scope == "work_package"
    assert restored.reviewed_files == ["src/retry.py"]
    assert restored.performance_notes == ["Retry loop has bounded backoff."]
    assert restored.anti_patterns == ["Broad exception handling hides root cause."]
    assert restored.execution_risks == ["Retry may fail under missing workspace."]
    assert restored.skipped is True
    assert restored.skipped_reason == "no peer reviewer"
    assert restored.confidence == "low"


def test_peer_review_planner_prepares_high_risk_escalation_hook():
    package = _package("WP-001", "codex")
    package.risk = "high"
    planner = PeerReviewPlanner()
    primary = planner.plan_reviews(
        [package],
        active_agents=["claude", "codex", "antigravity"],
    )

    escalations = planner.plan_escalation_reviews(
        [package],
        active_agents=["claude", "codex", "antigravity"],
        existing_reviews=primary,
    )

    assert len(escalations) == 1
    escalation = escalations[0]
    assert escalation.depth == ReviewDepth.ESCALATED_PEER
    assert escalation.escalation_parent_id == primary[0].id
    assert escalation.reviewer_agent == "claude"
    assert escalation.reason == "package risk is high"


def test_peer_review_planner_prepares_changes_requested_escalation_hook():
    package = _package("WP-001", "codex")
    planner = PeerReviewPlanner()
    primary = planner.plan_reviews(
        [package],
        active_agents=["claude", "codex", "antigravity"],
    )

    escalations = planner.plan_escalation_reviews(
        [package],
        active_agents=["claude", "codex", "antigravity"],
        existing_reviews=primary,
        review_results=[
            ReviewResult(
                review_package_id=primary[0].id,
                package_id="WP-001",
                reviewer_agent=primary[0].reviewer_agent,
                target_agent="codex",
                status=ReviewStatus.CHANGES_REQUESTED,
            )
        ],
    )

    assert len(escalations) == 1
    assert escalations[0].reviewer_agent == "claude"
    assert escalations[0].reason == "primary review status is changes_requested"


def test_final_review_package_uses_codex_first_fallback_contract():
    assert FINAL_REVIEW_FALLBACK_PRIORITY == ("codex", "claude", "antigravity")

    review = final_review_package(FINAL_REVIEW_FALLBACK_PRIORITY[0])

    assert review.package_id == FINAL_REVIEW_PACKAGE_ID
    assert review.reviewer_agent == "codex"
    assert review.target_agent == "project"
    assert review.scope == "final"
    assert review.self_review is False
    assert "project overview" in " ".join(final_review_criteria()).lower()
