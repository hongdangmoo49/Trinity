"""Tests for workflow review flow module boundaries."""

from __future__ import annotations

from trinity.workflow.execution_review_flow import (
    WorkflowReviewFlow as LegacyWorkflowReviewFlow,
)
from trinity.workflow.review_flow import WorkflowReviewFlow


def test_legacy_execution_review_flow_reexports_review_flow():
    assert LegacyWorkflowReviewFlow is WorkflowReviewFlow
