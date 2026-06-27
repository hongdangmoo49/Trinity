"""Review flow helpers for WorkflowEngine."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from trinity.workflow.models import (
    WorkPackage,
    WorkStatus,
    WorkflowState,
)
from trinity.workflow.review import (
    FINAL_REVIEW_PACKAGE_ID,
    PeerReviewPlanner,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
)
from trinity.workflow.review_repair_metadata import (
    ReviewRepairEventMetadata,
    review_repair_metadata_from_events,
)
from trinity.workflow.targeting_flow import WorkflowTargetingFlow


class WorkflowReviewFlow:
    """Review planning, result recording, and repair-loop entrypoints."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def ensure_review_packages(self) -> list[ReviewPackage]:
        session = self.engine.session
        if not session.review_packages and session.work_packages:
            self._plan_review_packages()
            session.updated_at = time.time()
            self.engine._persistence_flow().persist(
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
            if not explicit and self._review_package_is_approved(review):
                continue
            reviews.append(review)
        return reviews

    def _plan_review_packages(self) -> None:
        """Create peer review packages for completed execution results."""
        planner = PeerReviewPlanner()
        session = self.engine.session
        reviewable_packages = [
            package
            for package in session.work_packages
            if package.requires_execution
            and package.status in {WorkStatus.DONE, WorkStatus.NEEDS_REVIEW}
            and not self._latest_review_is_approved(package.id)
        ]
        reviews = planner.plan_reviews(
            reviewable_packages,
            WorkflowTargetingFlow.decomposition_agents(
                self.engine.agent_specs,
                self.engine.session.active_agents,
            ),
            session.execution_results,
        )
        session.review_packages = [review.to_dict() for review in reviews]

    def _latest_review_is_approved(self, package_id: str) -> bool:
        planned = [
            review
            for review in self._planned_review_packages()
            if review.package_id == package_id
            and review.scope != "final"
            and review.package_id != FINAL_REVIEW_PACKAGE_ID
            and review.required
        ]
        if planned:
            return all(self._review_package_is_approved(review) for review in planned)

        for result in reversed(self._review_results()):
            if result.package_id == package_id and result.scope != "final":
                return result.status == ReviewStatus.APPROVED
        return False

    def _review_package_is_approved(self, review: ReviewPackage) -> bool:
        for result in reversed(self._review_results()):
            if result.review_package_id == review.id:
                return result.status == ReviewStatus.APPROVED
            if (
                result.package_id == review.package_id
                and result.reviewer_agent == review.reviewer_agent
                and result.target_agent == review.target_agent
                and result.scope == review.scope
            ):
                return result.status == ReviewStatus.APPROVED
        return False

    def _planned_review_packages(self) -> list[ReviewPackage]:
        reviews: list[ReviewPackage] = []
        for item in self.engine.session.review_packages:
            if not isinstance(item, dict):
                continue
            try:
                reviews.append(ReviewPackage.from_dict(item))
            except (TypeError, ValueError):
                continue
        return reviews

    def _review_results(self) -> list[ReviewResult]:
        reviews: list[ReviewResult] = []
        for item in self.engine.session.review_results:
            if not isinstance(item, dict):
                continue
            try:
                reviews.append(ReviewResult.from_dict(item))
            except (TypeError, ValueError):
                continue
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
            self.record_review_result(result)
        if finalize:
            self.finalize_review_state(review_results)

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
            package = self.engine._collection_flow().work_package_by_id(
                result.package_id
            )
            if package is None or not package.requires_execution:
                continue
            if package.id not in repair_requests:
                repair_requests[package.id] = (package, [])
            repair_requests[package.id][1].append(result)

        for package, package_results in repair_requests.values():
            result = package_results[-1]
            required_changes = self._merged_review_repair_changes(package_results)
            signature = self._review_repair_signature_from_parts(
                package.id,
                self._review_repair_target_agent(package, package_results),
                required_changes,
            )
            if package.repair_attempt_count >= max_attempts:
                blocked.append(
                    self.block_review_repair(
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
                    self.block_review_repair(
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
            self.engine._persistence_flow().persist(
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
        self.engine._persistence_flow().persist(
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
        event_metadata = self._review_repair_metadata_from_events()
        if not event_metadata:
            return ()

        latest_change_by_package: dict[str, ReviewResult] = {}
        for result in self._review_results():
            if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            if result.status == ReviewStatus.CHANGES_REQUESTED:
                latest_change_by_package[result.package_id] = result

        changed = False
        blocked: list[str] = []
        for package in self.engine.session.work_packages:
            metadata = event_metadata.get(package.id, ReviewRepairEventMetadata())
            attempts = metadata.attempt_count
            if attempts <= 0:
                continue
            if package.repair_attempt_count < attempts:
                package.repair_attempt_count = attempts
                changed = True
            event_signature = metadata.repair_signature
            event_review_id = metadata.review_package_id
            if event_signature and not package.last_repair_signature:
                package.last_repair_signature = event_signature
                package.last_repair_review_id = event_review_id
                changed = True
            latest_change = latest_change_by_package.get(package.id)
            if latest_change is not None and not package.last_repair_signature:
                package.last_repair_signature = self._review_repair_signature(
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
                self.engine._persistence_flow().persist(
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

    def _review_repair_metadata_from_events(
        self,
    ) -> dict[str, ReviewRepairEventMetadata]:
        return review_repair_metadata_from_events(
            self.engine.persistence.load_events_for_workflow(
                self.engine.session.id,
                event_names={"work_package_repair_requested"},
            )
        )

    @classmethod
    def _review_repair_signature(cls, result: ReviewResult) -> str:
        return cls._review_repair_signature_from_parts(
            result.package_id,
            result.target_agent,
            result.required_changes,
        )

    @classmethod
    def _review_repair_signature_from_parts(
        cls,
        package_id: str,
        target_agent: str,
        required_changes: Iterable[str],
    ) -> str:
        changes = [
            normalized
            for normalized in (
                cls._normalize_repair_change(change) for change in required_changes
            )
            if normalized
        ]
        payload = {
            "package_id": package_id,
            "target_agent": target_agent,
            "required_changes": sorted(set(changes)),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _merged_review_repair_changes(
        cls,
        results: Iterable[ReviewResult],
    ) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for result in results:
            for change in result.required_changes:
                normalized = cls._normalize_repair_change(change)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged

    @staticmethod
    def _review_repair_target_agent(
        package: WorkPackage,
        results: Iterable[ReviewResult],
    ) -> str:
        targets = {
            str(result.target_agent).strip()
            for result in results
            if str(result.target_agent).strip()
        }
        if len(targets) == 1:
            return next(iter(targets))
        if targets:
            return ",".join(sorted(targets))
        return package.owner_agent

    @staticmethod
    def _normalize_repair_change(change: str) -> str:
        return re.sub(r"\s+", " ", str(change).strip())

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
            self.engine._persistence_flow().persist(
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
        self.engine._persistence_flow().persist(
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

    def block_review_repair(
        self,
        package: WorkPackage,
        result: ReviewResult,
        *,
        reason: str,
        signature: str,
        max_attempts: int,
        required_changes: Iterable[str] | None = None,
        review_package_ids: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        previous_status = package.status.value
        package.status = WorkStatus.BLOCKED
        package.current_executor = ""
        package.last_repair_signature = signature
        package.last_repair_review_id = result.review_package_id
        package.repair_blocked_reason = reason
        package.repair_blocked_at = time.time()
        payload = {
            "package_id": package.id,
            "previous_status": previous_status,
            "reason": reason,
            "review_package_id": result.review_package_id,
            "review_package_ids": (
                list(review_package_ids)
                if review_package_ids is not None
                else [result.review_package_id]
            ),
            "reviewer": result.reviewer_agent,
            "target": result.target_agent,
            "required_changes": (
                list(required_changes)
                if required_changes is not None
                else list(result.required_changes)
            ),
            "repair_attempt_count": package.repair_attempt_count,
            "max_attempts": max_attempts,
            "repair_signature": signature,
        }
        self.engine._persistence_flow().persist(
            "work_package_repair_blocked",
            payload,
        )
        return payload

    def record_review_result(self, result: ReviewResult) -> None:
        session = self.engine.session
        session.review_results.append(result.to_dict())
        self.apply_review_result_to_package(result)
        self.engine._quality_flow().record_review_quality(result)
        session.updated_at = time.time()
        self.engine._persistence_flow().persist(
            "review_result_recorded",
            {
                "review_package_id": result.review_package_id,
                "package_id": result.package_id,
                "reviewer": result.reviewer_agent,
                "target": result.target_agent,
                "status": result.status.value,
                "severity": result.severity,
                "scope": result.scope,
                "quality_signal": (
                    session.quality_signals[-1] if session.quality_signals else {}
                ),
            },
        )

    def apply_review_result_to_package(self, result: ReviewResult) -> None:
        if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID:
            return
        package = self.engine._collection_flow().work_package_by_id(result.package_id)
        if package is None:
            return
        if result.status == ReviewStatus.APPROVED:
            if package.status == WorkStatus.NEEDS_REVIEW:
                package.status = WorkStatus.DONE
            return
        if result.status == ReviewStatus.CHANGES_REQUESTED:
            package.status = WorkStatus.NEEDS_REVIEW
            for change in result.required_changes:
                note = f"review {result.review_package_id}: {change}"
                if note not in package.repair_notes:
                    package.repair_notes.append(note)
            return
        if result.status == ReviewStatus.BLOCKED:
            package.status = WorkStatus.BLOCKED
            return
        if result.status == ReviewStatus.FAILED:
            package.status = WorkStatus.FAILED

    def finalize_review_state(self, latest_results: list[ReviewResult]) -> None:
        final_results = [
            result
            for result in latest_results
            if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID
        ]
        if final_results:
            final = final_results[-1]
            if final.status in {
                ReviewStatus.APPROVED,
                ReviewStatus.CHANGES_REQUESTED,
            }:
                self.engine.finalize_post_review(final)
            elif final.status == ReviewStatus.BLOCKED:
                self.engine.set_state(
                    WorkflowState.NEEDS_USER_DECISION,
                    reason="final review blocked",
                )
            else:
                self.engine.set_state(WorkflowState.FAILED, reason="final review failed")
            return

        if any(result.status == ReviewStatus.FAILED for result in latest_results):
            self.engine.set_state(
                WorkflowState.FAILED,
                reason="work package review failed",
            )
            return
        if any(result.status == ReviewStatus.BLOCKED for result in latest_results):
            self.engine.set_state(
                WorkflowState.NEEDS_USER_DECISION,
                reason="work package review blocked",
            )
            return
        if any(result.status == ReviewStatus.CHANGES_REQUESTED for result in latest_results):
            self.engine.set_state(
                WorkflowState.REVIEWING,
                reason="work package review requested changes",
            )
            return
        self.engine.set_state(WorkflowState.REVIEWING, reason="work package review completed")
