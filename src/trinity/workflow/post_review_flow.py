"""Post-review flow helpers for WorkflowEngine."""

from __future__ import annotations

import time
import re
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
    FINAL_REVIEW_PACKAGE_ID,
    ReviewResult,
    ReviewStatus,
)
from trinity.workflow.post_review_selection import (
    looks_like_post_review_selector,
    select_post_review_items,
)


class WorkflowPostReviewFlow:
    """Final-review follow-up and supplemental work package entrypoints."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine

    def finalize_post_review(self, final_result: ReviewResult | None = None) -> None:
        created = self.extract_post_review_items(final_result)
        self.engine.session.updated_at = time.time()
        self.engine._persistence_flow().persist(
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
        existing = self._post_review_items()
        existing_keys = {self._post_review_item_key(item) for item in existing}
        created: list[PostReviewActionItem] = []
        reviews = list(self.engine.review_results)
        if final_result is not None and not any(
            item.review_package_id == final_result.review_package_id
            and item.package_id == final_result.package_id
            for item in reviews
        ):
            reviews.append(final_result)

        for review in reviews:
            candidates = self._post_review_candidates_from_review(review)
            for candidate in candidates:
                key = self._post_review_item_key(candidate)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                candidate.id = self._next_post_review_item_id([*existing, *created])
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
        instruction = self._normalize_improve_instruction(text)
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

        if self._is_post_review_done_command(instruction):
            self._record_follow_up_request(
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

        selected = self._select_post_review_items(instruction)
        created_from_text = False
        if not selected and not self._looks_like_post_review_selector(instruction):
            item = self._create_user_request_action_item(instruction)
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
        self._record_follow_up_request(instruction, selected, source_state=source_state)
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
        items = self._post_review_items()
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
        self.engine._persistence_flow().persist(
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
            package_id = self._next_supplemental_package_id()
            owner = self._owner_for_post_review_item(item, agents, index)
            related = [
                package_id
                for package_id in item.related_wp_ids
                if (
                    self.engine._collection_flow().work_package_by_id(package_id)
                    is not None
                )
            ]
            package = WorkPackage(
                id=package_id,
                title=item.title or f"Post-review follow-up {item.id}",
                owner_agent=owner,
                objective=self._supplemental_objective(item),
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
        items = self._post_review_items()
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
        items = self._post_review_items()
        for item in items:
            if item.id in ids:
                item.status = PostReviewActionStatus.DONE
                item.updated_at = time.time()
                changed = True
        if changed:
            self.engine.session.post_review_items = [item.to_dict() for item in items]

    def _post_review_items(self) -> list[PostReviewActionItem]:
        items: list[PostReviewActionItem] = []
        for item in self.engine.session.post_review_items:
            if not isinstance(item, dict):
                continue
            try:
                items.append(PostReviewActionItem.from_dict(item))
            except (TypeError, ValueError):
                continue
        return items

    def _post_review_candidates_from_review(
        self,
        review: ReviewResult,
    ) -> list[PostReviewActionItem]:
        candidates: list[PostReviewActionItem] = []
        is_final = review.scope == "final" or review.package_id == FINAL_REVIEW_PACKAGE_ID
        source = "final_review" if is_final else "wp_review"
        related_wp_ids = [] if is_final else [review.package_id]
        suggested_owner = "" if is_final else self._owner_for_related_package(review.package_id)

        for change in review.required_changes:
            candidates.append(
                self._new_post_review_item(
                    source=source,
                    kind="bugfix",
                    severity=review.severity or "high",
                    summary=change,
                    review=review,
                    related_wp_ids=related_wp_ids,
                    suggested_owner=suggested_owner,
                    rationale=review.summary,
                )
            )
        for risk in review.execution_risks:
            candidates.append(
                self._new_post_review_item(
                    source=source,
                    kind="validation",
                    severity=review.severity or "high",
                    summary=risk,
                    review=review,
                    related_wp_ids=related_wp_ids,
                    suggested_owner=suggested_owner,
                    rationale=review.summary,
                )
            )
        if is_final:
            for follow_up in review.follow_up:
                candidates.append(
                    self._new_post_review_item(
                        source=source,
                        kind="enhancement",
                        severity=self._downgrade_optional_severity(review.severity),
                        summary=follow_up,
                        review=review,
                        related_wp_ids=[],
                        suggested_owner="",
                        rationale=review.summary,
                    )
                )
        return [item for item in candidates if item.summary.strip()]

    def _new_post_review_item(
        self,
        *,
        source: str,
        kind: str,
        severity: str,
        summary: str,
        review: ReviewResult,
        related_wp_ids: list[str],
        suggested_owner: str,
        rationale: str = "",
    ) -> PostReviewActionItem:
        return PostReviewActionItem(
            id="",
            source=source,
            kind=kind,
            severity=self._normalize_severity(severity),
            title=self._action_title(summary),
            summary=summary.strip(),
            rationale=rationale.strip(),
            related_wp_ids=list(related_wp_ids),
            related_review_ids=[review.review_package_id],
            suggested_owner=suggested_owner,
            requires_execution=True,
        )

    def _create_user_request_action_item(self, instruction: str) -> PostReviewActionItem:
        return PostReviewActionItem(
            id=self._next_post_review_item_id(self._post_review_items()),
            source="user_request",
            kind="enhancement",
            severity="medium",
            title=self._action_title(instruction),
            summary=instruction.strip(),
            rationale="User requested additional post-review improvement.",
            requires_execution=True,
        )

    @staticmethod
    def _post_review_item_key(item: PostReviewActionItem) -> tuple[str, str, tuple[str, ...]]:
        normalized = " ".join(item.summary.strip().lower().split())
        return (item.source, normalized, tuple(sorted(item.related_wp_ids)))

    @staticmethod
    def _normalize_improve_instruction(text: str) -> str:
        instruction = text.strip()
        if instruction.lower().startswith("/improve"):
            instruction = instruction[len("/improve") :].strip()
        return instruction

    @staticmethod
    def _is_post_review_done_command(instruction: str) -> bool:
        return instruction.strip().lower() in {
            "done",
            "complete",
            "close",
            "finish",
            "완료",
            "종료",
            "끝",
            "닫기",
        }

    def _select_post_review_items(self, instruction: str) -> list[str]:
        return select_post_review_items(instruction, self._post_review_items())

    @staticmethod
    def _looks_like_post_review_selector(instruction: str) -> bool:
        return looks_like_post_review_selector(instruction)

    def _next_post_review_item_id(
        self,
        existing: Iterable[PostReviewActionItem],
    ) -> str:
        used: set[int] = set()
        for item in existing:
            match = re.fullmatch(r"AI-(\d+)", item.id.strip().upper())
            if match:
                used.add(int(match.group(1)))
        index = 1
        while index in used:
            index += 1
        return f"AI-{index:03d}"

    def _next_supplemental_package_id(self) -> str:
        used: set[int] = set()
        for package in self.engine.session.work_packages:
            match = re.fullmatch(r"WP-S(\d+)", package.id.strip().upper())
            if match:
                used.add(int(match.group(1)))
        index = 1
        while index in used:
            index += 1
        return f"WP-S{index:03d}"

    def _owner_for_post_review_item(
        self,
        item: PostReviewActionItem,
        active_agents: list[str],
        index: int,
    ) -> str:
        agents = [agent for agent in active_agents if agent]
        if item.suggested_owner and (not agents or item.suggested_owner in agents):
            return item.suggested_owner
        for package_id in item.related_wp_ids:
            owner = self._owner_for_related_package(package_id)
            if owner and (not agents or owner in agents):
                return owner
        if agents:
            return agents[index % len(agents)]
        return item.suggested_owner or "codex"

    def _owner_for_related_package(self, package_id: str) -> str:
        package = self.engine._collection_flow().work_package_by_id(package_id)
        if package is None:
            return ""
        return package.last_executor or package.owner_agent

    def _record_follow_up_request(
        self,
        text: str,
        accepted_action_item_ids: Iterable[str],
        *,
        source_state: str | None = None,
    ) -> None:
        existing = self.engine.session.follow_up_requests
        request = {
            "id": f"fur-{len(existing) + 1:03d}",
            "text": text,
            "source_state": source_state or self.engine.session.state.value,
            "created_at": time.time(),
            "accepted_action_item_ids": [
                str(item_id) for item_id in accepted_action_item_ids
            ],
        }
        self.engine.session.follow_up_requests.append(request)
        self.engine.session.updated_at = time.time()
        self.engine._persistence_flow().persist(
            "post_review_follow_up_requested",
            request,
        )

    @staticmethod
    def _supplemental_objective(item: PostReviewActionItem) -> str:
        parts = [
            f"Post-review action item {item.id}: {item.summary}",
            f"Source: {item.source}",
            f"Kind: {item.kind}",
            f"Severity: {item.severity}",
        ]
        if item.rationale:
            parts.append(f"Rationale: {item.rationale}")
        if item.related_wp_ids:
            parts.append(f"Related work packages: {', '.join(item.related_wp_ids)}")
        return "\n".join(parts)

    @staticmethod
    def _action_title(value: str, limit: int = 80) -> str:
        text = " ".join(value.strip().split())
        if not text:
            return "Post-review follow-up"
        sentence = re.split(r"[.!?\n]", text, maxsplit=1)[0].strip() or text
        if len(sentence) <= limit:
            return sentence
        return sentence[: limit - 3].rstrip() + "..."

    @staticmethod
    def _normalize_severity(value: str) -> str:
        normalized = str(value or "medium").strip().lower()
        return normalized if normalized in {"low", "medium", "high", "critical"} else "medium"

    @classmethod
    def _downgrade_optional_severity(cls, value: str) -> str:
        severity = cls._normalize_severity(value)
        if severity == "critical":
            return "high"
        if severity == "high":
            return "medium"
        return severity

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
            self.engine._persistence_flow().persist(
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
        self.engine._persistence_flow().persist(
            "post_review_auto_replan_queued",
            {
                "review_package_id": final_result.review_package_id,
                "action_item_ids": list(candidate_ids),
                "work_packages": list(package_ids),
            },
        )
        return tuple(package_ids)
