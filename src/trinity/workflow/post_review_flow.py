"""Post-review flow helpers for WorkflowEngine."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any
from uuid import uuid4

from trinity.workflow.models import (
    PostReviewActionItem,
    PostReviewActionStatus,
    WorkPackage,
    WorkStatus,
    WorkflowState,
)
from trinity.workflow.review import (
    ReviewResult,
    ReviewStatus,
)


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
