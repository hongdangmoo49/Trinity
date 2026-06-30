from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from trinity.project_intake import build_project_intake
from trinity.textual_app.widgets.project_generation_confirm_modal import (
    ProjectGenerationConfirmationSummary,
    ProjectGenerationConfirmModal,
    project_generation_confirmation_summary,
)


def test_project_generation_confirmation_summary_uses_generation_preview(
    tmp_path,
) -> None:
    intake = build_project_intake(
        mode="new",
        target_workspace=tmp_path,
        product_goal="Build a planning board.",
        project_type="textual app",
        target_users="operators",
        success_criteria="Operators can plan weekly work.",
        stack_preferences=("python", "textual"),
        first_milestone="First board workflow.",
        validation_commands=("uv run pytest",),
        constraints=("No external service",),
    )

    summary = project_generation_confirmation_summary(intake)

    assert summary.target_workspace == str(tmp_path.resolve())
    assert summary.available is True
    assert summary.generation_preview == (
        "Generation preview: create: README.md, pyproject.toml, src/ +1 | "
        "validate: uv run pytest | guardrails: No external service"
    )
    assert summary.dry_run_lines == (
        "create: README.md, pyproject.toml, src/, tests/",
        "validate: uv run pytest",
        "guardrails: No external service",
        "conflicts: none",
    )
    assert summary.validation_plan == (
        "Validation plan: fast: uv run pytest | "
        "required: uv run pytest | "
        "full: first scaffold smoke before release"
    )


def test_project_generation_confirmation_summary_supports_korean(tmp_path) -> None:
    intake = build_project_intake(
        mode="new",
        target_workspace=tmp_path,
        product_goal="작업 보드를 만든다.",
        project_type="textual app",
        target_users="운영자",
        success_criteria="운영자가 주간 작업을 계획한다.",
        stack_preferences=("python", "textual"),
        first_milestone="첫 보드 흐름.",
        validation_commands=("uv run pytest",),
    )

    summary = project_generation_confirmation_summary(intake, lang="ko")

    assert summary.available is True
    assert summary.generation_preview.startswith("생성 미리보기: ")
    assert "검증: uv run pytest" in summary.generation_preview
    assert summary.dry_run_lines[0].startswith("생성: ")
    assert "검증: uv run pytest" in summary.dry_run_lines
    assert summary.validation_plan.startswith("검증 계획: ")


def test_project_generation_confirmation_summary_reports_dry_run_gaps(
    tmp_path,
) -> None:
    (tmp_path / "README.md").write_text("# Existing\n", encoding="utf-8")
    intake = build_project_intake(
        mode="new",
        target_workspace=tmp_path,
        product_goal="Build a CLI package.",
        project_type="python cli",
        target_users="developers",
        success_criteria="Developers can run the command.",
        stack_preferences=("python",),
        first_milestone="First command.",
    )

    summary = project_generation_confirmation_summary(intake)

    assert "validate: missing (suggested: uv run pytest)" in summary.dry_run_lines
    assert "conflicts: README.md" in summary.dry_run_lines


@pytest.mark.asyncio
async def test_project_generation_confirm_modal_keeps_actions_inside_narrow_viewport() -> None:
    summary = ProjectGenerationConfirmationSummary(
        target_workspace="/workspace/" + "long-target-directory-" * 8,
        generation_preview=(
            "Generation preview: "
            + "create many files with long generated names, " * 16
        ),
        validation_plan=(
            "Validation plan: "
            + "run a long validation command before release, " * 16
        ),
        dry_run_lines=tuple(
            f"dry-run-{index}: create generated-file-{index}-with-a-long-name.py"
            for index in range(16)
        ),
    )

    class ProbeApp(App[None]):
        def compose(self) -> ComposeResult:
            yield Static("root")

        def on_mount(self) -> None:
            self.push_screen(ProjectGenerationConfirmModal(summary, lang="en"))

    app = ProbeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        modal = app.screen
        shell = modal.query_one("#project-generation-confirm-modal")

        for widget_id in (
            "#project-generation-confirm-title",
            "#project-generation-confirm-body",
            "#project-generation-confirm-content",
            "#project-generation-confirm-actions",
            "#cancel-project-generation-confirm",
            "#confirm-project-generation",
        ):
            widget = modal.query_one(widget_id)
            assert widget.region.y >= shell.region.y
            assert widget.region.y + widget.region.height <= (
                shell.region.y + shell.region.height
            )
