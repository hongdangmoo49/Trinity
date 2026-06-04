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


class ParallelExecutionPolicy:
    """Decide whether provider invocations may run in the same batch."""

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
        remaining = list(scopes)
        batches: list[tuple[ExecutionScope, ...]] = []

        while remaining:
            batch: list[ExecutionScope] = []
            next_remaining: list[ExecutionScope] = []
            for scope in remaining:
                decision = self.can_run_together((*batch, scope))
                if decision.allowed:
                    batch.append(scope)
                else:
                    next_remaining.append(scope)

            if not batch:
                batch.append(next_remaining.pop(0))
            batches.append(tuple(batch))
            remaining = next_remaining

        return tuple(batches)

    @staticmethod
    def _has_disjoint_file_ownership(scopes: list[ExecutionScope]) -> bool:
        """Return whether every writer has a non-overlapping ownership set."""
        seen: set[str] = set()
        for scope in scopes:
            owned = set(scope.file_ownership)
            if not owned:
                return False
            if seen.intersection(owned):
                return False
            seen.update(owned)
        return True
