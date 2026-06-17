"""Peer review planning models for workflow execution results."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from trinity.workflow.models import ExecutionResult, WorkPackage, WorkStatus


class ReviewStatus(str, Enum):
    """Lifecycle state for one peer review result."""

    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"
    FAILED = "failed"


class ReviewDepth(str, Enum):
    """Planned depth for work-package review."""

    NONE = "none"
    SELF_CHECK = "self_check"
    SINGLE_PEER = "single_peer"
    ESCALATED_PEER = "escalated_peer"


FINAL_REVIEW_PACKAGE_ID = "FINAL"
FINAL_REVIEW_FALLBACK_PRIORITY: tuple[str, ...] = (
    "codex",
    "claude",
    "antigravity",
)
PRIMARY_REVIEWER_PRIORITY: tuple[str, ...] = (
    "antigravity",
    "claude",
    "codex",
)
ESCALATION_REVIEW_STATUSES: frozenset[ReviewStatus] = frozenset(
    {
        ReviewStatus.CHANGES_REQUESTED,
        ReviewStatus.BLOCKED,
        ReviewStatus.FAILED,
    }
)


@dataclass
class ReviewPackage:
    """A review task assigned to an agent for one completed work package."""

    package_id: str
    reviewer_agent: str
    target_agent: str
    criteria: list[str] = field(default_factory=list)
    id: str = ""
    self_review: bool = False
    execution_status: WorkStatus | None = None
    scope: str = "work_package"
    attempt: int = 1
    depth: ReviewDepth = ReviewDepth.SINGLE_PEER
    required: bool = True
    reason: str = ""
    escalation_parent_id: str = ""
    skipped_reason: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.depth, ReviewDepth):
            self.depth = ReviewDepth(str(self.depth))
        if self.depth == ReviewDepth.NONE:
            self.required = False
        self.reason = str(self.reason or "")
        self.escalation_parent_id = str(self.escalation_parent_id or "")
        self.skipped_reason = str(self.skipped_reason or "")
        if not self.id:
            reviewer = self.reviewer_agent or "skipped"
            self.id = f"RP-{self.package_id}-{reviewer}"
        self.self_review = bool(
            self.reviewer_agent and self.reviewer_agent == self.target_agent
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "package_id": self.package_id,
            "reviewer_agent": self.reviewer_agent,
            "target_agent": self.target_agent,
            "criteria": list(self.criteria),
            "self_review": self.self_review,
            "execution_status": (
                self.execution_status.value if self.execution_status else None
            ),
            "scope": self.scope,
            "attempt": self.attempt,
            "depth": self.depth.value,
            "required": self.required,
            "reason": self.reason,
            "escalation_parent_id": self.escalation_parent_id,
            "skipped_reason": self.skipped_reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewPackage":
        status = data.get("execution_status")
        reviewer_agent = str(data.get("reviewer_agent", ""))
        target_agent = str(data.get("target_agent", ""))
        depth = str(data.get("depth", "") or "")
        if not depth:
            depth = (
                ReviewDepth.SELF_CHECK.value
                if reviewer_agent and reviewer_agent == target_agent
                else ReviewDepth.SINGLE_PEER.value
            )
        return cls(
            id=str(data.get("id", "")),
            package_id=str(data.get("package_id", "")),
            reviewer_agent=reviewer_agent,
            target_agent=target_agent,
            criteria=[str(item) for item in data.get("criteria", [])],
            self_review=bool(data.get("self_review", False)),
            execution_status=WorkStatus(str(status)) if status else None,
            scope=str(data.get("scope", "work_package") or "work_package"),
            attempt=max(1, int(data.get("attempt", 1) or 1)),
            depth=ReviewDepth(depth),
            required=bool(data.get("required", True)),
            reason=str(data.get("reason", "") or ""),
            escalation_parent_id=str(data.get("escalation_parent_id", "") or ""),
            skipped_reason=str(data.get("skipped_reason", "") or ""),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class ReviewResult:
    """Result reported by a reviewer after checking one review package."""

    review_package_id: str
    package_id: str
    reviewer_agent: str
    target_agent: str
    status: ReviewStatus
    summary: str = ""
    findings: list[str] = field(default_factory=list)
    required_changes: list[str] = field(default_factory=list)
    follow_up: list[str] = field(default_factory=list)
    raw_response_path: Path | None = None
    severity: str = "medium"
    scope: str = "work_package"
    reviewed_files: list[str] = field(default_factory=list)
    compatibility_notes: list[str] = field(default_factory=list)
    performance_notes: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    execution_risks: list[str] = field(default_factory=list)
    skipped: bool = False
    skipped_reason: str = ""
    confidence: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_package_id": self.review_package_id,
            "package_id": self.package_id,
            "reviewer_agent": self.reviewer_agent,
            "target_agent": self.target_agent,
            "status": self.status.value,
            "summary": self.summary,
            "findings": list(self.findings),
            "required_changes": list(self.required_changes),
            "follow_up": list(self.follow_up),
            "raw_response_path": (
                str(self.raw_response_path) if self.raw_response_path else None
            ),
            "severity": self.severity,
            "scope": self.scope,
            "reviewed_files": list(self.reviewed_files),
            "compatibility_notes": list(self.compatibility_notes),
            "performance_notes": list(self.performance_notes),
            "anti_patterns": list(self.anti_patterns),
            "execution_risks": list(self.execution_risks),
            "skipped": self.skipped,
            "skipped_reason": self.skipped_reason,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewResult":
        raw_path = data.get("raw_response_path")
        return cls(
            review_package_id=str(data.get("review_package_id", "")),
            package_id=str(data.get("package_id", "")),
            reviewer_agent=str(data.get("reviewer_agent", "")),
            target_agent=str(data.get("target_agent", "")),
            status=ReviewStatus(str(data.get("status", ReviewStatus.PENDING.value))),
            summary=str(data.get("summary", "")),
            findings=[str(item) for item in data.get("findings", [])],
            required_changes=[
                str(item) for item in data.get("required_changes", [])
            ],
            follow_up=[str(item) for item in data.get("follow_up", [])],
            raw_response_path=Path(str(raw_path)) if raw_path else None,
            severity=str(data.get("severity", "medium") or "medium"),
            scope=str(data.get("scope", "work_package") or "work_package"),
            reviewed_files=[str(item) for item in data.get("reviewed_files", [])],
            compatibility_notes=[
                str(item) for item in data.get("compatibility_notes", [])
            ],
            performance_notes=[str(item) for item in data.get("performance_notes", [])],
            anti_patterns=[str(item) for item in data.get("anti_patterns", [])],
            execution_risks=[str(item) for item in data.get("execution_risks", [])],
            skipped=bool(data.get("skipped", False)),
            skipped_reason=str(data.get("skipped_reason", "") or ""),
            confidence=str(data.get("confidence", "medium") or "medium"),
        )


class PeerReviewPlanner:
    """Assign peer reviewers to completed workflow work packages."""

    DEFAULT_CRITERIA = (
        "Verify the work package acceptance criteria are satisfied.",
        "Check changed files for correctness, regressions, and missing tests.",
        "Identify severe runtime or execution-breaking defects.",
        "Flag anti-patterns that make the implementation hard to maintain.",
        "Call out performance risks introduced by the implementation.",
        "Identify blockers or follow-up needed before merge.",
    )

    def __init__(self, default_criteria: list[str] | None = None):
        self.default_criteria = (
            list(default_criteria)
            if default_criteria is not None
            else list(self.DEFAULT_CRITERIA)
        )

    def plan_reviews(
        self,
        work_packages: list[WorkPackage],
        active_agents: list[str],
        execution_results: list[ExecutionResult] | None = None,
    ) -> list[ReviewPackage]:
        """Create review packages for work packages using the active agent set."""
        packages = list(work_packages)
        if not packages:
            return []

        agents = self._normalize_agents(active_agents)
        if not agents:
            raise ValueError("active_agents must include at least one reviewer")

        results_by_package = {
            result.package_id: result
            for result in execution_results or []
        }
        review_packages: list[ReviewPackage] = []

        for package in packages:
            result = results_by_package.get(package.id)
            target_agent = result.agent_name if result else package.owner_agent
            reviewer_agent = self._primary_reviewer_for(
                target_agent=target_agent,
                active_agents=agents,
            )
            if reviewer_agent is None:
                review_packages.append(
                    self._skipped_no_peer_package(package, target_agent, result)
                )
                continue
            review_packages.append(
                ReviewPackage(
                    package_id=package.id,
                    reviewer_agent=reviewer_agent,
                    target_agent=target_agent,
                    criteria=self._criteria_for(package),
                    execution_status=result.status if result else None,
                    depth=ReviewDepth.SINGLE_PEER,
                    reason=self._primary_reason(target_agent, agents),
                )
            )

        return review_packages

    def plan_escalation_reviews(
        self,
        work_packages: list[WorkPackage],
        active_agents: list[str],
        existing_reviews: list[ReviewPackage],
        review_results: list[ReviewResult] | None = None,
        execution_results: list[ExecutionResult] | None = None,
    ) -> list[ReviewPackage]:
        """Create optional second-review packages for risk or review issues."""
        agents = self._normalize_agents(active_agents)
        if len(agents) < 3:
            return []

        results_by_package = {
            result.package_id: result
            for result in execution_results or []
        }
        review_results_by_package: dict[str, list[ReviewResult]] = {}
        for result in review_results or []:
            review_results_by_package.setdefault(result.package_id, []).append(result)

        escalations: list[ReviewPackage] = []
        for package in work_packages:
            primary_reviews = [
                review
                for review in existing_reviews
                if review.package_id == package.id
                and review.scope != "final"
                and review.required
                and not review.escalation_parent_id
                and review.depth != ReviewDepth.NONE
            ]
            if not primary_reviews:
                continue
            primary = primary_reviews[0]
            if any(
                review.escalation_parent_id == primary.id
                for review in existing_reviews
            ):
                continue
            reason = self._escalation_reason(
                package,
                review_results_by_package.get(package.id, []),
            )
            if not reason:
                continue
            reviewer_agent = self._secondary_reviewer_for(
                target_agent=primary.target_agent,
                active_agents=agents,
                existing_reviewers=[
                    review.reviewer_agent
                    for review in existing_reviews
                    if review.package_id == package.id
                ],
            )
            if reviewer_agent is None:
                continue
            result = results_by_package.get(package.id)
            escalations.append(
                ReviewPackage(
                    id=f"{primary.id}-ESC-{reviewer_agent}",
                    package_id=package.id,
                    reviewer_agent=reviewer_agent,
                    target_agent=primary.target_agent,
                    criteria=self._criteria_for(package),
                    execution_status=result.status if result else primary.execution_status,
                    depth=ReviewDepth.ESCALATED_PEER,
                    reason=reason,
                    escalation_parent_id=primary.id,
                )
            )
        return escalations

    def _criteria_for(self, package: WorkPackage) -> list[str]:
        return self._dedupe([*self.default_criteria, *package.acceptance_criteria])

    def _primary_reviewer_for(
        self,
        target_agent: str,
        active_agents: list[str],
    ) -> str | None:
        if len(active_agents) == 1:
            return None

        candidates = [
            agent
            for agent in active_agents
            if agent != target_agent
        ]
        if not candidates:
            return None
        return self._select_by_priority(candidates)

    def _secondary_reviewer_for(
        self,
        target_agent: str,
        active_agents: list[str],
        existing_reviewers: list[str],
    ) -> str | None:
        used = {agent for agent in existing_reviewers if agent}
        candidates = [
            agent
            for agent in active_agents
            if agent != target_agent and agent not in used
        ]
        if not candidates:
            return None
        return self._select_by_priority(candidates)

    def _select_by_priority(self, candidates: list[str]) -> str:
        return sorted(candidates, key=self._priority_key)[0]

    def _priority_key(self, agent: str) -> tuple[int, str]:
        normalized = agent.strip().lower()
        try:
            priority = PRIMARY_REVIEWER_PRIORITY.index(normalized)
        except ValueError:
            priority = len(PRIMARY_REVIEWER_PRIORITY)
        return (priority, normalized)

    def _primary_reason(self, target_agent: str, active_agents: list[str]) -> str:
        candidates = [agent for agent in active_agents if agent != target_agent]
        if len(candidates) == 1:
            return "single available non-owner reviewer"
        return "selected primary reviewer by deterministic provider priority"

    def _skipped_no_peer_package(
        self,
        package: WorkPackage,
        target_agent: str,
        result: ExecutionResult | None,
    ) -> ReviewPackage:
        skipped_reason = (
            f"only {target_agent} is active; no non-owner peer reviewer is available"
        )
        return ReviewPackage(
            id=f"RP-{package.id}-skipped-no-peer",
            package_id=package.id,
            reviewer_agent="",
            target_agent=target_agent,
            criteria=[],
            execution_status=result.status if result else None,
            depth=ReviewDepth.NONE,
            required=False,
            reason="peer review skipped because no peer reviewer is active",
            skipped_reason=skipped_reason,
        )

    def _escalation_reason(
        self,
        package: WorkPackage,
        review_results: list[ReviewResult],
    ) -> str:
        if str(package.risk).strip().lower() in {"high", "critical"}:
            return f"package risk is {package.risk}"
        for result in reversed(review_results):
            if result.status in ESCALATION_REVIEW_STATUSES:
                return f"primary review status is {result.status.value}"
        return ""

    def _normalize_agents(self, agents: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for agent in agents:
            name = str(agent).strip()
            if name and name not in seen:
                normalized.append(name)
                seen.add(name)
        return normalized

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = str(value).strip()
            if item and item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped


def final_review_package(
    reviewer_agent: str,
    *,
    attempt: int = 1,
    criteria: list[str] | None = None,
) -> ReviewPackage:
    """Build the session-level final review task for a selected reviewer."""
    return ReviewPackage(
        id=f"RP-{FINAL_REVIEW_PACKAGE_ID}-{reviewer_agent}",
        package_id=FINAL_REVIEW_PACKAGE_ID,
        reviewer_agent=reviewer_agent,
        target_agent="project",
        criteria=criteria or final_review_criteria(),
        execution_status=WorkStatus.DONE,
        scope="final",
        attempt=attempt,
    )


def final_review_criteria() -> list[str]:
    """Return the required focus areas for final project review."""
    return [
        "Review whole-project compatibility across the completed work packages.",
        "Summarize the project overview in user-facing language.",
        "Document how to run the project from the selected target workspace.",
        "Identify additional features that appear necessary or high-value.",
        "Call out critical execution risks before the workflow is considered done.",
    ]
