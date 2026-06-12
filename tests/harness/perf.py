"""Synthetic workflow fixtures and timing probes for performance regression tests."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from trinity.config import TrinityConfig
from trinity.textual_app.snapshot import NexusSnapshotAdapter
from trinity.workflow import (
    ExecutionResult,
    ReviewPackage,
    ReviewResult,
    ReviewStatus,
    WorkPackage,
    WorkflowPersistence,
    WorkflowSession,
    WorkflowState,
    WorkStatus,
)

T = TypeVar("T")


@dataclass(frozen=True)
class TimingStats:
    """Simple timing summary in milliseconds."""

    count: int
    min_ms: float
    avg_ms: float
    max_ms: float


@dataclass(frozen=True)
class WorkflowPerfFixture:
    """Paths and handles for a generated workflow performance fixture."""

    config: TrinityConfig
    persistence: WorkflowPersistence
    session: WorkflowSession

    @property
    def state_dir(self) -> Path:
        return self.config.effective_state_dir

    @property
    def session_path(self) -> Path:
        return self.persistence.session_path

    @property
    def events_path(self) -> Path:
        return self.persistence.events_path


def measure_ms(fn: Callable[[], T], *, repeat: int = 5) -> tuple[TimingStats, T]:
    """Run a callable repeatedly and return timing stats plus the last result."""
    if repeat <= 0:
        raise ValueError("repeat must be positive")

    durations: list[float] = []
    result: T | None = None
    for _ in range(repeat):
        started = time.perf_counter()
        result = fn()
        durations.append((time.perf_counter() - started) * 1000)

    return (
        TimingStats(
            count=repeat,
            min_ms=min(durations),
            avg_ms=statistics.fmean(durations),
            max_ms=max(durations),
        ),
        result,
    )


def create_workflow_perf_fixture(
    project_dir: Path,
    *,
    workflow_id: str = "wf-perf",
    package_count: int = 25,
    event_count: int = 1_000,
    review_result_count: int = 100,
    shared_bytes: int = 0,
) -> WorkflowPerfFixture:
    """Create a deterministic workflow fixture with scalable persisted state."""
    if package_count <= 0:
        raise ValueError("package_count must be positive")
    if event_count < 0:
        raise ValueError("event_count must be non-negative")
    if review_result_count < 0:
        raise ValueError("review_result_count must be non-negative")
    if shared_bytes < 0:
        raise ValueError("shared_bytes must be non-negative")

    config = TrinityConfig.default_config(project_dir=project_dir)
    config.agents["codex"].enabled = True
    config.agents["antigravity"].enabled = True
    persistence = WorkflowPersistence(config.effective_state_dir)

    packages = [
        WorkPackage(
            id=f"WP-{index:03d}",
            title=f"Performance package {index}",
            owner_agent=_agent_for(index),
            objective=f"Implement deterministic fixture package {index}.",
            expected_files=[f"src/perf/package_{index}.py"],
            acceptance_criteria=[
                f"Acceptance criterion {index}-1",
                f"Acceptance criterion {index}-2",
            ],
            status=WorkStatus.RUNNING if index == package_count else WorkStatus.DONE,
            current_executor=_agent_for(index) if index == package_count else "",
            last_executor=_agent_for(index) if index != package_count else "",
            risk="high" if index % 3 == 0 else "medium",
        )
        for index in range(1, package_count + 1)
    ]
    execution_results = [
        ExecutionResult(
            package_id=package.id,
            agent_name=package.owner_agent,
            status=WorkStatus.DONE,
            summary=f"Completed {package.title}.",
            files_changed=list(package.expected_files),
            follow_up=[f"Follow-up for {package.id}"],
        )
        for package in packages
        if package.status == WorkStatus.DONE
    ]
    review_packages = [
        ReviewPackage(
            package_id=package.id,
            reviewer_agent=_reviewer_for(package.owner_agent),
            target_agent=package.owner_agent,
            criteria=["Check correctness.", "Check regressions."],
        ).to_dict()
        for package in packages
    ]
    review_results = [
        ReviewResult(
            review_package_id=(
                f"RP-{packages[index % package_count].id}-"
                f"{_reviewer_for(_agent_for(index + 1))}"
            ),
            package_id=packages[index % package_count].id,
            reviewer_agent=_reviewer_for(_agent_for(index + 1)),
            target_agent=_agent_for(index + 1),
            status=ReviewStatus.APPROVED,
            summary=f"Approved review result {index}.",
            findings=[f"Finding {index}-1", f"Finding {index}-2"],
            reviewed_files=[f"src/perf/package_{index % package_count}.py"],
        ).to_dict()
        for index in range(review_result_count)
    ]

    session = WorkflowSession(
        id=workflow_id,
        goal="Measure Trinity workflow projection performance.",
        state=WorkflowState.EXECUTING,
        active_agents=["claude", "codex", "antigravity"],
        current_round=2,
        target_workspace=project_dir / "target",
        work_packages=packages,
        execution_results=execution_results,
        review_packages=review_packages,
        review_results=review_results,
        execution_run={"state": "running", "run_id": "run-perf"},
    )
    persistence.save(session)

    for index in range(event_count):
        package = packages[index % package_count]
        event = "work_package_completed" if index % 5 == 0 else "work_package_started"
        persistence.append_event(
            {
                "timestamp": float(index),
                "workflow_id": workflow_id,
                "event": event,
                "data": {
                    "package_id": package.id,
                    "agent": package.owner_agent,
                    "summary": f"event summary {index}",
                },
            }
        )
    persistence.append_event(
        {
            "timestamp": float(event_count + 1),
            "workflow_id": f"{workflow_id}-other",
            "event": "ignored",
        }
    )

    if shared_bytes:
        config.shared_context_path.parent.mkdir(parents=True, exist_ok=True)
        config.shared_context_path.write_text(
            _sized_markdown(shared_bytes),
            encoding="utf-8",
        )

    return WorkflowPerfFixture(
        config=config,
        persistence=persistence,
        session=session,
    )


def snapshot_probe(fixture: WorkflowPerfFixture):
    """Load one Nexus snapshot for a generated fixture."""
    return NexusSnapshotAdapter(fixture.config).load_snapshot()


def _agent_for(index: int) -> str:
    return ("claude", "codex", "antigravity")[index % 3]


def _reviewer_for(owner: str) -> str:
    for agent in ("claude", "codex", "antigravity"):
        if agent != owner:
            return agent
    return "codex"


def _sized_markdown(size: int) -> str:
    header = "## Current Goal\nMeasure projection performance.\n\n"
    if size <= len(header):
        return header[:size]
    filler = "0123456789abcdef\n"
    repeats = ((size - len(header)) // len(filler)) + 1
    return (header + (filler * repeats))[:size]
