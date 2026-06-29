from __future__ import annotations

from trinity.textual_app.snapshot import (
    ProviderSnapshot,
    WorkPackageSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.widgets.execution_confirm_modal import (
    execution_confirmation_summary,
)


def test_execution_confirmation_summary_uses_snapshot_details() -> None:
    snapshot = WorkflowNexusSnapshot(
        target_workspace="/workspace/app",
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status="Ready",
            ),
            ProviderSnapshot(
                name="agy",
                provider="antigravity-cli",
                enabled=False,
                status="Ready",
            ),
        ],
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build API",
                owner_agent="codex",
                status="pending",
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Update docs",
                owner_agent="claude",
                status="pending",
                requires_execution=False,
            ),
        ],
    )

    summary = execution_confirmation_summary(
        snapshot,
        project_mode="existing",
        instruction="focus api",
    )

    assert summary.target_workspace == "/workspace/app"
    assert summary.project_mode == "existing"
    assert summary.providers == ("claude",)
    assert summary.total_packages == 2
    assert summary.executable_packages == 1
    assert summary.package_preview == (
        "WP-001 codex: Build API",
        "WP-002 claude: Update docs",
    )
    assert summary.instruction == "focus api"


def test_execution_confirmation_summary_falls_back_to_package_lines() -> None:
    snapshot = WorkflowNexusSnapshot(
        work_packages=[
            "WP-001 codex: Build CLI",
            "WP-002 claude: Document flow",
        ],
    )

    summary = execution_confirmation_summary(snapshot)

    assert summary.total_packages == 2
    assert summary.executable_packages == 2
    assert summary.package_preview == (
        "WP-001 codex: Build CLI",
        "WP-002 claude: Document flow",
    )
