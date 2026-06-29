from __future__ import annotations

from trinity.project_intake import build_project_intake
from trinity.textual_app.widgets.project_generation_confirm_modal import (
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
    assert summary.validation_plan.startswith("검증 계획: ")
