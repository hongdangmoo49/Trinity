"""Execution flow helpers for WorkflowEngine."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from trinity.providers.policy import (
    ExecutionAuthority,
    ExecutionScope,
    InvocationAccess,
    ParallelExecutionPolicy,
)
from trinity.routing.quality import QualityLedger
from trinity.workflow.models import (
    ExecutionResult,
    WorkPackage,
    WorkStatus,
    WorkflowState,
)


class WorkflowExecutionFlow:
    """Execution scheduling and result-recording entrypoints."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def pending_execution_package_ids(self) -> list[str]:
        session = self.engine.session
        run = session.execution_run if isinstance(session.execution_run, dict) else {}
        retry_packages = (
            [
                str(package_id).strip()
                for package_id in run.get("retry_packages", [])
                if str(package_id).strip()
            ]
            if str(run.get("state", "")) == "retry_requested"
            else []
        )
        if retry_packages:
            retry_id_set = set(retry_packages)
            return [
                package.id
                for package in session.work_packages
                if package.id in retry_id_set
                and package.requires_execution
                and package.status not in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
            ]

        return [
            package.id
            for package in session.work_packages
            if package.requires_execution
            and package.status not in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
        ]

    def begin_execution(self, package_ids: Iterable[str] | None = None) -> None:
        session = self.engine.session
        if not session.work_packages:
            return
        if session.target_workspace is None:
            raise RuntimeError("Target workspace is required before implementation.")
        run_id = f"exec-run-{uuid4().hex[:12]}"
        now = time.time()
        previous_run = (
            dict(session.execution_run)
            if isinstance(session.execution_run, dict)
            else {}
        )
        if package_ids is None:
            selected_ids = self.pending_execution_package_ids()
        else:
            requested = {str(package_id).strip() for package_id in package_ids}
            selected_ids = [
                package.id
                for package in session.work_packages
                if package.id in requested
                and package.requires_execution
                and package.status not in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
            ]
        work_package_ids = list(selected_ids)
        if not work_package_ids:
            return
        execution_run = {
            "run_id": run_id,
            "started_at": now,
            "heartbeat_at": now,
            "state": "running",
            "target_workspace": str(session.target_workspace),
            "work_packages": list(work_package_ids),
        }
        if str(previous_run.get("state", "")) == "retry_requested":
            execution_run["retry_selector"] = str(previous_run.get("retry_selector", "") or "")
            execution_run["retry_requested_at"] = previous_run.get("retry_requested_at")
            execution_run["retry_packages"] = list(previous_run.get("retry_packages", []))
            execution_run["repair_blocked_packages"] = list(
                previous_run.get("repair_blocked_packages", [])
            )
            if previous_run.get("repair_blocked_at") is not None:
                execution_run["repair_blocked_at"] = previous_run.get("repair_blocked_at")
        if str(previous_run.get("state", "")) == "supplemental_queued":
            execution_run["kind"] = str(previous_run.get("kind", "supplemental") or "supplemental")
            execution_run["source"] = str(
                previous_run.get("source", "post_review_followup") or "post_review_followup"
            )
            execution_run["round"] = previous_run.get("round")
            execution_run["action_item_ids"] = list(previous_run.get("action_item_ids", []))
        session.execution_run = execution_run
        self.engine._persist(
            "execution_run_started",
            {
                "run_id": run_id,
                "target_workspace": str(session.target_workspace),
                "work_packages": list(work_package_ids),
            },
            timestamp=now,
        )
        self.engine._persist(
            "implementation_requested",
            {
                "target_workspace": str(session.target_workspace),
                "work_packages": list(work_package_ids),
            },
        )
        self.engine.set_state(WorkflowState.EXECUTING, reason="work package execution started")

    def record_work_package_started(
        self,
        package_id: str,
        agent_name: str = "",
        occurred_at: float | None = None,
    ) -> None:
        package = self.engine._work_package_by_id(package_id)
        if package is None:
            return

        executor = agent_name or package.owner_agent
        package.status = WorkStatus.RUNNING
        package.current_executor = executor
        package.last_executor = executor
        self.engine._touch_execution_run(occurred_at)
        self.engine.session.updated_at = time.time()
        self.engine._persist(
            "work_package_started",
            {
                "package_id": package.id,
                "agent": executor,
                "status": package.status.value,
            },
            timestamp=occurred_at,
        )

    def record_work_package_completed(
        self,
        package_id: str,
        agent_name: str = "",
        status: str = "",
        summary: str = "",
        occurred_at: float | None = None,
        attempt_chain: list[dict[str, object]] | None = None,
        raw_response_path: str = "",
    ) -> None:
        package = self.engine._work_package_by_id(package_id)
        if package is None:
            return

        executor = agent_name or package.owner_agent
        if status:
            try:
                package.status = WorkStatus(status)
            except ValueError:
                pass
        package.current_executor = ""
        package.last_executor = executor
        self.engine._touch_execution_run(occurred_at)
        self.engine.session.updated_at = time.time()
        event_data: dict[str, object] = {
            "package_id": package.id,
            "agent": executor,
            "status": package.status.value,
            "summary": summary,
        }
        if attempt_chain:
            event_data["attempt_chain"] = attempt_chain
        if raw_response_path:
            event_data["raw_response_path"] = raw_response_path
        self.engine._persist(
            "work_package_completed",
            event_data,
            timestamp=occurred_at,
        )

    def plan_parallel_groups(self) -> list[list[WorkPackage]]:
        session = self.engine.session
        packages_by_id = {
            package.id: package
            for package in session.work_packages
            if package.requires_execution
        }
        remaining = dict(packages_by_id)
        completed = {
            package.id
            for package in session.work_packages
            if package.status == WorkStatus.DONE
        }
        groups: list[list[WorkPackage]] = []
        policy = ParallelExecutionPolicy()

        while remaining:
            ready = [
                package
                for package in remaining.values()
                if all(
                    dep_id in completed or dep_id not in packages_by_id
                    for dep_id in package.dependencies
                )
            ]
            if not ready:
                groups.extend([package] for package in remaining.values())
                break

            ordered_ready = sorted(
                ready,
                key=lambda item: (-item.estimated_weight, item.id),
            )
            scope_by_package_id = {
                id(package): self.preview_execution_scope(package)
                for package in ordered_ready
            }
            package_by_scope_id = {
                id(scope): package
                for package in ordered_ready
                for scope in (scope_by_package_id[id(package)],)
            }
            scope_batches = policy.plan_batches(scope_by_package_id.values())
            batch = [
                package_by_scope_id[id(scope)]
                for scope in (scope_batches[0] if scope_batches else ())
            ]
            if not batch:
                batch.append(ordered_ready[0])
            groups.append(batch)
            for package in batch:
                completed.add(package.id)
                remaining.pop(package.id, None)

        return groups

    @staticmethod
    def preview_execution_scope(package: WorkPackage) -> ExecutionScope:
        return ExecutionScope(
            agent_name=package.owner_agent,
            authority=ExecutionAuthority.PROVIDER_MANAGED,
            access=InvocationAccess.WORKSPACE_WRITE,
            workspace_id="workflow-preview",
            file_ownership=frozenset(
                item.strip() for item in package.expected_files if item.strip()
            ),
            parallelizable=package.parallelizable,
            risk=package.risk,
            parallel_group=package.parallel_group,
        )

    def record_execution_batch_planned(
        self,
        batches: list[list[str]],
        notices: list[dict[str, object]] | None = None,
        occurred_at: float | None = None,
    ) -> None:
        self.engine._touch_execution_run(occurred_at)
        self.engine.session.updated_at = time.time()
        self.engine._persist(
            "execution_batch_planned",
            {
                "batches": batches,
                "notices": notices or [],
            },
            timestamp=occurred_at,
        )

    def record_execution_results(
        self,
        results: list[ExecutionResult],
        *,
        finalize: bool = True,
        emit_events: bool = True,
    ) -> None:
        if not results:
            return

        for result in results:
            self.record_execution_result(result, emit_event=emit_events)

        if finalize:
            self.finalize_execution_state()

    def record_execution_result(
        self,
        result: ExecutionResult,
        *,
        emit_event: bool,
    ) -> None:
        session = self.engine.session
        package = self.engine._work_package_by_id(result.package_id)
        if package:
            package.status = result.status
            package.current_executor = ""
            package.last_executor = result.agent_name or package.last_executor
            if (
                result.status == WorkStatus.DONE
                and package.origin == "post_review_followup"
            ):
                self.engine._post_review_flow().mark_items_done(
                    package.origin_action_item_ids
                )

        existing_by_package = {item.package_id: item for item in session.execution_results}
        existing_by_package[result.package_id] = result

        for decision in result.decisions_made:
            if not any(existing.id == decision.id for existing in session.decisions):
                session.decisions.append(decision)
        for subtask in result.subtasks:
            self.engine._upsert_subtask_result(subtask)
        self.record_execution_quality(result)

        ordered_package_ids = [package.id for package in session.work_packages]
        session.execution_results = [
            existing_by_package[package_id]
            for package_id in ordered_package_ids
            if package_id in existing_by_package
        ]
        ordered_package_id_set = set(ordered_package_ids)
        extras = [
            result
            for package_id, result in existing_by_package.items()
            if package_id not in ordered_package_id_set
        ]
        session.execution_results.extend(extras)
        session.updated_at = time.time()

        if emit_event:
            event_data: dict[str, object] = {
                "package_id": result.package_id,
                "agent": result.agent_name,
                "status": result.status.value,
            }
            if result.attempt_chain:
                event_data["attempt_chain"] = list(result.attempt_chain)
            if result.raw_response_path:
                event_data["raw_response_path"] = str(result.raw_response_path)
            if session.quality_signals:
                event_data["quality_signal"] = session.quality_signals[-1]
            self.engine._persist(
                "execution_result_recorded",
                event_data,
            )
        else:
            self.engine.save()

    def finalize_execution_state(self) -> None:
        session = self.engine.session
        executable = [
            package for package in session.work_packages if package.requires_execution
        ]
        if any(package.status == WorkStatus.FAILED for package in executable):
            self.engine._finish_execution_run("failed")
            self.engine.set_state(
                WorkflowState.FAILED,
                reason="work package execution failed",
            )
            return
        if any(
            package.status in {WorkStatus.BLOCKED, WorkStatus.WAITING_ON_DECISION}
            for package in executable
        ):
            self.engine._finish_execution_run("blocked")
            self.engine.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="work package execution is blocked",
            )
            return
        if executable and all(
            package.status in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
            for package in executable
        ):
            self.engine._finish_execution_run("completed")
            self.engine._plan_review_packages()
            self.engine.set_state(
                WorkflowState.REVIEWING,
                reason="all work packages completed",
            )
            return
        self.engine.set_state(
            WorkflowState.EXECUTING,
            reason="work package execution still in progress",
        )

    def record_execution_quality(self, result: ExecutionResult) -> None:
        ledger = QualityLedger(self.engine.session.quality_signals)
        signal = ledger.record_execution(result)
        self.engine.session.quality_signals = ledger.to_dicts()
        self.engine._persist(
            "quality_signal_recorded",
            signal.to_dict(),
        )
