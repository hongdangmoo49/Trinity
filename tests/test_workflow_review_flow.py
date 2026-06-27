"""Tests for workflow review flow module boundaries."""

from __future__ import annotations

from trinity.workflow.execution_review_flow import (
    WorkflowReviewFlow as LegacyWorkflowReviewFlow,
)
from trinity.workflow.review_flow import WorkflowReviewFlow
from trinity.workflow.review_repair_metadata import (
    ReviewRepairEventMetadata,
    review_repair_metadata_from_events,
)


def test_legacy_execution_review_flow_reexports_review_flow():
    assert LegacyWorkflowReviewFlow is WorkflowReviewFlow


def test_review_repair_metadata_from_events_counts_legacy_requests():
    metadata = review_repair_metadata_from_events(
        [
            {
                "data": {
                    "package_id": "WP-001",
                    "review_package_id": "RP-WP-001-claude",
                }
            },
            {
                "data": {
                    "package_id": "WP-001",
                    "review_package_ids": [
                        "RP-WP-001-claude",
                        "RP-WP-001-codex",
                    ],
                    "repair_signature": "sig-2",
                }
            },
            {"data": {"package_id": ""}},
            {"data": []},
        ]
    )

    assert metadata == {
        "WP-001": ReviewRepairEventMetadata(
            attempt_count=2,
            repair_signature="sig-2",
            review_package_id="RP-WP-001-codex",
        )
    }


def test_review_repair_metadata_from_events_uses_event_attempt_count():
    metadata = review_repair_metadata_from_events(
        [
            {
                "data": {
                    "package_id": "WP-002",
                    "repair_attempt_count": 3,
                    "repair_signature": "sig-3",
                    "review_package_ids": ["RP-WP-002-claude"],
                }
            },
        ]
    )

    assert metadata["WP-002"] == ReviewRepairEventMetadata(
        attempt_count=3,
        repair_signature="sig-3",
        review_package_id="RP-WP-002-claude",
    )
