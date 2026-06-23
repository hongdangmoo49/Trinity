"""Execution, review, and post-review flow helpers for WorkflowEngine."""

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
from trinity.workflow.models import (
    ExecutionResult,
    PostReviewActionItem,
    PostReviewActionStatus,
    WorkPackage,
    WorkStatus,
    WorkflowState,
)
from trinity.workflow.review import (
    FINAL_REVIEW_PACKAGE_ID,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
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
            self.engine._record_execution_result(result, emit_event=emit_events)

        if finalize:
            self.engine._finalize_execution_state()


class WorkflowReviewFlow:
    """Review planning, result recording, and repair-loop entrypoints."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def ensure_review_packages(self) -> list[ReviewPackage]:
        session = self.engine.session
        if not session.review_packages and session.work_packages:
            self.engine._plan_review_packages()
            session.updated_at = time.time()
            self.engine._persist(
                "review_packages_planned",
                {
                    "review_packages": [
                        item.get("id", "") for item in session.review_packages
                    ],
                },
            )
        return self.review_packages_for_request("wp")

    def review_packages_for_request(
        self,
        selector: str = "wp",
        package_ids: Iterable[str] = (),
    ) -> list[ReviewPackage]:
        normalized = (selector or "wp").strip().lower()
        requested = {
            str(package_id).strip()
            for package_id in package_ids
            if str(package_id).strip()
        }
        explicit = bool(requested)
        if normalized in {"all", "wp", "work-package", "work_packages"}:
            scope = "work_package"
        else:
            scope = normalized

        reviews: list[ReviewPackage] = []
        for item in self.engine.session.review_packages:
            if not isinstance(item, dict):
                continue
            try:
                review = ReviewPackage.from_dict(item)
            except (TypeError, ValueError):
                continue
            if review.scope == "final" or review.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            if not review.required:
                continue
            if scope not in {"work_package", "custom"}:
                continue
            if requested and review.package_id not in requested:
                continue
            if not explicit and self.engine._review_package_is_approved(review):
                continue
            reviews.append(review)
        return reviews

    def record_review_results(
        self,
        results: Iterable[ReviewResult],
        *,
        finalize: bool = True,
    ) -> None:
        review_results = list(results)
        if not review_results:
            return
        for result in review_results:
            self.engine._record_review_result(result)
        if finalize:
            self.engine._finalize_review_state(review_results)

    def prepare_review_repairs(
        self,
        results: Iterable[ReviewResult],
        *,
        max_attempts: int = 3,
    ) -> tuple[str, ...]:
        selected: list[str] = []
        blocked: list[dict[str, Any]] = []
        max_attempts = max(0, int(max_attempts or 0))
        repair_requests: dict[str, tuple[WorkPackage, list[ReviewResult]]] = {}
        for result in results:
            if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            if result.status != ReviewStatus.CHANGES_REQUESTED:
                continue
            package = self.engine._work_package_by_id(result.package_id)
            if package is None or not package.requires_execution:
                continue
            if package.id not in repair_requests:
                repair_requests[package.id] = (package, [])
            repair_requests[package.id][1].append(result)

        for package, package_results in repair_requests.values():
            result = package_results[-1]
            required_changes = self.engine._merged_review_repair_changes(package_results)
            signature = self.engine._review_repair_signature_from_parts(
                package.id,
                self.engine._review_repair_target_agent(package, package_results),
                required_changes,
            )
            if package.repair_attempt_count >= max_attempts:
                blocked.append(
                    self.engine._block_review_repair(
                        package,
                        result,
                        reason="max_attempts_exceeded",
                        signature=signature,
                        max_attempts=max_attempts,
                        required_changes=required_changes,
                        review_package_ids=[
                            review.review_package_id for review in package_results
                        ],
                    )
                )
                continue
            if package.last_repair_signature == signature and package.repair_attempt_count > 0:
                blocked.append(
                    self.engine._block_review_repair(
                        package,
                        result,
                        reason="duplicate_required_changes",
                        signature=signature,
                        max_attempts=max_attempts,
                        required_changes=required_changes,
                        review_package_ids=[
                            review.review_package_id for review in package_results
                        ],
                    )
                )
                continue
            previous_status = package.status.value
            package.status = WorkStatus.PENDING
            package.current_executor = ""
            package.repair_attempt_count += 1
            package.last_repair_signature = signature
            package.last_repair_review_id = result.review_package_id
            package.repair_blocked_reason = ""
            package.repair_blocked_at = 0.0
            if package.id not in selected:
                selected.append(package.id)
            self.engine._persist(
                "work_package_repair_requested",
                {
                    "package_id": package.id,
                    "previous_status": previous_status,
                    "review_package_id": result.review_package_id,
                    "review_package_ids": [
                        review.review_package_id for review in package_results
                    ],
                    "reviewer": result.reviewer_agent,
                    "reviewers": [review.reviewer_agent for review in package_results],
                    "target": result.target_agent,
                    "targets": [review.target_agent for review in package_results],
                    "required_changes": list(required_changes),
                    "repair_attempt_count": package.repair_attempt_count,
                    "max_attempts": max_attempts,
                    "repair_signature": signature,
                    "executor": package.last_executor or package.owner_agent,
                },
            )

        if not selected:
            if blocked:
                self._mark_repair_blocked(blocked, reason="review repair blocked")
            return ()

        session = self.engine.session
        run = dict(session.execution_run) if isinstance(session.execution_run, dict) else {}
        run.setdefault("run_id", f"exec-run-{uuid4().hex[:12]}")
        run.setdefault("target_workspace", str(session.target_workspace or ""))
        run["state"] = "retry_requested"
        run["retry_requested_at"] = time.time()
        run["retry_selector"] = "review-repair"
        run["retry_packages"] = list(selected)
        if blocked:
            run["repair_blocked_at"] = time.time()
            run["repair_blocked_packages"] = [
                item["package_id"] for item in blocked
            ]
        else:
            run.pop("repair_blocked_at", None)
            run.pop("repair_blocked_packages", None)
        session.execution_run = run
        session.updated_at = time.time()
        self.engine._persist(
            "execution_recovery_action",
            {
                "action": "review_repair",
                "packages": list(selected),
                "blocked_packages": [
                    item["package_id"] for item in blocked
                ],
                "target_workspace": str(session.target_workspace or ""),
            },
        )
        self.engine.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="review changes queued for repair",
        )
        return tuple(selected)

    def reconcile_review_repair_metadata(
        self,
        *,
        max_attempts: int = 3,
    ) -> tuple[str, ...]:
        max_attempts = max(0, int(max_attempts or 0))
        event_metadata = self.engine._review_repair_metadata_from_events()
        if not event_metadata:
            return ()

        latest_change_by_package: dict[str, ReviewResult] = {}
        for result in self.engine._review_results():
            if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            if result.status == ReviewStatus.CHANGES_REQUESTED:
                latest_change_by_package[result.package_id] = result

        changed = False
        blocked: list[str] = []
        for package in self.engine.session.work_packages:
            metadata = event_metadata.get(package.id, {})
            attempts = int(metadata.get("attempt_count", 0) or 0)
            if attempts <= 0:
                continue
            if package.repair_attempt_count < attempts:
                package.repair_attempt_count = attempts
                changed = True
            event_signature = str(metadata.get("repair_signature", "") or "")
            event_review_id = str(metadata.get("review_package_id", "") or "")
            if event_signature and not package.last_repair_signature:
                package.last_repair_signature = event_signature
                package.last_repair_review_id = event_review_id
                changed = True
            latest_change = latest_change_by_package.get(package.id)
            if latest_change is not None and not package.last_repair_signature:
                package.last_repair_signature = self.engine._review_repair_signature(
                    latest_change
                )
                package.last_repair_review_id = latest_change.review_package_id
                changed = True
            if (
                package.repair_attempt_count >= max_attempts
                and not package.repair_blocked_reason
                and package.status
                in {WorkStatus.PENDING, WorkStatus.RUNNING, WorkStatus.NEEDS_REVIEW}
            ):
                previous_status = package.status.value
                package.status = WorkStatus.BLOCKED
                package.current_executor = ""
                package.repair_blocked_reason = "legacy_repair_loop_detected"
                package.repair_blocked_at = time.time()
                blocked.append(package.id)
                changed = True
                self.engine._persist(
                    "work_package_repair_blocked",
                    {
                        "package_id": package.id,
                        "previous_status": previous_status,
                        "reason": package.repair_blocked_reason,
                        "repair_attempt_count": package.repair_attempt_count,
                        "max_attempts": max_attempts,
                        "repair_signature": package.last_repair_signature,
                    },
                )

        if blocked:
            self._mark_repair_blocked(
                [{"package_id": package_id} for package_id in blocked],
                reason="legacy review repair loop detected",
            )
            return tuple(blocked)

        if changed:
            self.engine.save()
        return ()

    def review_repair_blocked_package_ids(self) -> tuple[str, ...]:
        return tuple(
            package.id
            for package in self.engine.session.work_packages
            if package.requires_execution
            and package.status == WorkStatus.BLOCKED
            and bool(package.repair_blocked_reason)
        )

    def accept_review_repair_blocks(self) -> tuple[str, ...]:
        package_ids = self.review_repair_blocked_package_ids()
        if not package_ids:
            return ()
        accepted = set(package_ids)
        for package in self.engine.session.work_packages:
            if package.id not in accepted:
                continue
            previous_status = package.status.value
            reason = package.repair_blocked_reason
            package.status = WorkStatus.DONE
            package.current_executor = ""
            package.repair_blocked_reason = ""
            package.repair_blocked_at = 0.0
            note = f"user accepted blocked repair: {reason}"
            if note not in package.repair_notes:
                package.repair_notes.append(note)
            self.engine._persist(
                "work_package_repair_accepted",
                {
                    "package_id": package.id,
                    "previous_status": previous_status,
                    "reason": reason,
                    "repair_attempt_count": package.repair_attempt_count,
                },
            )

        session = self.engine.session
        run = dict(session.execution_run) if isinstance(session.execution_run, dict) else {}
        run["state"] = "repair_accepted"
        run["repair_accepted_at"] = time.time()
        run["repair_accepted_packages"] = list(package_ids)
        session.execution_run = run
        session.updated_at = time.time()
        self.engine.set_state(
            WorkflowState.REVIEWING,
            reason="review repair accepted by user",
        )
        return package_ids

    def stop_review_repair_blocks(self) -> tuple[str, ...]:
        package_ids = self.review_repair_blocked_package_ids()
        if not package_ids:
            return ()
        session = self.engine.session
        run = dict(session.execution_run) if isinstance(session.execution_run, dict) else {}
        run["state"] = "repair_stopped"
        run["repair_stopped_at"] = time.time()
        run["repair_stopped_packages"] = list(package_ids)
        session.execution_run = run
        session.updated_at = time.time()
        self.engine._persist(
            "work_package_repair_stopped",
            {
                "packages": list(package_ids),
            },
        )
        self.engine.set_state(
            WorkflowState.FAILED,
            reason="review repair stopped by user",
        )
        return package_ids

    def _mark_repair_blocked(
        self,
        blocked: list[dict[str, Any]],
        *,
        reason: str,
    ) -> None:
        session = self.engine.session
        run = dict(session.execution_run) if isinstance(session.execution_run, dict) else {}
        run["state"] = "repair_blocked"
        run["repair_blocked_at"] = time.time()
        run["repair_blocked_packages"] = [item["package_id"] for item in blocked]
        session.execution_run = run
        session.updated_at = time.time()
        self.engine.set_state(WorkflowState.NEEDS_USER_DECISION, reason=reason)


class WorkflowPostReviewFlow:
    """Final-review follow-up and supplemental work package entrypoints."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def finalize_post_review(self, final_result: ReviewResult | None = None) -> None:
        created = self.extract_post_review_items(final_result)
        self.engine.session.updated_at = time.time()
        self.engine._persist(
            "post_review_items_extracted",
            {
                "review_package_id": final_result.review_package_id if final_result else "",
                "created": [item.id for item in created],
                "total": len(self.engine.session.post_review_items),
            },
        )
        auto_replanned = self._auto_replan_final_review_changes(
            final_result,
            created,
        )
        if auto_replanned:
            return
        self.engine.set_state(
            WorkflowState.POST_REVIEW_READY,
            reason="final review complete; waiting for follow-up selection",
        )

    def extract_post_review_items(
        self,
        final_result: ReviewResult | None = None,
    ) -> list[PostReviewActionItem]:
        existing = self.engine._post_review_items()
        existing_keys = {self.engine._post_review_item_key(item) for item in existing}
        created: list[PostReviewActionItem] = []
        reviews = self.engine._review_results()
        if final_result is not None and not any(
            item.review_package_id == final_result.review_package_id
            and item.package_id == final_result.package_id
            for item in reviews
        ):
            reviews.append(final_result)

        for review in reviews:
            candidates = self.engine._post_review_candidates_from_review(review)
            for candidate in candidates:
                key = self.engine._post_review_item_key(candidate)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                candidate.id = self.engine._next_post_review_item_id([*existing, *created])
                created.append(candidate)

        if created:
            self.engine.session.post_review_items.extend(
                item.to_dict() for item in created
            )
        return created

    def handle_post_review_input(
        self,
        text: str,
        active_agents: list[str],
    ) -> Any:
        instruction = self.engine._normalize_improve_instruction(text)
        if self.engine.session.state != WorkflowState.POST_REVIEW_READY:
            return self.engine.input_action_type(
                should_deliberate=False,
                message="No post-review follow-up is ready for this workflow.",
            )
        if active_agents:
            self.engine.session.active_agents = list(active_agents)
        if not instruction:
            return self.engine.input_action_type(
                should_deliberate=False,
                message=self.post_review_summary(),
            )

        if self.engine._is_post_review_done_command(instruction):
            self.engine._record_follow_up_request(
                instruction,
                [],
                source_state=self.engine.session.state.value,
            )
            self.engine.set_state(WorkflowState.DONE, reason="post-review follow-up closed by user")
            return self.engine.input_action_type(
                should_deliberate=False,
                message="Post-review follow-up closed. Workflow is done.",
            )

        if self.engine.session.target_workspace is None:
            return self.engine.input_action_type(
                should_deliberate=False,
                target_workspace_required=True,
                message="Target workspace is required before post-review improvement.",
            )

        selected = self.engine._select_post_review_items(instruction)
        created_from_text = False
        if not selected and not self.engine._looks_like_post_review_selector(instruction):
            item = self.engine._create_user_request_action_item(instruction)
            self.engine.session.post_review_items.append(item.to_dict())
            selected = [item.id]
            created_from_text = True

        if not selected:
            return self.engine.input_action_type(
                should_deliberate=False,
                message=(
                    "No matching post-review action items. "
                    "Use /improve, /improve high, /improve all, /improve AI-001, or /improve done."
                ),
            )

        source_state = self.engine.session.state.value
        package_ids = self.accept_post_review_items(
            selected,
            note=instruction,
            active_agents=active_agents,
        )
        self.engine._record_follow_up_request(instruction, selected, source_state=source_state)
        if not package_ids:
            return self.engine.input_action_type(
                should_deliberate=False,
                message="Selected post-review items do not require execution.",
            )

        source = "new request" if created_from_text else "selected items"
        return self.engine.input_action_type(
            should_deliberate=False,
            execution_requested=True,
            message=(
                f"Queued post-review improvement from {source}: "
                f"{', '.join(package_ids)}."
            ),
        )

    def accept_post_review_items(
        self,
        item_ids: Iterable[str],
        *,
        note: str | None = None,
        active_agents: list[str] | None = None,
    ) -> tuple[str, ...]:
        requested = {str(item_id).strip() for item_id in item_ids if str(item_id).strip()}
        if not requested:
            return ()
        items = self.engine._post_review_items()
        accepted: list[PostReviewActionItem] = []
        now = time.time()
        for item in items:
            if item.id not in requested:
                continue
            if item.status in {PostReviewActionStatus.QUEUED, PostReviewActionStatus.DONE}:
                continue
            item.status = PostReviewActionStatus.ACCEPTED
            item.updated_at = now
            if note and note not in item.rationale:
                item.rationale = "\n".join(part for part in [item.rationale, note] if part)
            accepted.append(item)
        if not accepted:
            return ()

        package_ids = self.queue_supplemental_work_packages(
            accepted,
            active_agents=active_agents or self.engine.session.active_agents,
        )
        self.engine.session.post_review_items = [item.to_dict() for item in items]
        self.engine.session.updated_at = time.time()
        self.engine._persist(
            "post_review_items_accepted",
            {
                "action_item_ids": [item.id for item in accepted],
                "work_packages": list(package_ids),
            },
        )
        return package_ids

    def queue_supplemental_work_packages(
        self,
        items: Iterable[PostReviewActionItem],
        *,
        active_agents: list[str] | None = None,
    ) -> tuple[str, ...]:
        selected = [item for item in items if item.requires_execution]
        if not selected:
            for item in items:
                item.status = PostReviewActionStatus.DONE
                item.updated_at = time.time()
            return ()

        agents = list(active_agents or self.engine.session.active_agents)
        self.engine.session.supplemental_round += 1
        supplemental_round = self.engine.session.supplemental_round
        created_ids: list[str] = []
        for index, item in enumerate(selected):
            package_id = self.engine._next_supplemental_package_id()
            owner = self.engine._owner_for_post_review_item(item, agents, index)
            related = [
                package_id
                for package_id in item.related_wp_ids
                if self.engine._work_package_by_id(package_id) is not None
            ]
            package = WorkPackage(
                id=package_id,
                title=item.title or f"Post-review follow-up {item.id}",
                owner_agent=owner,
                objective=self.engine._supplemental_objective(item),
                scope=[item.summary] if item.summary else [],
                dependencies=related,
                acceptance_criteria=[
                    item.summary or item.title or f"Complete action item {item.id}."
                ],
                status=WorkStatus.PENDING,
                requires_execution=True,
                risk=item.severity or "medium",
                origin="post_review_followup",
                origin_action_item_ids=[item.id],
                parent_package_ids=related,
                supplemental_round=supplemental_round,
            )
            self.engine.session.work_packages.append(package)
            item.status = PostReviewActionStatus.QUEUED
            item.updated_at = time.time()
            created_ids.append(package.id)

        run = (
            dict(self.engine.session.execution_run)
            if isinstance(self.engine.session.execution_run, dict)
            else {}
        )
        run.setdefault("run_id", f"exec-run-{uuid4().hex[:12]}")
        run["state"] = "supplemental_queued"
        run["kind"] = "supplemental"
        run["source"] = "post_review_followup"
        run["round"] = supplemental_round
        run["package_ids"] = list(created_ids)
        run["action_item_ids"] = [item.id for item in selected]
        run["target_workspace"] = str(self.engine.session.target_workspace or "")
        self.engine.session.execution_run = run
        self.engine.session.updated_at = time.time()
        self.engine.set_state(
            WorkflowState.BLUEPRINT_READY,
            reason="post-review supplemental work packages queued",
        )
        return tuple(created_ids)

    def post_review_summary(self) -> str:
        items = self.engine._post_review_items()
        if not items:
            return (
                "Final review is complete. No post-review action items were extracted. "
                "Use /improve done to close."
            )
        lines = ["Post-review action items:"]
        for item in items:
            lines.append(
                f"- {item.id} [{item.severity}][{item.status.value}] "
                f"{item.title or item.summary}"
            )
        lines.append("Use /improve high, /improve all, /improve AI-001, or /improve done.")
        return "\n".join(lines)

    def mark_items_done(self, item_ids: Iterable[str]) -> None:
        ids = {str(item_id).strip() for item_id in item_ids if str(item_id).strip()}
        if not ids:
            return
        changed = False
        items = self.engine._post_review_items()
        for item in items:
            if item.id in ids:
                item.status = PostReviewActionStatus.DONE
                item.updated_at = time.time()
                changed = True
        if changed:
            self.engine.session.post_review_items = [item.to_dict() for item in items]

    def _auto_replan_final_review_changes(
        self,
        final_result: ReviewResult | None,
        created_items: Iterable[PostReviewActionItem],
    ) -> tuple[str, ...]:
        if final_result is None or final_result.status != ReviewStatus.CHANGES_REQUESTED:
            return ()

        candidate_ids = [
            item.id
            for item in created_items
            if item.source == "final_review"
            and final_result.review_package_id in item.related_review_ids
            and item.requires_execution
            and item.kind in {"bugfix", "validation"}
        ]
        if not candidate_ids:
            return ()

        if self.engine.session.target_workspace is None:
            self.engine._persist(
                "post_review_auto_replan_skipped",
                {
                    "review_package_id": final_result.review_package_id,
                    "reason": "target_workspace_missing",
                    "action_item_ids": list(candidate_ids),
                },
            )
            return ()

        package_ids = self.accept_post_review_items(
            candidate_ids,
            note="auto replanned from final review changes",
            active_agents=self.engine.session.active_agents,
        )
        if not package_ids:
            return ()

        run = (
            dict(self.engine.session.execution_run)
            if isinstance(self.engine.session.execution_run, dict)
            else {}
        )
        run["source"] = "final_review_auto_replan"
        run["auto_replanned_from_review"] = final_result.review_package_id
        run["auto_replanned_action_item_ids"] = list(candidate_ids)
        self.engine.session.execution_run = run
        self.engine.session.updated_at = time.time()
        self.engine._persist(
            "post_review_auto_replan_queued",
            {
                "review_package_id": final_result.review_package_id,
                "action_item_ids": list(candidate_ids),
                "work_packages": list(package_ids),
            },
        )
        return tuple(package_ids)
