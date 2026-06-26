"""Workflow intent helpers."""

from __future__ import annotations

from trinity.models import DeliberationResult
from trinity.workflow.decomposer import classify_execution_intent


def requires_execution_for_deliberation(
    goal: str,
    result: DeliberationResult,
) -> bool:
    """Return whether a deliberation result should produce executable packages."""
    if any(task.requires_execution for task in result.tasks):
        return True

    text = "\n".join(
        part
        for part in (
            goal,
            result.user_prompt,
            result.consensus.summary if result.consensus else "",
        )
        if part
    )
    return classify_execution_intent(text)
