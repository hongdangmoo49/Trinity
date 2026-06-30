from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.textual_app.snapshot import (
    ProviderSnapshot,
    WorkPackageSnapshot,
    WorkflowNexusSnapshot,
)
from trinity.textual_app.widgets.execution_confirm_modal import (
    ExecutionConfirmationSummary,
    ExecutionConfirmModal,
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
    assert summary.estimated_execution_runs == 1
    assert summary.estimated_review_runs == 0
    assert summary.estimated_agent_runs == 1
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


def test_execution_confirmation_summary_estimates_peer_review_runs() -> None:
    snapshot = WorkflowNexusSnapshot(
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status="Ready",
            ),
            ProviderSnapshot(
                name="codex",
                provider="codex-cli",
                enabled=True,
                status="Ready",
            ),
        ],
        work_package_details=[
            WorkPackageSnapshot(
                id="WP-001",
                title="Build CLI",
                owner_agent="codex",
                status="pending",
            ),
            WorkPackageSnapshot(
                id="WP-002",
                title="Build TUI",
                owner_agent="claude",
                status="pending",
            ),
            WorkPackageSnapshot(
                id="WP-003",
                title="Write notes",
                owner_agent="claude",
                status="pending",
                requires_execution=False,
            ),
        ],
    )

    summary = execution_confirmation_summary(snapshot)

    assert summary.executable_packages == 2
    assert summary.estimated_execution_runs == 2
    assert summary.estimated_review_runs == 2
    assert summary.estimated_agent_runs == 4


def test_execution_confirmation_modal_shows_agent_run_estimate() -> None:
    snapshot = WorkflowNexusSnapshot(
        providers=[
            ProviderSnapshot(
                name="claude",
                provider="claude-code",
                enabled=True,
                status="Ready",
            ),
            ProviderSnapshot(
                name="codex",
                provider="codex-cli",
                enabled=True,
                status="Ready",
            ),
        ],
        work_packages=("WP-001 codex: Build CLI",),
    )
    summary = execution_confirmation_summary(snapshot)

    assert "Agent runs: 2 approx (1 execution, 1 review)" in (
        ExecutionConfirmModal(summary)._summary_text()
    )


@pytest.mark.asyncio
async def test_execution_confirmation_modal_keeps_actions_inside_narrow_viewport() -> None:
    summary = ExecutionConfirmationSummary(
        target_workspace="/workspace/" + "long-target-directory-" * 8,
        project_mode="existing-project-with-long-mode-name",
        context_items=tuple(f"context-item-{index}-with-long-text" for index in range(8)),
        providers=("claude", "codex", "antigravity"),
        total_packages=12,
        executable_packages=10,
        estimated_execution_runs=10,
        estimated_review_runs=10,
        package_preview=tuple(
            f"WP-{index:03d} owner: long package preview title {'x' * 40}"
            for index in range(8)
        ),
        risk_items=tuple(f"risk-{index}-long-risk-description" for index in range(6)),
        instruction="long execution instruction " * 30,
    )

    class ProbeApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("root")

        def on_mount(self) -> None:
            self.push_screen(ExecutionConfirmModal(summary, lang="en"))

    app = ProbeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        modal = app.screen
        shell = modal.query_one("#execution-confirm-modal")

        for widget_id in (
            "#execution-confirm-title",
            "#execution-confirm-body",
            "#execution-confirm-content",
            "#execution-confirm-actions",
            "#cancel-execution-confirm",
            "#confirm-execution",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
