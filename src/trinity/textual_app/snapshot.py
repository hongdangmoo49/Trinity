"""Read-only workflow snapshot projection for Textual screens."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from trinity.config import TrinityConfig
from trinity.context.shared import SharedContextEngine
from trinity.tui.events import TUIEvent, TUIEventType
from trinity.workflow import (
    FINAL_REVIEW_PACKAGE_ID,
    PostReviewActionItem,
    ReviewPackage,
    ReviewResult,
    WorkflowPersistence,
    WorkflowSession,
)


@dataclass(frozen=True)
class ProviderSnapshot:
    """Projected provider state for Textual UI."""

    name: str
    provider: str
    enabled: bool
    status: str
    summary: str = ""
    readiness: str = "unknown"
    readiness_reason: str = ""
    raw_output: str = ""
    configured_model: str = ""
    actual_model: str = ""
    model_label: str = ""
    context_window: int = 0
    budget_source: str = ""
    session_id: str = ""
    session_kind: str = ""


@dataclass(frozen=True)
class SynthesisSnapshot:
    """Projected central synthesis state."""

    summary: str = ""
    consensus_progress: str = ""
    source: str = "none"
    status: str = "idle"


@dataclass(frozen=True)
class QuestionSnapshot:
    """Projected user question for interactive synthesis."""

    id: str
    question: str
    options: list[str] = field(default_factory=list)
    recommended_option: str = ""
    status: str = "open"
    answer: str = ""


@dataclass(frozen=True)
class SubtaskSnapshot:
    """Projected provider-internal delegation result."""

    id: str
    parent_package_id: str
    parent_agent: str
    delegated_to: str
    objective: str
    result_summary: str
    status: str


@dataclass(frozen=True)
class LocalCommandSnapshot:
    """A locally handled slash command result for Textual display."""

    command: str
    title: str
    body: str
    severity: str = "info"
    result_kind: str = "markdown"
    empty: bool = False
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class WorkPackageSnapshot:
    """Projected work package state for execution UIs."""

    id: str
    title: str
    owner_agent: str
    status: str
    risk: str = "unknown"
    current_executor: str = ""
    last_executor: str = ""
    objective: str = ""
    scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    expected_files: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    requires_execution: bool = True
    estimated_weight: int = 1
    parallel_group: int | None = None
    parallelizable: bool = True
    repair_notes: list[str] = field(default_factory=list)
    repair_attempt_count: int = 0
    repair_max_attempts: int = 0
    repair_blocked_reason: str = ""
    repair_blocked_at: float = 0.0
    last_result_agent: str = ""
    last_result_status: str = ""
    last_result_summary: str = ""
    last_result_files_changed: list[str] = field(default_factory=list)
    last_result_blockers: list[str] = field(default_factory=list)
    retryable: bool = False
    retry_disabled_reason: str = ""
    topic: str = ""
    review_status: str = ""
    reviewer_agent: str = ""
    review_summary: str = ""
    review_required_changes: list[str] = field(default_factory=list)
    review_severity: str = ""


@dataclass(frozen=True)
class ReviewSnapshot:
    """Projected review result state for Textual UI."""

    review_package_id: str = ""
    package_id: str = ""
    reviewer_agent: str = ""
    target_agent: str = ""
    status: str = ""
    severity: str = ""
    scope: str = ""
    summary: str = ""
    findings: list[str] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)
    follow_up: list[str] = field(default_factory=list)
    reviewed_files: list[str] = field(default_factory=list)
    compatibility_notes: list[str] = field(default_factory=list)
    performance_notes: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    execution_risks: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _ReviewProjection:
    """Aggregated per-work-package review state for compact UI surfaces."""

    status: str = ""
    reviewer_agent: str = ""
    summary: str = ""
    required_changes: list[str] = field(default_factory=list)
    severity: str = ""


@dataclass(frozen=True)
class PostReviewActionSnapshot:
    """Projected review follow-up item for Textual UI."""

    id: str = ""
    source: str = ""
    kind: str = ""
    severity: str = ""
    title: str = ""
    summary: str = ""
    status: str = ""
    suggested_owner: str = ""
    requires_execution: bool = True
    related_wp_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionRecoverySnapshot:
    """Projected execution run/recovery state."""

    run_id: str = ""
    state: str = ""
    target_workspace: str = ""
    running_packages: tuple[str, ...] = ()
    done_packages: tuple[str, ...] = ()
    retry_candidates: tuple[str, ...] = ()
    last_event: str = ""
    last_event_at: float | None = None
    interrupted_reason: str = ""


@dataclass(frozen=True)
class WorkflowNexusSnapshot:
    """Read-only UI projection of the current workflow."""

    session_id: str = ""
    goal: str = ""
    state: str = "idle"
    round_num: int = 0
    target_workspace: str = ""
    providers: list[ProviderSnapshot] = field(default_factory=list)
    synthesis: SynthesisSnapshot = field(default_factory=SynthesisSnapshot)
    questions: list[QuestionSnapshot] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    central_blueprint: str = ""
    central_work_packages: list[str] = field(default_factory=list)
    work_packages: list[str] = field(default_factory=list)
    work_package_details: list[WorkPackageSnapshot] = field(default_factory=list)
    subtasks: list[SubtaskSnapshot] = field(default_factory=list)
    work_package_repairs: list[str] = field(default_factory=list)
    workflow_events: list[str] = field(default_factory=list)
    execution_log: list[str] = field(default_factory=list)
    execution_recovery: ExecutionRecoverySnapshot | None = None
    final_review: ReviewSnapshot | None = None
    post_review_items: list[PostReviewActionSnapshot] = field(default_factory=list)
    follow_up_requests: list[str] = field(default_factory=list)
    supplemental_round: int = 0
    local_commands: list[LocalCommandSnapshot] = field(default_factory=list)


class NexusSnapshotAdapter:
    """Build a read-only Nexus snapshot from persisted Trinity state."""

    def __init__(self, config: TrinityConfig) -> None:
        self.config = config
        self.persistence = WorkflowPersistence(config.effective_state_dir)
        self.shared = SharedContextEngine(
            config.shared_context_path,
            max_read_bytes=config.shared_max_bytes,
            section_entry_max_chars=config.shared_section_entry_max_chars,
            memory_index_enabled=config.memory_index_enabled,
        )
        self._cached_snapshot_key: tuple[object, ...] | None = None
        self._cached_snapshot: WorkflowNexusSnapshot | None = None

    def new_session_snapshot(self, goal: str) -> WorkflowNexusSnapshot:
        """Create a fresh in-memory snapshot for a newly submitted UI prompt."""
        return WorkflowNexusSnapshot(
            session_id=f"wf-{uuid4().hex[:12]}",
            goal=goal.strip(),
            state="preflight",
            providers=list(self._provider_states(None).values()),
        )

    def load_snapshot(
        self,
        recent_events: Iterable[TUIEvent] = (),
    ) -> WorkflowNexusSnapshot:
        """Load a snapshot without mutating workflow/session state."""
        recent = list(recent_events)
        cache_key = self._make_snapshot_cache_key(recent)
        if (
            self._cached_snapshot_key == cache_key
            and self._cached_snapshot is not None
        ):
            return self._cached_snapshot

        session = self.persistence.load()
        session_events = (
            self.persistence.load_events_for_workflow(session.id) if session else []
        )
        provider_states = self._provider_states(session)
        self._fold_recent_events(provider_states, recent)
        round_num = self._round_num(session, recent)

        snapshot = WorkflowNexusSnapshot(
            session_id=session.id if session else "",
            goal=session.goal if session else "",
            state=session.state.value if session else "idle",
            round_num=round_num,
            target_workspace=str(session.target_workspace or "") if session else "",
            providers=list(provider_states.values()),
            synthesis=self._synthesis(session, recent, round_num),
            questions=self._questions(session),
            decisions=[d.decision for d in session.decisions] if session else [],
            central_blueprint=self._central_blueprint_markdown(session),
            central_work_packages=self._central_work_packages(session),
            work_packages=[
                self._work_package_line(package)
                for package in session.work_packages
            ]
            if session
            else [],
            work_package_details=self._work_package_details(session),
            subtasks=self._subtasks(session),
            work_package_repairs=self._work_package_repairs(session),
            workflow_events=self._workflow_events(session, session_events),
            execution_log=self._execution_log(session, session_events),
            execution_recovery=self._execution_recovery(session, session_events),
            final_review=self._final_review(session),
            post_review_items=self._post_review_items(session),
            follow_up_requests=self._follow_up_requests(session),
            supplemental_round=session.supplemental_round if session else 0,
        )
        self._cached_snapshot_key = cache_key
        self._cached_snapshot = snapshot
        return snapshot

    def _make_snapshot_cache_key(
        self,
        recent_events: list[TUIEvent],
    ) -> tuple[object, ...]:
        return (
            self._path_cache_key(self.persistence.session_path),
            self._path_cache_key(self.persistence.events_path),
            self._path_cache_key(
                self.config.shared_context_path,
                content_fingerprint_bytes=64_000,
            ),
            self._config_cache_key(),
            self._recent_events_cache_key(recent_events),
        )

    @staticmethod
    def _path_cache_key(
        path: Path,
        *,
        content_fingerprint_bytes: int = 0,
    ) -> tuple[str, int, int, int, str]:
        try:
            stat = path.stat()
        except OSError:
            return ("missing", 0, 0, 0, "")
        fingerprint = ""
        if content_fingerprint_bytes > 0 and stat.st_size <= content_fingerprint_bytes:
            try:
                fingerprint = hashlib.blake2b(
                    path.read_bytes(),
                    digest_size=8,
                ).hexdigest()
            except OSError:
                fingerprint = ""
        return ("file", stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, fingerprint)

    def _config_cache_key(self) -> tuple[object, ...]:
        agents = tuple(
            (
                name,
                spec.enabled,
                spec.provider.value,
                spec.cli_command,
                spec.model,
                spec.context_budget,
                tuple(spec.extra_args),
            )
            for name, spec in sorted(self.config.agents.items())
        )
        return (
            self.config.repair_max_attempts,
            self.config.shared_max_bytes,
            self.config.shared_section_entry_max_chars,
            self.config.memory_index_enabled,
            agents,
        )

    @staticmethod
    def _recent_events_cache_key(events: list[TUIEvent]) -> tuple[tuple[str, str], ...]:
        return tuple(
            (
                event.type.value,
                json.dumps(event.data, ensure_ascii=False, sort_keys=True, default=str),
            )
            for event in events
        )

    def _work_package_details(
        self,
        session: WorkflowSession | None,
    ) -> list[WorkPackageSnapshot]:
        if session is None:
            return []
        result_by_package_id = {result.package_id: result for result in session.execution_results}
        review_by_package_id = NexusSnapshotAdapter._work_package_review_projections(session)
        return [
            WorkPackageSnapshot(
                id=package.id,
                title=package.title,
                owner_agent=package.owner_agent,
                status=package.status.value,
                risk=package.risk or "unknown",
                current_executor=package.current_executor,
                last_executor=package.last_executor,
                objective=package.objective,
                scope=list(package.scope),
                out_of_scope=list(package.out_of_scope),
                dependencies=list(package.dependencies),
                expected_files=list(package.expected_files),
                acceptance_criteria=list(package.acceptance_criteria),
                requires_execution=package.requires_execution,
                estimated_weight=package.estimated_weight,
                parallel_group=package.parallel_group,
                parallelizable=package.parallelizable,
                repair_notes=list(package.repair_notes),
                repair_attempt_count=package.repair_attempt_count,
                repair_max_attempts=self.config.repair_max_attempts,
                repair_blocked_reason=package.repair_blocked_reason,
                repair_blocked_at=package.repair_blocked_at,
                last_result_agent=(
                    result_by_package_id[package.id].agent_name
                    if package.id in result_by_package_id
                    else ""
                ),
                last_result_status=(
                    result_by_package_id[package.id].status.value
                    if package.id in result_by_package_id
                    else ""
                ),
                last_result_summary=(
                    result_by_package_id[package.id].summary
                    if package.id in result_by_package_id
                    else ""
                ),
                last_result_files_changed=(
                    list(result_by_package_id[package.id].files_changed)
                    if package.id in result_by_package_id
                    else []
                ),
                last_result_blockers=(
                    list(result_by_package_id[package.id].blockers)
                    if package.id in result_by_package_id
                    else []
                ),
                retryable=NexusSnapshotAdapter._work_package_retryable(package),
                retry_disabled_reason=NexusSnapshotAdapter._work_package_retry_disabled_reason(
                    package
                ),
                topic=NexusSnapshotAdapter._work_package_topic(package),
                review_status=(
                    review_by_package_id[package.id].status
                    if package.id in review_by_package_id
                    else ""
                ),
                reviewer_agent=(
                    review_by_package_id[package.id].reviewer_agent
                    if package.id in review_by_package_id
                    else ""
                ),
                review_summary=(
                    review_by_package_id[package.id].summary
                    if package.id in review_by_package_id
                    else ""
                ),
                review_required_changes=(
                    list(review_by_package_id[package.id].required_changes)
                    if package.id in review_by_package_id
                    else []
                ),
                review_severity=(
                    review_by_package_id[package.id].severity
                    if package.id in review_by_package_id
                    else ""
                ),
            )
            for package in session.work_packages
        ]

    def _work_package_line(self, package: object) -> str:
        status = str(getattr(getattr(package, "status", ""), "value", "") or "unknown")
        line = (
            f"{getattr(package, 'id', '')} {getattr(package, 'owner_agent', '')}: "
            f"{getattr(package, 'title', '')} ({status})"
        )
        attempt_count = int(getattr(package, "repair_attempt_count", 0) or 0)
        blocked_reason = str(getattr(package, "repair_blocked_reason", "") or "")
        if attempt_count or blocked_reason:
            line = f"{line} repair {attempt_count}/{self.config.repair_max_attempts}"
        if blocked_reason:
            line = f"{line} blocked: {blocked_reason}"
        return line

    @staticmethod
    def _work_package_review_projections(
        session: WorkflowSession,
    ) -> dict[str, _ReviewProjection]:
        planned_by_package = NexusSnapshotAdapter._planned_work_package_reviews(session)
        result_by_package: dict[str, dict[str, ReviewResult]] = {}
        for result in NexusSnapshotAdapter._review_results(session):
            if result.scope == "final" or result.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            review_id = result.review_package_id or f"{result.package_id}:{result.reviewer_agent}"
            result_by_package.setdefault(result.package_id, {})[review_id] = result

        projections: dict[str, _ReviewProjection] = {}
        for package_id in set(planned_by_package) | set(result_by_package):
            planned = planned_by_package.get(package_id, [])
            results = list(result_by_package.get(package_id, {}).values())
            pending_status = NexusSnapshotAdapter._pending_review_status(session)
            status = pending_status
            if results:
                status = NexusSnapshotAdapter._aggregate_review_status(results)
                planned_ids = {review.id for review in planned if review.id}
                completed_ids = {
                    result.review_package_id for result in results if result.review_package_id
                }
                if (
                    status == "approved"
                    and planned_ids
                    and not planned_ids.issubset(completed_ids)
                ):
                    status = pending_status
            representative = NexusSnapshotAdapter._representative_review_result(results)
            projections[package_id] = _ReviewProjection(
                status=status,
                reviewer_agent=NexusSnapshotAdapter._reviewer_label(planned, results),
                summary=representative.summary if representative else "",
                required_changes=NexusSnapshotAdapter._review_required_changes(results),
                severity=NexusSnapshotAdapter._aggregate_review_severity(results),
            )
        return projections

    @staticmethod
    def _planned_work_package_reviews(
        session: WorkflowSession | None,
    ) -> dict[str, list[ReviewPackage]]:
        if session is None:
            return {}
        reviews: dict[str, list[ReviewPackage]] = {}
        for item in session.review_packages:
            if not isinstance(item, dict):
                continue
            try:
                review = ReviewPackage.from_dict(item)
            except (TypeError, ValueError):
                continue
            if review.scope == "final" or review.package_id == FINAL_REVIEW_PACKAGE_ID:
                continue
            reviews.setdefault(review.package_id, []).append(review)
        return reviews

    @staticmethod
    def _pending_review_status(session: WorkflowSession) -> str:
        state = str(getattr(getattr(session, "state", ""), "value", "") or "")
        return "reviewing" if state == "reviewing" else "queued"

    @staticmethod
    def _aggregate_review_status(results: list[ReviewResult]) -> str:
        if not results:
            return ""
        priority = {
            "failed": 5,
            "blocked": 4,
            "changes_requested": 3,
            "approved": 2,
            "pending": 1,
        }
        return max(
            (result.status.value for result in results),
            key=lambda status: priority.get(status, 0),
        )

    @staticmethod
    def _representative_review_result(results: list[ReviewResult]) -> ReviewResult | None:
        if not results:
            return None
        priority = {
            "failed": 5,
            "blocked": 4,
            "changes_requested": 3,
            "approved": 2,
            "pending": 1,
        }
        return max(results, key=lambda result: priority.get(result.status.value, 0))

    @staticmethod
    def _reviewer_label(
        planned: list[ReviewPackage],
        results: list[ReviewResult],
    ) -> str:
        names: list[str] = []
        for result in results:
            if result.reviewer_agent and result.reviewer_agent not in names:
                names.append(result.reviewer_agent)
        for review in planned:
            if review.reviewer_agent and review.reviewer_agent not in names:
                names.append(review.reviewer_agent)
        if len(names) <= 2:
            return ", ".join(names)
        return f"{', '.join(names[:2])}, +{len(names) - 2}"

    @staticmethod
    def _review_required_changes(results: list[ReviewResult]) -> list[str]:
        changes: list[str] = []
        for result in results:
            for change in result.required_changes:
                if change and change not in changes:
                    changes.append(change)
        return changes

    @staticmethod
    def _aggregate_review_severity(results: list[ReviewResult]) -> str:
        if not results:
            return ""
        priority = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }
        return max(
            (result.severity for result in results if result.severity),
            key=lambda severity: priority.get(severity, 0),
            default="",
        )

    @staticmethod
    def _review_results(session: WorkflowSession | None) -> list[ReviewResult]:
        if session is None:
            return []
        reviews: list[ReviewResult] = []
        for item in session.review_results:
            if not isinstance(item, dict):
                continue
            try:
                reviews.append(ReviewResult.from_dict(item))
            except (TypeError, ValueError):
                continue
        return reviews

    @staticmethod
    def _final_review(session: WorkflowSession | None) -> ReviewSnapshot | None:
        for review in reversed(NexusSnapshotAdapter._review_results(session)):
            if review.scope == "final" or review.package_id == FINAL_REVIEW_PACKAGE_ID:
                return NexusSnapshotAdapter._review_snapshot(review)
        return None

    @staticmethod
    def _review_snapshot(review: ReviewResult) -> ReviewSnapshot:
        return ReviewSnapshot(
            review_package_id=review.review_package_id,
            package_id=review.package_id,
            reviewer_agent=review.reviewer_agent,
            target_agent=review.target_agent,
            status=review.status.value,
            severity=review.severity,
            scope=review.scope,
            summary=review.summary,
            findings=list(review.findings),
            required_changes=list(review.required_changes),
            follow_up=list(review.follow_up),
            reviewed_files=list(review.reviewed_files),
            compatibility_notes=list(review.compatibility_notes),
            performance_notes=list(review.performance_notes),
            anti_patterns=list(review.anti_patterns),
            execution_risks=list(review.execution_risks),
        )

    @staticmethod
    def _post_review_items(
        session: WorkflowSession | None,
    ) -> list[PostReviewActionSnapshot]:
        if session is None:
            return []
        items: list[PostReviewActionSnapshot] = []
        for raw in session.post_review_items:
            if not isinstance(raw, dict):
                continue
            try:
                item = PostReviewActionItem.from_dict(raw)
            except (TypeError, ValueError):
                continue
            items.append(
                PostReviewActionSnapshot(
                    id=item.id,
                    source=item.source,
                    kind=item.kind,
                    severity=item.severity,
                    title=item.title,
                    summary=item.summary,
                    status=item.status.value,
                    suggested_owner=item.suggested_owner,
                    requires_execution=item.requires_execution,
                    related_wp_ids=tuple(item.related_wp_ids),
                )
            )
        return items

    @staticmethod
    def _follow_up_requests(session: WorkflowSession | None) -> list[str]:
        if session is None:
            return []
        requests: list[str] = []
        for item in session.follow_up_requests:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            request_id = str(item.get("id", "")).strip()
            if text:
                requests.append(f"{request_id or '(request)'}: {text}")
        return requests

    @staticmethod
    def _work_package_retryable(package: object) -> bool:
        if not bool(getattr(package, "requires_execution", True)):
            return False
        status = str(getattr(getattr(package, "status", ""), "value", ""))
        return status in {"running", "failed", "blocked"}

    @staticmethod
    def _work_package_retry_disabled_reason(package: object) -> str:
        if not bool(getattr(package, "requires_execution", True)):
            return "does not require execution"
        status = str(getattr(getattr(package, "status", ""), "value", ""))
        if status == "done":
            return "already done"
        if status == "needs_review":
            return "already needs review"
        if status in {"running", "failed", "blocked"}:
            return ""
        return f"status is {status or 'unknown'}"

    @staticmethod
    def _work_package_topic(package: object) -> str:
        title = str(getattr(package, "title", "")).strip()
        if title:
            return title
        objective = str(getattr(package, "objective", "")).strip()
        if objective:
            first_sentence = objective.split(".", 1)[0].strip()
            return first_sentence or objective
        return str(getattr(package, "id", "")).strip()

    def _execution_recovery(
        self,
        session: WorkflowSession | None,
        session_events: Iterable[dict[str, object]] | None = None,
    ) -> ExecutionRecoverySnapshot | None:
        if session is None or not isinstance(session.execution_run, dict):
            return None
        run = session.execution_run
        state = str(run.get("state", "") or "")
        if state not in {"running", "interrupted", "aborted", "repair_blocked"}:
            return None
        if state == "running" and session.state.value != "executing":
            return None
        running_packages = tuple(
            package.id
            for package in session.work_packages
            if package.requires_execution and package.status.value == "running"
        )
        retry_candidates = tuple(
            package.id
            for package in session.work_packages
            if package.requires_execution
            and package.status.value in {"running", "blocked", "failed"}
        )
        done_packages = tuple(
            package.id
            for package in session.work_packages
            if package.requires_execution and package.status.value == "done"
        )
        last_event = self._last_session_event(session, session_events)
        return ExecutionRecoverySnapshot(
            run_id=str(run.get("run_id", "") or ""),
            state=state,
            target_workspace=str(run.get("target_workspace") or session.target_workspace or ""),
            running_packages=running_packages,
            done_packages=done_packages,
            retry_candidates=retry_candidates,
            last_event=(str(last_event.get("event", "")) if last_event is not None else ""),
            last_event_at=(
                float(last_event.get("timestamp"))
                if last_event is not None and last_event.get("timestamp") is not None
                else None
            ),
            interrupted_reason=str(run.get("interrupted_reason", "") or ""),
        )

    @staticmethod
    def _central_work_packages(session: WorkflowSession | None) -> list[str]:
        if session is None or session.blueprint is None:
            return []
        return [
            NexusSnapshotAdapter._format_central_package(package)
            for package in session.blueprint.work_packages
        ]

    @staticmethod
    def _central_blueprint_markdown(session: WorkflowSession | None) -> str:
        if session is None or session.blueprint is None:
            return ""
        blueprint = session.blueprint
        lines: list[str] = []
        title = blueprint.title.strip()
        summary = blueprint.summary.strip()
        if title:
            lines.append(f"**{title}**")
        if summary:
            if lines:
                lines.append("")
            lines.append(summary)

        if blueprint.architecture:
            lines.extend(["", "#### Architecture"])
            for component in blueprint.architecture:
                owner = f" `{component.owner_agent}`" if component.owner_agent else ""
                dependencies = (
                    f" Dependencies: {', '.join(component.dependencies)}."
                    if component.dependencies
                    else ""
                )
                lines.append(
                    f"- **{component.name}**{owner}: "
                    f"{component.responsibility}{dependencies}"
                )

        NexusSnapshotAdapter._append_blueprint_list(
            lines,
            "Data Flow",
            blueprint.data_flow,
        )
        NexusSnapshotAdapter._append_blueprint_list(
            lines,
            "External Dependencies",
            blueprint.external_dependencies,
        )

        if blueprint.risks:
            lines.extend(["", "#### Risks"])
            for risk in blueprint.risks:
                owner = f" `{risk.owner_agent}`" if risk.owner_agent else ""
                mitigation = f" Mitigation: {risk.mitigation}" if risk.mitigation else ""
                lines.append(
                    f"- **{risk.severity}**{owner}: {risk.description}{mitigation}"
                )

        NexusSnapshotAdapter._append_blueprint_list(
            lines,
            "Acceptance Criteria",
            blueprint.acceptance_criteria,
        )

        if blueprint.open_questions:
            lines.extend(["", "#### Open Questions"])
            for question in blueprint.open_questions:
                options = (
                    f" Options: {', '.join(question.options)}."
                    if question.options
                    else ""
                )
                recommended = (
                    f" Recommended: {question.recommended_option}."
                    if question.recommended_option
                    else ""
                )
                lines.append(
                    f"- **{question.id}**: {question.question}{options}{recommended}"
                )

        return "\n".join(lines).strip()

    @staticmethod
    def _append_blueprint_list(
        lines: list[str],
        title: str,
        values: list[str],
    ) -> None:
        items = [item.strip() for item in values if item.strip()]
        if not items:
            return
        lines.extend(["", f"#### {title}"])
        lines.extend(f"- {item}" for item in items)

    @staticmethod
    def _work_package_repairs(session: WorkflowSession | None) -> list[str]:
        if session is None:
            return []
        repairs: list[str] = []
        for package in session.work_packages:
            for note in package.repair_notes:
                repairs.append(f"{package.id}: {note}")
            if package.repair_blocked_reason:
                repairs.append(
                    f"{package.id}: blocked after "
                    f"{package.repair_attempt_count} repair attempts "
                    f"({package.repair_blocked_reason})"
                )
        return repairs[-8:]

    @staticmethod
    def _subtasks(session: WorkflowSession | None) -> list[SubtaskSnapshot]:
        if session is None:
            return []

        subtasks: list[SubtaskSnapshot] = []
        seen: set[tuple[str, str, str]] = set()

        def add(subtask: object) -> None:
            subtask_id = str(getattr(subtask, "id", "")).strip()
            parent_package_id = str(getattr(subtask, "parent_package_id", "")).strip()
            parent_agent = str(getattr(subtask, "parent_agent", "")).strip()
            key = (subtask_id, parent_package_id, parent_agent)
            if key in seen:
                return
            seen.add(key)
            status = getattr(getattr(subtask, "status", ""), "value", "")
            if not status:
                status = getattr(subtask, "status", "")
            subtasks.append(
                SubtaskSnapshot(
                    id=subtask_id,
                    parent_package_id=parent_package_id,
                    parent_agent=parent_agent,
                    delegated_to=str(getattr(subtask, "delegated_to", "")).strip(),
                    objective=str(getattr(subtask, "objective", "")).strip(),
                    result_summary=str(getattr(subtask, "result_summary", "")).strip(),
                    status=str(status).strip() or "unknown",
                )
            )

        for subtask in session.subtask_results:
            add(subtask)
        for result in session.execution_results:
            for subtask in result.subtasks:
                add(subtask)
        return subtasks

    @staticmethod
    def _format_central_package(package: object) -> str:
        package_id = str(getattr(package, "id", "")).strip()
        owner = str(getattr(package, "owner_agent", "")).strip() or "unassigned"
        title = str(getattr(package, "title", "")).strip() or "Untitled package"
        dependencies = [
            str(item).strip() for item in getattr(package, "dependencies", []) if str(item).strip()
        ]
        expected_files = [
            str(item).strip()
            for item in getattr(package, "expected_files", [])
            if str(item).strip()
        ]
        details = [
            f"deps={','.join(dependencies) if dependencies else '-'}",
            f"files={','.join(expected_files) if expected_files else '-'}",
        ]
        prefix = f"{package_id} " if package_id else ""
        return f"{prefix}{owner}: {title} ({'; '.join(details)})"

    @staticmethod
    def _questions(session: WorkflowSession | None) -> list[QuestionSnapshot]:
        if session is None:
            return []
        answer_by_question_id = {
            str(decision.question_id): decision.decision
            for decision in session.decisions
            if decision.question_id
        }
        return [
            QuestionSnapshot(
                id=q.id,
                question=q.question,
                options=list(q.options),
                recommended_option=q.recommended_option or "",
                status=q.status,
                answer=answer_by_question_id.get(q.id, "") if q.status != "open" else "",
            )
            for q in session.pending_questions
        ]

    def _provider_states(
        self,
        session: WorkflowSession | None,
    ) -> dict[str, ProviderSnapshot]:
        active = set(session.active_agents) if session else set()
        targets = set(session.last_target_agents) if session else set()
        artifacts = self._latest_response_artifacts(session)
        states: dict[str, ProviderSnapshot] = {}
        for name, spec in self.config.agents.items():
            enabled = spec.enabled
            if session and session.active_agents:
                enabled = name in active
            targeted = True
            if session and session.state.value == "deliberating" and targets:
                targeted = name in targets
            artifact = artifacts.get(name)
            summary = ""
            raw_output = ""
            status = "Queued" if enabled else "Disabled"
            if enabled and not targeted:
                status = "Idle"
            elif enabled and artifact is not None:
                clean_output = self._read_artifact_text(artifact[0])
                raw_output = self._read_artifact_text(artifact[1]) or clean_output
                summary = self._short_summary(clean_output or raw_output)
                status = "Ready"
            elif enabled and session and session.state.value == "deliberating":
                status = "Running"
            runtime_model = self._runtime_model_for(session, name)
            provider_session = self._provider_session_for(session, name)
            actual_model = ""
            model_label = ""
            context_window = 0
            budget_source = ""
            if runtime_model is not None:
                actual_model = runtime_model.actual_model
                model_label = runtime_model.model_label
                context_window = runtime_model.context_window
                budget_source = runtime_model.budget_source
            session_id = provider_session.provider_session_id if provider_session else ""
            session_kind = provider_session.session_kind if provider_session else ""
            configured_model = spec.model
            if session is not None and name in session.agent_model_overrides:
                configured_model = session.agent_model_overrides[name]
            provider_line = spec.provider.value
            display_model = actual_model or model_label
            if display_model:
                provider_line = f"{provider_line} · {display_model}"
            states[name] = ProviderSnapshot(
                name=name,
                provider=provider_line,
                enabled=enabled,
                status=status,
                summary=summary,
                raw_output=raw_output,
                configured_model=configured_model,
                actual_model=actual_model,
                model_label=model_label,
                context_window=context_window,
                budget_source=budget_source,
                session_id=session_id,
                session_kind=session_kind,
            )
        return states

    @staticmethod
    def _runtime_model_for(session: WorkflowSession | None, agent_name: str):
        if session is None:
            return None
        return session.runtime_models.get(agent_name)

    @staticmethod
    def _provider_session_for(session: WorkflowSession | None, agent_name: str):
        if session is None:
            return None
        matches = [
            item
            for item in session.provider_sessions.values()
            if item.agent_name == agent_name and item.provider_session_id
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.last_observed_at, reverse=True)[0]

    def _fold_recent_events(
        self,
        states: dict[str, ProviderSnapshot],
        recent_events: Iterable[TUIEvent],
    ) -> None:
        for event in recent_events:
            data = event.data
            agent = str(data.get("agent", ""))
            if not agent or agent not in states:
                continue

            current = states[agent]
            if event.type == TUIEventType.AGENT_THINKING:
                states[agent] = self._replace(current, status="Running")
            elif event.type == TUIEventType.AGENT_RESPONDED:
                content = str(data.get("content", ""))
                states[agent] = self._replace(
                    current,
                    status="Ready",
                    summary=self._short_summary(content),
                    raw_output=content,
                )
            elif event.type == TUIEventType.AGENT_ERROR:
                error = str(data.get("error", ""))
                states[agent] = self._replace(
                    current,
                    status="Error",
                    summary=self._short_summary(error),
                    raw_output=error,
                )
            elif event.type == TUIEventType.PROVIDER_READINESS:
                states[agent] = self._replace(
                    current,
                    readiness=str(data.get("state", "unknown")),
                    readiness_reason=str(data.get("reason", "")),
                )

    def _synthesis(
        self,
        session: WorkflowSession | None,
        recent_events: list[TUIEvent],
        round_num: int,
    ) -> SynthesisSnapshot:
        if session and session.blueprint:
            return SynthesisSnapshot(
                summary=session.blueprint.summary,
                consensus_progress="blueprint ready",
                source="workflow",
                status="ready",
            )

        event_synthesis = self._synthesis_from_events(recent_events)
        if event_synthesis is not None:
            return event_synthesis

        if session is None or not self._has_workflow_context(session):
            return SynthesisSnapshot()

        if round_num:
            section = self.shared.read_section(f"Round {round_num} Synthesis")
            if section:
                return SynthesisSnapshot(
                    summary=section.strip(),
                    consensus_progress=f"round {round_num}",
                    source="shared.md",
                    status="ready",
                )

        agreed = self.shared.read_section("Agreed Conclusion")
        if agreed:
            return SynthesisSnapshot(
                summary=agreed.strip(),
                consensus_progress="agreed",
                source="shared.md",
                status="ready",
            )

        if session and session.state.value == "deliberating":
            active_round = round_num or 1
            return SynthesisSnapshot(
                summary=f"Collecting provider responses for round {active_round}.",
                consensus_progress=f"round {active_round} collecting",
                source="runtime",
                status="waiting",
            )

        return SynthesisSnapshot()

    @staticmethod
    def _has_workflow_context(session: WorkflowSession) -> bool:
        """Return whether a persisted session should project shared synthesis."""
        return bool(
            session.goal
            or session.current_round
            or session.active_agents
            or session.blueprint
            or session.open_questions
            or session.decisions
            or session.work_packages
            or session.subtask_results
            or session.review_packages
            or session.review_results
        )

    def _round_num(
        self,
        session: WorkflowSession | None,
        recent_events: list[TUIEvent],
    ) -> int:
        current = session.current_round if session else 0
        for event in recent_events:
            value = event.data.get("round_num")
            try:
                current = max(current, int(value))
            except (TypeError, ValueError):
                continue
        if current == 0 and session and session.state.value == "deliberating":
            current = 1
        return current

    def _synthesis_from_events(
        self,
        recent_events: list[TUIEvent],
    ) -> SynthesisSnapshot | None:
        synthesis: SynthesisSnapshot | None = None
        for event in recent_events:
            data = event.data
            if event.type == TUIEventType.ROUND_START:
                round_num = self._event_round(data)
                synthesis = SynthesisSnapshot(
                    summary=f"Collecting provider responses for round {round_num}.",
                    consensus_progress=f"round {round_num} collecting",
                    source="runtime",
                    status="waiting",
                )
            elif event.type == TUIEventType.CONSENSUS_CHECKING:
                round_num = self._event_round(data)
                synthesis = SynthesisSnapshot(
                    summary=(
                        f"Central agent is synthesizing round {round_num} provider responses."
                    ),
                    consensus_progress=f"round {round_num} synthesizing",
                    source="runtime",
                    status="running",
                )
            elif event.type == TUIEventType.CONSENSUS_RESULT:
                round_num = self._event_round(data)
                summary = str(data.get("summary", "")).strip()
                reached = bool(data.get("reached", False))
                agreement = self._event_int(data.get("agreement_count"))
                total = self._event_int(data.get("total_agents"))
                vote_text = f"{agreement}/{total}" if total else "0/0"
                state_text = "reached" if reached else "not reached"
                if not summary:
                    summary = f"Round {round_num} consensus {state_text} ({vote_text})."
                fallback_reason = str(data.get("fallback_reason", "")).strip()
                if fallback_reason:
                    summary = f"{summary}\n\nSynthesis fallback: {fallback_reason}"
                source = str(data.get("synthesis_source", "runtime")) or "runtime"
                progress = f"round {round_num} consensus {state_text} ({vote_text})"
                if bool(data.get("fallback_used", False)):
                    progress = f"{progress}; fallback used"
                synthesis = SynthesisSnapshot(
                    summary=summary,
                    consensus_progress=progress,
                    source=source,
                    status="ready",
                )
        return synthesis

    @staticmethod
    def _event_round(data: dict[str, object]) -> int:
        return NexusSnapshotAdapter._event_int(data.get("round_num")) or 1

    @staticmethod
    def _event_int(value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _execution_log(
        self,
        session: WorkflowSession | None,
        session_events: Iterable[dict[str, object]] | None = None,
    ) -> list[str]:
        if session is None:
            return []

        lines: list[str] = []
        session_events = list(session_events) if session_events is not None else (
            self.persistence.load_events_for_workflow(session.id)
        )
        completed_event_package_ids = {
            self._event_package_id(event)
            for event in session_events
            if str(event.get("event", "")) == "work_package_completed"
        }
        display_events = session_events[-80:]
        displayed_finished_package_ids: set[str] = set()
        for event in display_events:
            event_name = str(event.get("event", ""))
            package_id = self._event_package_id(event)
            if (
                event_name == "execution_result_recorded"
                and package_id in completed_event_package_ids
            ):
                continue
            lines.append(self._format_execution_event(event))
            if event_name in {"work_package_completed", "execution_result_recorded"}:
                displayed_finished_package_ids.add(package_id)

        if session:
            for result in session.execution_results[-10:]:
                if str(getattr(result, "package_id", "")) in displayed_finished_package_ids:
                    continue
                lines.append(self._format_execution_result(result))
        return lines

    def _workflow_events(
        self,
        session: WorkflowSession | None,
        session_events: Iterable[dict[str, object]] | None = None,
    ) -> list[str]:
        if session is None:
            return []
        session_events = list(session_events) if session_events is not None else (
            self.persistence.load_events_for_workflow(session.id)
        )
        return [
            self._format_workflow_event(event)
            for event in session_events
        ]

    def _last_session_event(
        self,
        session: WorkflowSession,
        session_events: Iterable[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        events = list(session_events) if session_events is not None else (
            self.persistence.load_events_for_workflow(session.id)
        )
        return events[-1] if events else None

    @staticmethod
    def _format_execution_result(result: object) -> str:
        package_id = str(getattr(result, "package_id", "")).strip()
        agent = str(getattr(result, "agent_name", "")).strip()
        status = str(getattr(getattr(result, "status", ""), "value", "")).strip()
        if not status:
            status = str(getattr(result, "status", "")).strip()
        details = " ".join(part for part in (package_id, agent) if part)
        line = f"{details}: {status}" if details else status
        blockers = getattr(result, "blockers", []) or []
        reason = ""
        if blockers:
            reason = str(blockers[0]).strip()
        if not reason:
            reason = str(getattr(result, "summary", "")).strip()
        if reason and status in {"failed", "blocked"}:
            line = f"{line} - {NexusSnapshotAdapter._short_summary(reason, limit=120)}"
        return line

    @staticmethod
    def _format_workflow_event(event: dict[str, object]) -> str:
        event_name = str(event.get("event", "event"))
        data = event.get("data", {})
        data = data if isinstance(data, dict) else {}
        prefix = NexusSnapshotAdapter._format_event_timestamp(event)

        if event_name == "workflow_started":
            goal = str(data.get("goal", "")).strip()
            agents = data.get("active_agents", [])
            agent_list = ", ".join(str(item) for item in agents) if isinstance(agents, list) else ""
            detail = NexusSnapshotAdapter._short_summary(goal, limit=120) or "workflow"
            if agent_list:
                detail = f"{detail}; agents={agent_list}"
            return f"{prefix}{event_name}: {detail}"

        if event_name == "state_changed":
            previous = str(data.get("from", "")).strip()
            current = str(data.get("to", "") or event.get("state", "")).strip()
            reason = str(data.get("reason", "")).strip()
            detail = f"{previous} -> {current}" if previous else current
            if reason:
                detail = f"{detail}; {reason}"
            return f"{prefix}{event_name}: {detail or event_name}"

        if event_name in {"decision_recorded", "decision_replaced"}:
            question_id = str(data.get("question_id", "")).strip()
            decision = str(data.get("decision", "")).strip()
            detail = question_id or str(data.get("decision_id", "")).strip()
            if decision:
                decision = NexusSnapshotAdapter._short_summary(decision, limit=140)
                detail = f"{detail}: {decision}" if detail else decision
            return f"{prefix}{event_name}: {detail or event_name}"

        if event_name == "workflow_continued":
            instruction = str(data.get("instruction", "")).strip()
            source_state = str(data.get("source_state", "")).strip()
            detail = NexusSnapshotAdapter._short_summary(instruction, limit=140)
            if source_state:
                detail = f"{detail}; from={source_state}" if detail else f"from={source_state}"
            return f"{prefix}{event_name}: {detail or event_name}"

        if event_name == "target_workspace_cleared":
            return f"{prefix}{event_name}"

        if event_name == "work_package_retry_skipped":
            package_id = str(data.get("package_id", "")).strip()
            reason = str(data.get("reason", "")).strip()
            detail = package_id
            if reason:
                detail = f"{detail} - {reason}" if detail else reason
            return f"{prefix}{event_name}: {detail or event_name}"

        return NexusSnapshotAdapter._format_execution_event(event)

    @staticmethod
    def _format_execution_event(event: dict[str, object]) -> str:
        event_name = str(event.get("event", "event"))
        state = str(event.get("state", ""))
        data = event.get("data", {})
        data = data if isinstance(data, dict) else {}
        prefix = NexusSnapshotAdapter._format_event_timestamp(event)

        if event_name == "work_package_started":
            package_id = str(data.get("package_id", "")).strip()
            agent = str(data.get("agent", "")).strip()
            status = str(data.get("status", "")).strip()
            details = " ".join(part for part in (package_id, agent, status) if part)
            line = f"{event_name}: {details}" if details else event_name
            return f"{prefix}{line}"

        if event_name in {"work_package_completed", "execution_result_recorded"}:
            package_id = str(data.get("package_id", "")).strip()
            agent = str(data.get("agent", "")).strip()
            status = str(data.get("status", "")).strip()
            summary = str(data.get("summary", "")).strip()
            details = " ".join(part for part in (package_id, agent, status) if part)
            if summary:
                details = f"{details} - {summary}" if details else summary
            line = f"work_package_completed: {details}" if details else event_name
            return f"{prefix}{line}"

        if event_name == "execution_run_started":
            packages = data.get("work_packages", [])
            package_count = len(packages) if isinstance(packages, list) else 0
            run_id = str(data.get("run_id", "")).strip()
            target = str(data.get("target_workspace", "")).strip()
            detail = f"{package_count} packages"
            if target:
                detail = f"{detail} -> {target}"
            if run_id:
                detail = f"{run_id} {detail}"
            return f"{prefix}{event_name}: {detail}"

        if event_name in {"execution_enabled", "implementation_requested"}:
            packages = data.get("work_packages", [])
            package_count = len(packages) if isinstance(packages, list) else 0
            target = str(data.get("target_workspace", "")).strip()
            if target:
                return f"{prefix}{event_name}: {package_count} packages -> {target}"
            return f"{prefix}{event_name}: {package_count} packages"

        if event_name == "execution_interrupted_detected":
            packages = data.get("running_packages", [])
            package_list = (
                ", ".join(str(item) for item in packages) if isinstance(packages, list) else ""
            )
            reason = str(data.get("reason", "")).strip()
            detail = package_list or "no running package"
            if reason:
                detail = f"{detail}; {reason}"
            return f"{prefix}{event_name}: {detail}"

        if event_name == "execution_recovery_action":
            action = str(data.get("action", "")).strip()
            packages = data.get("packages", [])
            package_list = (
                ", ".join(str(item) for item in packages) if isinstance(packages, list) else ""
            )
            detail = action or "action"
            if package_list:
                detail = f"{detail}: {package_list}"
            return f"{prefix}{event_name}: {detail}"

        if event_name == "work_package_retry_requested":
            package_id = str(data.get("package_id", "")).strip()
            previous = str(data.get("previous_status", "")).strip()
            agent = str(data.get("agent", "")).strip()
            details = " ".join(part for part in (package_id, agent, previous) if part)
            return f"{prefix}{event_name}: {details or package_id}"

        if event_name == "execution_batch_planned":
            batches = data.get("batches", [])
            batch_count = len(batches) if isinstance(batches, list) else 0
            notices = data.get("notices", [])
            notice_count = len(notices) if isinstance(notices, list) else 0
            detail = f"{batch_count} batches"
            if notice_count:
                first_notice = notices[0] if isinstance(notices[0], dict) else {}
                reason = str(first_notice.get("reason", "")).strip()
                detail = f"{detail}; {notice_count} policy notices"
                if reason:
                    detail = f"{detail} - {reason}"
            return f"{prefix}{event_name}: {detail}"

        if event_name == "target_workspace_selected":
            target = str(data.get("target_workspace", "")).strip()
            line = f"{event_name}: {target}" if target else event_name
            return f"{prefix}{line}"

        if state:
            return f"{prefix}{event_name}: {state}"
        return f"{prefix}{event_name}"

    @staticmethod
    def _event_package_id(event: dict[str, object]) -> str:
        data = event.get("data", {})
        data = data if isinstance(data, dict) else {}
        return str(data.get("package_id", "")).strip()

    @staticmethod
    def _format_event_timestamp(event: dict[str, object]) -> str:
        value = event.get("timestamp")
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            return ""
        if timestamp <= 0:
            return ""
        return f"[{datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')}] "

    def _latest_response_artifacts(
        self,
        session: WorkflowSession | None,
    ) -> dict[str, tuple[Path, Path | None]]:
        if session is None or session.current_round <= 0:
            return {}

        round_dir = (
            self.config.effective_state_dir / "responses" / f"round-{session.current_round:02d}"
        )
        if not round_dir.exists():
            return {}

        cutoff = max(0.0, session.created_at - 1.0)
        artifacts: dict[str, tuple[Path, Path | None]] = {}
        for name in self.config.agents:
            candidates = sorted(
                round_dir.glob(f"{name}-*.clean.txt"),
                key=lambda path: self._mtime(path),
                reverse=True,
            )
            for clean_path in candidates:
                if self._mtime(clean_path) < cutoff:
                    continue
                raw_path = Path(str(clean_path).removesuffix(".clean.txt") + ".raw.txt")
                artifacts[name] = (
                    clean_path,
                    raw_path if raw_path.exists() else None,
                )
                break
        return artifacts

    @staticmethod
    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    @staticmethod
    def _read_artifact_text(path: Path | None, limit: int = 120_000) -> str:
        if path is None:
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text if len(text) <= limit else text[:limit].rstrip() + "\n..."

    @staticmethod
    def _replace(snapshot: ProviderSnapshot, **updates: object) -> ProviderSnapshot:
        data = {
            "name": snapshot.name,
            "provider": snapshot.provider,
            "enabled": snapshot.enabled,
            "status": snapshot.status,
            "summary": snapshot.summary,
            "readiness": snapshot.readiness,
            "readiness_reason": snapshot.readiness_reason,
            "raw_output": snapshot.raw_output,
            "configured_model": snapshot.configured_model,
            "actual_model": snapshot.actual_model,
            "model_label": snapshot.model_label,
            "context_window": snapshot.context_window,
            "budget_source": snapshot.budget_source,
            "session_id": snapshot.session_id,
            "session_kind": snapshot.session_kind,
        }
        data.update(updates)
        return ProviderSnapshot(**data)

    @staticmethod
    def _short_summary(text: str, limit: int = 96) -> str:
        cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"
