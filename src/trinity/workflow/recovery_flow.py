"""Execution interruption and retry recovery flow for WorkflowEngine."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from trinity.workflow.models import (
    WorkPackage,
    WorkStatus,
    WorkflowSession,
    WorkflowState,
)
from trinity.workflow.persistence import WorkflowPersistence


@dataclass(frozen=True)
class RetrySkip:
    """A work package omitted from an execution retry plan."""

    package_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class ExecutionRetryPlan:
    """Preview of the work packages that an execution retry will restart."""

    selector: str
    requested: tuple[str, ...]
    selected: tuple[str, ...]
    skipped: tuple[RetrySkip, ...]
    target_workspace: Path | None


PersistCallback = Callable[..., None]
SetStateCallback = Callable[..., None]


class ExecutionRecoveryFlow:
    """Stateful helper for execution interruption and retry recovery."""

    def __init__(
        self,
        *,
        session: WorkflowSession,
        persistence: WorkflowPersistence,
        persist: PersistCallback,
        set_state: SetStateCallback,
    ) -> None:
        self.session = session
        self.persistence = persistence
        self.persist = persist
        self.set_state = set_state

    def detect_interrupted_execution(
        self,
        *,
        worker_running: bool = False,
        reason: str = "process_lost",
    ) -> dict[str, Any] | None:
        """Mark and return stale execution recovery metadata."""
        if worker_running:
            return None
        if self.session.state != WorkflowState.EXECUTING:
            return None
        run = self.session.execution_run
        run_state = str(run.get("state", "")) if isinstance(run, dict) else ""
        running_packages = self.packages_with_status(WorkStatus.RUNNING)
        if run_state == "completed":
            return None
        if run_state not in {"running", "interrupted"} and not running_packages:
            return None
        if run_state != "interrupted":
            now = time.time()
            run = dict(run) if isinstance(run, dict) else {}
            run.setdefault("run_id", f"exec-run-{uuid4().hex[:12]}")
            run.setdefault("target_workspace", str(self.session.target_workspace or ""))
            run["state"] = "interrupted"
            run["interrupted_reason"] = reason
            run["interrupted_at"] = now
            run["running_packages"] = [package.id for package in running_packages]
            self.session.execution_run = run
            self.session.updated_at = now
            summary = self.execution_recovery_summary()
            self.persist(
                "execution_interrupted_detected",
                {
                    "run_id": run.get("run_id", ""),
                    "running_packages": run.get("running_packages", []),
                    "last_event_at": summary.get("last_event_at") if summary else None,
                    "reason": reason,
                },
                timestamp=now,
            )
            return summary
        return self.execution_recovery_summary()

    def execution_recovery_summary(self) -> dict[str, Any] | None:
        """Return a serializable execution recovery summary when applicable."""
        run = self.session.execution_run
        if not isinstance(run, dict) or not run:
            return None
        run_state = str(run.get("state", "") or "")
        if run_state not in {
            "running",
            "interrupted",
            "aborted",
            "failed",
            "repair_blocked",
        }:
            return None
        running_packages = self.packages_with_status(WorkStatus.RUNNING)
        if run_state == "running" and self.session.state != WorkflowState.EXECUTING:
            return None
        retry_candidates = [
            package.id
            for package in self.session.work_packages
            if package.requires_execution
            and package.status in {WorkStatus.RUNNING, WorkStatus.BLOCKED, WorkStatus.FAILED}
        ]
        done_packages = [
            package.id
            for package in self.session.work_packages
            if package.requires_execution and package.status == WorkStatus.DONE
        ]
        last_event = self.last_workflow_event()
        return {
            "run_id": str(run.get("run_id", "")),
            "state": run_state,
            "target_workspace": str(
                run.get("target_workspace") or self.session.target_workspace or ""
            ),
            "started_at": run.get("started_at"),
            "heartbeat_at": run.get("heartbeat_at"),
            "interrupted_reason": str(run.get("interrupted_reason", "") or ""),
            "running_packages": [package.id for package in running_packages],
            "done_packages": done_packages,
            "retry_candidates": retry_candidates,
            "last_event_at": last_event.get("timestamp") if last_event else None,
            "last_event": str(last_event.get("event", "")) if last_event else "",
        }

    def build_execution_retry_plan(
        self,
        selector: str = "all",
        package_ids: Iterable[str] = (),
    ) -> ExecutionRetryPlan:
        """Build a non-destructive retry plan for failed/blocked/stale packages."""
        normalized_selector = self.normalize_execution_retry_selector(selector, package_ids)
        requested = tuple(
            str(package_id).strip() for package_id in package_ids if str(package_id).strip()
        )
        summary = self.execution_recovery_summary()
        interrupted_ids = {
            str(package_id)
            for package_id in ((summary or {}).get("running_packages", []) if summary else [])
        }

        selected: list[str] = []
        skipped: list[RetrySkip] = []
        if normalized_selector == "custom":
            for package_id in requested:
                package = self.work_package_by_id(package_id)
                if package is None:
                    skipped.append(RetrySkip(package_id, "missing", "package not found"))
                    continue
                reason = self.execution_retry_disabled_reason(package, interrupted_ids)
                if reason:
                    skipped.append(RetrySkip(package.id, package.status.value, reason))
                    continue
                if package.id not in selected:
                    selected.append(package.id)
        else:
            for package in self.session.work_packages:
                if not self.matches_execution_retry_selector(
                    package,
                    normalized_selector,
                    interrupted_ids,
                ):
                    continue
                reason = self.execution_retry_disabled_reason(package, interrupted_ids)
                if reason:
                    skipped.append(RetrySkip(package.id, package.status.value, reason))
                    continue
                selected.append(package.id)

        return ExecutionRetryPlan(
            selector=normalized_selector,
            requested=requested,
            selected=tuple(selected),
            skipped=tuple(skipped),
            target_workspace=self.session.target_workspace,
        )

    def prepare_execution_retry(
        self,
        selector: str = "all",
        package_ids: Iterable[str] = (),
    ) -> ExecutionRetryPlan:
        """Mark selected retry packages pending without deleting prior results."""
        self.detect_interrupted_execution(worker_running=False)
        plan = self.build_execution_retry_plan(selector=selector, package_ids=package_ids)
        candidates = set(plan.selected)
        if not candidates:
            return plan

        summary = self.execution_recovery_summary()
        stale_running_ids = {
            str(package_id)
            for package_id in ((summary or {}).get("running_packages", []) if summary else [])
        }
        for package in self.session.work_packages:
            if package.id in candidates:
                previous_status = package.status.value
                package.status = WorkStatus.PENDING
                package.current_executor = ""
                package.repair_blocked_reason = ""
                package.repair_blocked_at = 0.0
                self.persist(
                    "work_package_retry_requested",
                    {
                        "package_id": package.id,
                        "previous_status": previous_status,
                        "agent": package.owner_agent,
                        "selector": plan.selector,
                    },
                )
                continue
            if package.id in stale_running_ids and package.status == WorkStatus.RUNNING:
                previous_status = package.status.value
                package.status = WorkStatus.BLOCKED
                package.current_executor = ""
                self.persist(
                    "work_package_retry_skipped",
                    {
                        "package_id": package.id,
                        "previous_status": previous_status,
                        "status": package.status.value,
                        "reason": "stale running package was not selected",
                    },
                )

        run = (
            dict(self.session.execution_run)
            if isinstance(self.session.execution_run, dict)
            else {}
        )
        run.setdefault("run_id", f"exec-run-{uuid4().hex[:12]}")
        run.setdefault("target_workspace", str(self.session.target_workspace or ""))
        run["state"] = "retry_requested"
        run["retry_requested_at"] = time.time()
        run["retry_selector"] = plan.selector
        run["retry_packages"] = list(plan.selected)
        self.session.execution_run = run
        self.session.updated_at = time.time()
        self.persist(
            "execution_recovery_action",
            {
                "action": "retry",
                "selector": plan.selector,
                "packages": list(plan.selected),
                "target_workspace": str(self.session.target_workspace or ""),
            },
        )
        self.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="work packages queued for retry",
        )
        return plan

    def retry_interrupted_execution(self) -> dict[str, Any] | None:
        """Prepare interrupted/failed packages for explicit user retry."""
        summary = self.detect_interrupted_execution(worker_running=False)
        if summary is None:
            summary = self.execution_recovery_summary()
        if summary is None:
            return None
        if summary.get("retry_candidates"):
            self.prepare_execution_retry("all")
        return summary

    @staticmethod
    def normalize_execution_retry_selector(
        selector: str,
        package_ids: Iterable[str],
    ) -> str:
        normalized = selector.strip().lower() or "all"
        if normalized in {"all", "failed", "blocked", "interrupted", "custom"}:
            return normalized
        if any(str(package_id).strip() for package_id in package_ids):
            return "custom"
        return "custom"

    @staticmethod
    def execution_retry_disabled_reason(
        package: WorkPackage,
        interrupted_ids: set[str],
    ) -> str:
        if not package.requires_execution:
            return "does not require execution"
        if package.status == WorkStatus.DONE:
            return "already done"
        if package.status == WorkStatus.NEEDS_REVIEW:
            return "already needs review"
        if package.status not in {WorkStatus.RUNNING, WorkStatus.FAILED, WorkStatus.BLOCKED}:
            return f"status is {package.status.value}"
        if (
            package.status == WorkStatus.RUNNING
            and interrupted_ids
            and package.id not in interrupted_ids
        ):
            return "running package is not part of the interrupted run"
        return ""

    @staticmethod
    def matches_execution_retry_selector(
        package: WorkPackage,
        selector: str,
        interrupted_ids: set[str],
    ) -> bool:
        if selector == "all":
            return package.status in {WorkStatus.RUNNING, WorkStatus.FAILED, WorkStatus.BLOCKED}
        if selector == "failed":
            return package.status == WorkStatus.FAILED
        if selector == "blocked":
            return package.status == WorkStatus.BLOCKED
        if selector == "interrupted":
            return package.id in interrupted_ids or (
                not interrupted_ids and package.status == WorkStatus.RUNNING
            )
        return False

    def mark_interrupted_execution(self) -> dict[str, Any] | None:
        """Turn stale running packages into blocked work that needs user review."""
        summary = self.detect_interrupted_execution(worker_running=False)
        if summary is None:
            summary = self.execution_recovery_summary()
        if summary is None:
            return None
        running_ids = set(summary.get("running_packages", []))
        for package in self.session.work_packages:
            if package.id in running_ids:
                package.status = WorkStatus.BLOCKED
                package.current_executor = ""
        self.persist_recovery_action("mark_interrupted", sorted(running_ids))
        self.set_state(WorkflowState.NEEDS_USER_DECISION, reason="execution marked interrupted")
        return self.execution_recovery_summary()

    def abort_interrupted_execution(self) -> dict[str, Any] | None:
        """Abort a stale execution and require an explicit user decision."""
        summary = self.detect_interrupted_execution(worker_running=False)
        if summary is None:
            summary = self.execution_recovery_summary()
        if summary is None:
            return None
        candidates = set(summary.get("retry_candidates", []))
        for package in self.session.work_packages:
            if package.id in candidates and package.status == WorkStatus.RUNNING:
                package.status = WorkStatus.BLOCKED
                package.current_executor = ""
        run = dict(self.session.execution_run)
        run["state"] = "aborted"
        run["aborted_at"] = time.time()
        self.session.execution_run = run
        self.persist_recovery_action("abort_execution", sorted(candidates))
        self.set_state(WorkflowState.NEEDS_USER_DECISION, reason="execution aborted")
        return self.execution_recovery_summary()

    def touch_execution_run(self, occurred_at: float | None = None) -> None:
        run = self.session.execution_run
        if not isinstance(run, dict) or not run:
            return
        if str(run.get("state", "")) != "running":
            return
        run["heartbeat_at"] = occurred_at if occurred_at is not None else time.time()
        self.session.execution_run = run

    def finish_execution_run(self, outcome: str) -> None:
        run = self.session.execution_run
        if not isinstance(run, dict) or not run:
            return
        if str(run.get("state", "")) == "interrupted":
            return
        run["state"] = "failed" if outcome == "failed" else "completed"
        run["outcome"] = outcome
        run["completed_at"] = time.time()
        self.session.execution_run = run

    def persist_recovery_action(self, action: str, packages: list[str]) -> None:
        run = dict(self.session.execution_run)
        run["last_recovery_action"] = action
        run["last_recovery_action_at"] = time.time()
        self.session.execution_run = run
        self.session.updated_at = time.time()
        self.persist(
            "execution_recovery_action",
            {
                "action": action,
                "packages": list(packages),
                "target_workspace": str(self.session.target_workspace or ""),
            },
        )

    def packages_with_status(self, status: WorkStatus) -> list[WorkPackage]:
        return [
            package
            for package in self.session.work_packages
            if package.requires_execution and package.status == status
        ]

    def last_workflow_event(self) -> dict[str, Any] | None:
        return self.persistence.last_event_for_workflow(self.session.id)

    def work_package_by_id(self, package_id: str) -> WorkPackage | None:
        for package in self.session.work_packages:
            if package.id == package_id:
                return package
        return None
