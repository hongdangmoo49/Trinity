"""Tests for workflow execution flow module boundaries."""

from __future__ import annotations

from trinity.workflow.execution_flow import WorkflowExecutionFlow
from trinity.workflow.execution_review_flow import (
    WorkflowExecutionFlow as LegacyWorkflowExecutionFlow,
)


def test_legacy_execution_review_flow_reexports_execution_flow():
    assert LegacyWorkflowExecutionFlow is WorkflowExecutionFlow
