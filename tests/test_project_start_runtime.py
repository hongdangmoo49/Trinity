from __future__ import annotations

from datetime import date

from trinity.project_intake import build_project_intake, write_project_intake
from trinity.textual_app.project_start_runtime import (
    project_intake_matches_workspace,
    project_setup_next_action,
)


def test_project_setup_next_action_requires_workspace_before_intake(tmp_path) -> None:
    assert (
        project_setup_next_action(
            tmp_path / ".trinity",
            None,
            ready_action="plan",
        )
        == "workspace"
    )


def test_project_setup_next_action_routes_existing_project_to_ready_action(
    tmp_path,
) -> None:
    state_dir = tmp_path / ".trinity"
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "README.md").write_text("# Customer App\n", encoding="utf-8")
    (target / "package.json").write_text(
        '{"scripts":{"test":"vitest run"}}',
        encoding="utf-8",
    )
    intake = build_project_intake(
        mode="existing",
        target_workspace=target,
        created_at=date.today().isoformat(),
    )
    write_project_intake(state_dir, intake)

    assert (
        project_setup_next_action(
            state_dir,
            target,
            ready_action="plan",
        )
        == "plan"
    )
    assert (
        project_setup_next_action(
            state_dir,
            str(target),
            ready_action="execute",
        )
        == "execute"
    )


def test_project_setup_next_action_routes_stale_existing_to_analyze_and_scope_choice(
    tmp_path,
) -> None:
    state_dir = tmp_path / ".trinity"
    target = tmp_path / "repo"
    target.mkdir()
    (target / "apps" / "web").mkdir(parents=True)
    (target / "apps" / "web" / "package.json").write_text(
        "{}",
        encoding="utf-8",
    )
    intake = build_project_intake(
        mode="existing",
        target_workspace=target,
        created_at=date.today().isoformat(),
    )
    write_project_intake(state_dir, intake)

    assert (
        project_setup_next_action(
            state_dir,
            target,
            ready_action="execute",
            analyze_variant="warning",
        )
        == "analyze"
    )
    assert (
        project_setup_next_action(
            state_dir,
            target,
            ready_action="execute",
        )
        == "scope"
    )

    write_project_intake(
        state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            selected_scope="apps/web",
            created_at=date.today().isoformat(),
        ),
    )
    assert (
        project_setup_next_action(
            state_dir,
            target,
            ready_action="execute",
        )
        == "validation"
    )

    write_project_intake(
        state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            selected_scope="apps/web",
            validation_commands=("npm test",),
            created_at=date.today().isoformat(),
        ),
    )
    assert (
        project_setup_next_action(
            state_dir,
            target,
            ready_action="execute",
        )
        == "execute"
    )


def test_project_setup_next_action_routes_new_project_setup_steps(tmp_path) -> None:
    state_dir = tmp_path / ".trinity"
    target = tmp_path / "new-app"
    write_project_intake(
        state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build an app.",
            created_at=date.today().isoformat(),
        ),
    )

    assert (
        project_setup_next_action(state_dir, target, ready_action="plan")
        == "create"
    )

    target.mkdir()
    write_project_intake(
        state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build an app.",
            created_at=date.today().isoformat(),
        ),
    )
    assert (
        project_setup_next_action(state_dir, target, ready_action="plan")
        == "brief"
    )

    write_project_intake(
        state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build an app.",
            project_type="tool",
            target_users="maintainers",
            success_criteria="Maintainers can run it.",
            first_milestone="First workflow.",
            created_at=date.today().isoformat(),
        ),
    )
    assert (
        project_setup_next_action(state_dir, target, ready_action="execute")
        == "validation"
    )

    write_project_intake(
        state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build an app.",
            project_type="tool",
            target_users="maintainers",
            success_criteria="Maintainers can run it.",
            first_milestone="First workflow.",
            validation_commands=("uv run pytest",),
            created_at=date.today().isoformat(),
        ),
    )
    assert (
        project_setup_next_action(state_dir, target, ready_action="execute")
        == "execute"
    )


def test_project_setup_next_action_routes_mismatched_or_invalid_intake_to_analyze(
    tmp_path,
) -> None:
    state_dir = tmp_path / ".trinity"
    target = tmp_path / "target"
    other = tmp_path / "other"
    target.mkdir()
    other.mkdir()
    write_project_intake(
        state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=other,
            created_at=date.today().isoformat(),
        ),
    )

    assert project_intake_matches_workspace(
        build_project_intake(
            mode="existing",
            target_workspace=other,
            created_at=date.today().isoformat(),
        ),
        target,
    ) is False
    assert (
        project_setup_next_action(state_dir, target, ready_action="plan")
        == "analyze"
    )

    (state_dir / "project-intake.json").write_text("{bad json", encoding="utf-8")
    assert (
        project_setup_next_action(state_dir, target, ready_action="plan")
        == "analyze"
    )
