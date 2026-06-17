"""Tests for provider permission argument policy."""

from pathlib import Path

from trinity.models import Provider
from trinity.providers.permissions import ProviderPermissionPolicy
from trinity.providers.policy import InvocationAccess


def test_claude_read_only_uses_plan_mode_and_filters_bypass() -> None:
    plan = ProviderPermissionPolicy().plan(
        provider=Provider.CLAUDE_CODE,
        access=InvocationAccess.READ_ONLY,
        cwd=Path("/workspace"),
        extra_args=(
            "--dangerously-skip-permissions",
            "--permission-mode",
            "bypassPermissions",
            "--tools=Edit,Bash",
            "--no-session-persistence",
        ),
    )

    assert plan.args == (
        "--permission-mode",
        "plan",
        "--tools",
        "Read,LS,Grep,Glob",
    )
    assert plan.extra_args == ("--no-session-persistence",)
    assert any("removed_dangerous_arg" in item for item in plan.diagnostics)
    assert any("removed_controlled_arg:--permission-mode" in item for item in plan.diagnostics)
    assert any("removed_controlled_arg:--tools" in item for item in plan.diagnostics)


def test_claude_workspace_write_uses_accept_edits_and_filters_bypass() -> None:
    plan = ProviderPermissionPolicy().plan(
        provider=Provider.CLAUDE_CODE,
        access=InvocationAccess.WORKSPACE_WRITE,
        cwd=Path("/workspace"),
        extra_args=(
            "--permission-mode=default",
            "--allow-dangerously-skip-permissions",
            "--debug",
        ),
    )

    assert plan.args == ("--permission-mode", "acceptEdits")
    assert plan.extra_args == ("--debug",)
    assert any("removed_controlled_arg:--permission-mode" in item for item in plan.diagnostics)
    assert any("removed_dangerous_arg" in item for item in plan.diagnostics)


def test_codex_policy_owns_sandbox_cd_and_strips_escape_hatches() -> None:
    plan = ProviderPermissionPolicy().plan(
        provider=Provider.CODEX,
        access=InvocationAccess.WORKSPACE_WRITE,
        cwd=Path("/workspace"),
        extra_args=(
            "--sandbox",
            "danger-full-access",
            "--cd=/tmp/other",
            "--add-dir",
            "/tmp/other",
            "--dangerously-bypass-approvals-and-sandbox",
            "--ignore-rules",
        ),
    )

    assert plan.args == ("--sandbox", "workspace-write", "--cd", "/workspace")
    assert plan.extra_args == ("--ignore-rules",)
    assert any("removed_controlled_arg:--sandbox" in item for item in plan.diagnostics)
    assert any("removed_controlled_arg:--cd" in item for item in plan.diagnostics)
    assert any("removed_controlled_arg:--add-dir" in item for item in plan.diagnostics)
    assert any("removed_dangerous_arg" in item for item in plan.diagnostics)


def test_antigravity_policy_filters_bypass_and_controls_sandbox() -> None:
    read_only = ProviderPermissionPolicy().plan(
        provider=Provider.ANTIGRAVITY_CLI,
        access=InvocationAccess.READ_ONLY,
        cwd=Path("/workspace"),
        extra_args=("--dangerously-skip-permissions", "--log-file", "agy.log"),
    )
    write = ProviderPermissionPolicy().plan(
        provider=Provider.ANTIGRAVITY_CLI,
        access=InvocationAccess.WORKSPACE_WRITE,
        cwd=Path("/workspace"),
        extra_args=("--sandbox", "--log-file", "agy.log"),
    )

    assert read_only.args == ("--sandbox",)
    assert read_only.extra_args == ("--log-file", "agy.log")
    assert write.args == ()
    assert write.extra_args == ("--log-file", "agy.log")
    assert any("removed_dangerous_arg" in item for item in read_only.diagnostics)
    assert any("removed_dangerous_arg:--sandbox" in item for item in write.diagnostics)
