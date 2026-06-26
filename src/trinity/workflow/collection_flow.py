"""Shared workflow collection helpers."""

from __future__ import annotations

from typing import Any

from trinity.workflow.models import SubtaskResult, WorkPackage


class WorkflowCollectionFlow:
    """Lookup and update list-backed workflow session collections."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def work_package_by_id(self, package_id: str) -> WorkPackage | None:
        return next(
            (
                package
                for package in self.engine.session.work_packages
                if package.id == package_id
            ),
            None,
        )

    def upsert_subtask_result(self, result: SubtaskResult) -> None:
        """Insert or replace a subtask result by id."""
        for index, existing in enumerate(self.engine.session.subtask_results):
            if existing.id == result.id:
                self.engine.session.subtask_results[index] = result
                return
        self.engine.session.subtask_results.append(result)
