"""Provider execution authority and parallel scheduling policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


class ExecutionAuthority(str, Enum):
    """Who executes local tools and file changes for a model request."""

    PROVIDER_MANAGED = "provider-managed"
    TRINITY_MANAGED = "trinity-managed"


class InvocationAccess(str, Enum):
    """Filesystem access level intended for a provider invocation."""

    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"


@dataclass(frozen=True)
class ExecutionScope:
    """Scheduling-relevant scope for one provider invocation."""

    agent_name: str
    authority: ExecutionAuthority = ExecutionAuthority.PROVIDER_MANAGED
    access: InvocationAccess = InvocationAccess.READ_ONLY
    cwd: Path | None = None
    workspace_id: str | None = None
    file_ownership: frozenset[str] = field(default_factory=frozenset)
    parallelizable: bool = True
    risk: str = "medium"
    parallel_group: int | None = None

    @property
    def writes_workspace(self) -> bool:
        """Return whether this invocation may write project files."""
        return self.access == InvocationAccess.WORKSPACE_WRITE

    @property
    def provider_managed_write(self) -> bool:
        """Return whether provider CLI internals may write files."""
        return (
            self.authority == ExecutionAuthority.PROVIDER_MANAGED
            and self.writes_workspace
        )

    @property
    def scheduling_key(self) -> str:
        """Return the workspace bucket used for write collision checks."""
        if self.workspace_id:
            return self.workspace_id
        if self.cwd is not None:
            return str(self.cwd.resolve())
        return "__unknown_workspace__"


@dataclass(frozen=True)
class ParallelExecutionDecision:
    """Decision returned by the parallel execution policy."""

    allowed: bool
    reason: str = ""
    serialized_agents: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParallelBatchPlan:
    """Batch plan plus conservative scheduling notices."""

    batches: tuple[tuple[ExecutionScope, ...], ...]
    notices: tuple[ParallelExecutionDecision, ...] = ()


class ParallelExecutionPolicy:
    """Decide whether provider invocations may run in the same batch."""

    BROAD_WRITE_PATHS: frozenset[str] = frozenset(
        {
            ".",
            "app",
            "lib",
            "packages",
            "src",
            "tests",
        }
    )
    SHARED_WRITE_PATHS: frozenset[str] = frozenset(
        {
            ".",
            "./",
            "Cargo.lock",
            "Cargo.toml",
            "go.mod",
            "go.sum",
            "package-lock.json",
            "package.json",
            "pnpm-lock.yaml",
            "poetry.lock",
            "pyproject.toml",
            "requirements.txt",
            "ruff.toml",
            "setup.cfg",
            "setup.py",
            "tox.ini",
            "tsconfig.json",
            "uv.lock",
            "vite.config.js",
            "vite.config.ts",
            "yarn.lock",
        }
    )

    def can_run_together(
        self,
        scopes: Iterable[ExecutionScope],
    ) -> ParallelExecutionDecision:
        """Return whether all scopes can run concurrently."""
        scope_list = tuple(scopes)
        provider_writes = [
            scope for scope in scope_list if scope.provider_managed_write
        ]
        if len(provider_writes) < 2:
            return ParallelExecutionDecision(
                allowed=True,
                reason="No provider-managed write collision.",
            )

        by_workspace: dict[str, list[ExecutionScope]] = {}
        for scope in provider_writes:
            by_workspace.setdefault(scope.scheduling_key, []).append(scope)

        for workspace, writers in by_workspace.items():
            if len(writers) < 2:
                continue
            if any(not scope.parallelizable for scope in writers):
                agents = tuple(scope.agent_name for scope in writers)
                return ParallelExecutionDecision(
                    allowed=False,
                    reason=(
                        "Provider-managed workspace-write invocations include a "
                        f"non-parallelizable package in workspace {workspace!r}."
                    ),
                    serialized_agents=agents,
                )
            if any(self._is_high_risk(scope) for scope in writers):
                agents = tuple(scope.agent_name for scope in writers)
                return ParallelExecutionDecision(
                    allowed=False,
                    reason=(
                        "Provider-managed workspace-write invocations include a "
                        f"high-risk package in workspace {workspace!r}."
                    ),
                    serialized_agents=agents,
                )
            if any(self._has_shared_write_path(scope) for scope in writers):
                agents = tuple(scope.agent_name for scope in writers)
                return ParallelExecutionDecision(
                    allowed=False,
                    reason=(
                        "Provider-managed workspace-write invocations include "
                        f"shared workspace files in workspace {workspace!r}."
                    ),
                    serialized_agents=agents,
                )
            if self._has_disjoint_file_ownership(writers):
                continue
            agents = tuple(scope.agent_name for scope in writers)
            return ParallelExecutionDecision(
                allowed=False,
                reason=(
                    "Provider-managed workspace-write invocations share "
                    f"workspace {workspace!r} without disjoint file ownership."
                ),
                serialized_agents=agents,
            )

        return ParallelExecutionDecision(
            allowed=True,
            reason=(
                "Provider-managed writes use separate workspaces or disjoint "
                "file ownership."
            ),
        )

    def plan_batches(
        self,
        scopes: Iterable[ExecutionScope],
    ) -> tuple[tuple[ExecutionScope, ...], ...]:
        """Build conservative parallel batches from the given scopes."""
        return self.plan(scopes).batches

    def plan(self, scopes: Iterable[ExecutionScope]) -> ParallelBatchPlan:
        """Build conservative batches and retain scheduling denial reasons."""
        remaining = self._ordered_scopes(scopes)
        batches: list[tuple[ExecutionScope, ...]] = []
        notices: list[ParallelExecutionDecision] = []

        while remaining:
            batch: list[ExecutionScope] = []
            next_remaining: list[ExecutionScope] = []
            for scope in remaining:
                if not self._same_parallel_group(batch, scope):
                    next_remaining.append(scope)
                    continue
                decision = self.can_run_together((*batch, scope))
                if decision.allowed:
                    batch.append(scope)
                else:
                    notices.append(decision)
                    next_remaining.append(scope)

            if not batch:
                batch.append(next_remaining.pop(0))
            batches.append(tuple(batch))
            remaining = next_remaining

        return ParallelBatchPlan(
            batches=tuple(batches),
            notices=self._dedupe_notices(notices),
        )

    @classmethod
    def _has_disjoint_file_ownership(cls, scopes: list[ExecutionScope]) -> bool:
        """Return whether every writer has a non-overlapping ownership set."""
        seen: list[str] = []
        for scope in scopes:
            owned = cls._normalized_file_ownership(scope.file_ownership)
            if not owned:
                return False
            for path in owned:
                if any(cls._paths_overlap(path, existing) for existing in seen):
                    return False
            seen.extend(sorted(owned))
        return True

    @staticmethod
    def _is_high_risk(scope: ExecutionScope) -> bool:
        return scope.risk.strip().lower() == "high"

    @classmethod
    def _has_shared_write_path(cls, scope: ExecutionScope) -> bool:
        for normalized in cls._normalized_file_ownership(scope.file_ownership):
            if normalized in cls.SHARED_WRITE_PATHS:
                return True
            if normalized in cls.BROAD_WRITE_PATHS:
                return True
        return False

    @classmethod
    def _ordered_scopes(cls, scopes: Iterable[ExecutionScope]) -> list[ExecutionScope]:
        indexed = list(enumerate(scopes))
        indexed.sort(
            key=lambda item: (
                item[1].parallel_group is None,
                item[1].parallel_group if item[1].parallel_group is not None else 10**9,
                item[0],
            )
        )
        return [scope for _, scope in indexed]

    @staticmethod
    def _same_parallel_group(
        batch: list[ExecutionScope],
        scope: ExecutionScope,
    ) -> bool:
        if not batch:
            return True
        batch_group = batch[0].parallel_group
        if batch_group is None or scope.parallel_group is None:
            return True
        return batch_group == scope.parallel_group

    @classmethod
    def _dedupe_notices(
        cls,
        notices: Iterable[ParallelExecutionDecision],
    ) -> tuple[ParallelExecutionDecision, ...]:
        seen: set[tuple[str, tuple[str, ...]]] = set()
        deduped: list[ParallelExecutionDecision] = []
        for notice in notices:
            key = (notice.reason, notice.serialized_agents)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(notice)
        return tuple(deduped)

    @staticmethod
    def _normalized_file_ownership(paths: Iterable[str]) -> set[str]:
        normalized: set[str] = set()
        for path in paths:
            item = str(path).strip().replace("\\", "/").strip("/")
            if item:
                normalized.add(item)
        return normalized

    @staticmethod
    def _paths_overlap(left: str, right: str) -> bool:
        if left == right:
            return True
        return left.startswith(f"{right}/") or right.startswith(f"{left}/")
