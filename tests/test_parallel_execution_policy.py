"""Tests for provider execution authority and parallel execution policy."""

from pathlib import Path

from trinity.providers.policy import (
    ExecutionAuthority,
    ExecutionScope,
    InvocationAccess,
    ParallelExecutionPolicy,
)


def _scope(
    agent: str,
    *,
    access: InvocationAccess = InvocationAccess.READ_ONLY,
    cwd: Path | None = None,
    workspace_id: str | None = None,
    file_ownership: set[str] | None = None,
    parallelizable: bool = True,
    risk: str = "medium",
) -> ExecutionScope:
    return ExecutionScope(
        agent_name=agent,
        authority=ExecutionAuthority.PROVIDER_MANAGED,
        access=access,
        cwd=cwd,
        workspace_id=workspace_id,
        file_ownership=frozenset(file_ownership or set()),
        parallelizable=parallelizable,
        risk=risk,
    )


def test_read_only_provider_invocations_can_run_in_parallel(tmp_path):
    policy = ParallelExecutionPolicy()

    decision = policy.can_run_together(
        [
            _scope("claude", cwd=tmp_path),
            _scope("codex", cwd=tmp_path),
        ]
    )

    assert decision.allowed is True
    assert decision.serialized_agents == ()


def test_same_worktree_provider_managed_writes_are_serialized(tmp_path):
    policy = ParallelExecutionPolicy()

    decision = policy.can_run_together(
        [
            _scope("claude", access=InvocationAccess.WORKSPACE_WRITE, cwd=tmp_path),
            _scope("codex", access=InvocationAccess.WORKSPACE_WRITE, cwd=tmp_path),
        ]
    )

    assert decision.allowed is False
    assert decision.serialized_agents == ("claude", "codex")
    assert "workspace-write" in decision.reason


def test_separate_worktrees_allow_provider_managed_writes(tmp_path):
    policy = ParallelExecutionPolicy()

    decision = policy.can_run_together(
        [
            _scope(
                "claude",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path / "wt-claude",
            ),
            _scope(
                "codex",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path / "wt-codex",
            ),
        ]
    )

    assert decision.allowed is True


def test_disjoint_file_ownership_allows_same_worktree_writes(tmp_path):
    policy = ParallelExecutionPolicy()

    decision = policy.can_run_together(
        [
            _scope(
                "claude",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"src/trinity/config.py"},
            ),
            _scope(
                "codex",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"tests/test_config.py"},
            ),
        ]
    )

    assert decision.allowed is True


def test_non_parallelizable_write_serializes_same_worktree(tmp_path):
    policy = ParallelExecutionPolicy()

    decision = policy.can_run_together(
        [
            _scope(
                "claude",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"src/a.py"},
                parallelizable=False,
            ),
            _scope(
                "codex",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"src/b.py"},
            ),
        ]
    )

    assert decision.allowed is False
    assert "non-parallelizable" in decision.reason


def test_high_risk_write_serializes_same_worktree(tmp_path):
    policy = ParallelExecutionPolicy()

    decision = policy.can_run_together(
        [
            _scope(
                "claude",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"src/a.py"},
                risk="high",
            ),
            _scope(
                "codex",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"src/b.py"},
            ),
        ]
    )

    assert decision.allowed is False
    assert "high-risk" in decision.reason


def test_shared_workspace_file_serializes_same_worktree(tmp_path):
    policy = ParallelExecutionPolicy()

    decision = policy.can_run_together(
        [
            _scope(
                "claude",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"pyproject.toml"},
            ),
            _scope(
                "codex",
                access=InvocationAccess.WORKSPACE_WRITE,
                cwd=tmp_path,
                file_ownership={"tests/test_config.py"},
            ),
        ]
    )

    assert decision.allowed is False
    assert "shared workspace files" in decision.reason


def test_plan_batches_splits_colliding_provider_managed_writes(tmp_path):
    policy = ParallelExecutionPolicy()
    read_only = _scope("antigravity", cwd=tmp_path)
    claude_write = _scope(
        "claude",
        access=InvocationAccess.WORKSPACE_WRITE,
        cwd=tmp_path,
    )
    codex_write = _scope(
        "codex",
        access=InvocationAccess.WORKSPACE_WRITE,
        cwd=tmp_path,
    )

    batches = policy.plan_batches([read_only, claude_write, codex_write])

    assert [[scope.agent_name for scope in batch] for batch in batches] == [
        ["antigravity", "claude"],
        ["codex"],
    ]
