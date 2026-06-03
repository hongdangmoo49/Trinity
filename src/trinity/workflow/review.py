"""Peer review planning models for workflow execution results."""

from __future__ import annotations

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

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"RP-{self.package_id}-{self.reviewer_agent}"
        self.self_review = self.reviewer_agent == self.target_agent

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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewPackage":
        status = data.get("execution_status")
        return cls(
            id=str(data.get("id", "")),
            package_id=str(data.get("package_id", "")),
            reviewer_agent=str(data.get("reviewer_agent", "")),
            target_agent=str(data.get("target_agent", "")),
            criteria=[str(item) for item in data.get("criteria", [])],
            self_review=bool(data.get("self_review", False)),
            execution_status=WorkStatus(str(status)) if status else None,
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
        )


class PeerReviewPlanner:
    """Assign at least one active reviewer to each workflow work package."""

    DEFAULT_CRITERIA = (
        "Verify the work package acceptance criteria are satisfied.",
        "Check changed files for correctness, regressions, and missing tests.",
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

        for index, package in enumerate(packages):
            result = results_by_package.get(package.id)
            target_agent = result.agent_name if result else package.owner_agent
            reviewer_agent = self._choose_reviewer(
                target_agent=target_agent,
                active_agents=agents,
                index=index,
            )
            review_packages.append(
                ReviewPackage(
                    package_id=package.id,
                    reviewer_agent=reviewer_agent,
                    target_agent=target_agent,
                    criteria=self._criteria_for(package),
                    execution_status=result.status if result else None,
                )
            )

        return review_packages

    def _criteria_for(self, package: WorkPackage) -> list[str]:
        return self._dedupe([*self.default_criteria, *package.acceptance_criteria])

    def _choose_reviewer(
        self,
        target_agent: str,
        active_agents: list[str],
        index: int,
    ) -> str:
        if len(active_agents) == 1:
            return active_agents[0]

        candidates = [
            agent
            for agent in active_agents
            if agent != target_agent
        ]
        if not candidates:
            candidates = active_agents
        return candidates[index % len(candidates)]

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
