"""Tests for workflow post-review flow module boundaries."""

from __future__ import annotations

from trinity.workflow.execution_review_flow import (
    WorkflowPostReviewFlow as LegacyWorkflowPostReviewFlow,
)
from trinity.workflow.post_review_flow import WorkflowPostReviewFlow


def test_legacy_execution_review_flow_reexports_post_review_flow():
    assert LegacyWorkflowPostReviewFlow is WorkflowPostReviewFlow
