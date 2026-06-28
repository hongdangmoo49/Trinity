from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from trinity.project_intake import (
    analyze_git_workspace,
    build_project_intake,
    detect_docs,
    detect_entrypoints,
    existing_project_intake_drift_fields,
    detect_package_managers,
    detect_source_roots,
    load_project_intake,
    load_project_intake_markdown,
    missing_new_project_brief_field_keys,
    missing_new_project_brief_fields,
    project_intake_guidance_block,
    project_intake_prompt_block,
    suggest_build_commands,
    suggest_dev_commands,
    suggest_test_commands,
    write_project_intake,
)


def _run_git(tmp_path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_analyze_git_workspace_reports_non_git_path(tmp_path) -> None:
    analysis = analyze_git_workspace(tmp_path)

    assert analysis.git_repo is False
    assert analysis.branch == "(none)"
    assert analysis.dirty_count is None
    assert analysis.untracked_count is None


def test_analyze_git_workspace_counts_dirty_and_untracked_entries(tmp_path) -> None:
    _run_git(tmp_path, "init")
    (tmp_path / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("new\n", encoding="utf-8")
    _run_git(tmp_path, "add", "tracked.txt")

    analysis = analyze_git_workspace(tmp_path)

    assert analysis.git_repo is True
    assert analysis.branch != "(none)"
    assert analysis.dirty_count == 1
    assert analysis.untracked_count == 1


def test_detect_package_managers_and_test_commands(tmp_path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "build": "vite build",
                    "dev": "vite --host",
                    "test": "vitest run",
                },
                "main": "dist/index.js",
                "bin": {"demo": "bin/demo.js"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")

    managers = detect_package_managers(tmp_path)

    assert managers == ("uv", "pnpm")
    assert suggest_test_commands(tmp_path, managers) == (
        "pnpm test",
        "uv run pytest",
    )
    assert suggest_dev_commands(tmp_path, managers) == ("pnpm dev",)
    assert suggest_build_commands(tmp_path, managers) == ("pnpm build",)
    assert detect_entrypoints(tmp_path, managers) == (
        "dist/index.js",
        "demo -> bin/demo.js",
    )
    assert detect_source_roots(tmp_path) == ("src",)
    assert detect_docs(tmp_path) == ("README.md", "docs")


def test_python_project_profile_detects_scripts_and_build_backend(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                "requires = ['hatchling']",
                "build-backend = 'hatchling.build'",
                "",
                "[project]",
                "name = 'demo'",
                "",
                "[project.scripts]",
                "demo = 'demo.cli:main'",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "manage.py").write_text("print('run')\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    managers = detect_package_managers(tmp_path)

    assert managers == ("uv",)
    assert detect_entrypoints(tmp_path, managers) == (
        "demo -> demo.cli:main",
        "manage.py",
    )
    assert suggest_dev_commands(tmp_path, managers) == (
        "python manage.py runserver",
    )
    assert suggest_build_commands(tmp_path, managers) == ("python -m build",)
    assert detect_source_roots(tmp_path) == ("tests",)


def test_build_project_intake_normalizes_metadata(tmp_path) -> None:
    _run_git(tmp_path, "init")
    (tmp_path / "notes.txt").write_text("new\n", encoding="utf-8")

    intake = build_project_intake(
        mode=" Existing ",
        target_workspace=tmp_path,
        product_goal="Ship a workflow dashboard.",
        project_type="developer tool",
        target_users="solo maintainers",
        success_criteria="The user can start safely.",
        stack_preferences=["python", "textual", "python"],
        first_milestone="Show project intake state.",
        constraints=["read-only analysis", "read-only analysis"],
        notes="Review before write.",
        created_at="2026-06-28T00:00:00Z",
    )

    assert intake.mode == "existing"
    assert intake.target_workspace == tmp_path.resolve()
    assert intake.created_at == "2026-06-28T00:00:00Z"
    assert intake.git_repo is True
    assert intake.dirty_count == 0
    assert intake.untracked_count == 1
    assert intake.dev_commands == ()
    assert intake.build_commands == ()
    assert intake.entrypoints == ()
    assert intake.source_roots == ()
    assert intake.docs_found == ()
    assert intake.product_goal == "Ship a workflow dashboard."
    assert intake.project_type == "developer tool"
    assert intake.target_users == "solo maintainers"
    assert intake.success_criteria == "The user can start safely."
    assert intake.stack_preferences == ("python", "textual")
    assert intake.first_milestone == "Show project intake state."
    assert intake.constraints == ("read-only analysis",)
    assert intake.notes == "Review before write."


def test_existing_project_intake_drift_ignores_unchanged_analysis(
    tmp_path,
) -> None:
    (tmp_path / "README.md").write_text("docs\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    intake = build_project_intake(
        mode="existing",
        target_workspace=tmp_path,
        created_at="2026-06-29T00:00:00Z",
    )

    assert existing_project_intake_drift_fields(intake, tmp_path) == ()


def test_existing_project_intake_drift_detects_changed_analysis_anchors(
    tmp_path,
) -> None:
    (tmp_path / "README.md").write_text("docs\n", encoding="utf-8")
    intake = build_project_intake(
        mode="existing",
        target_workspace=tmp_path,
        created_at="2026-06-29T00:00:00Z",
    )

    (tmp_path / "src").mkdir()

    assert existing_project_intake_drift_fields(intake, tmp_path) == (
        "source_roots",
    )


def test_existing_project_intake_drift_detects_changed_git_state(
    tmp_path,
) -> None:
    _run_git(tmp_path, "init")
    (tmp_path / "README.md").write_text("docs\n", encoding="utf-8")
    _run_git(tmp_path, "add", "README.md")
    _run_git(
        tmp_path,
        "-c",
        "user.name=Trinity Test",
        "-c",
        "user.email=trinity@example.com",
        "commit",
        "-m",
        "initial",
    )
    intake = build_project_intake(
        mode="existing",
        target_workspace=tmp_path,
        created_at="2026-06-29T00:00:00Z",
    )

    (tmp_path / "notes.txt").write_text("new\n", encoding="utf-8")

    assert existing_project_intake_drift_fields(intake, tmp_path) == (
        "untracked_count",
    )


def test_build_project_intake_rejects_unknown_mode(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unsupported project intake mode"):
        build_project_intake(mode="repair", target_workspace=tmp_path)


def test_missing_new_project_brief_fields_only_apply_to_new_projects(
    tmp_path,
) -> None:
    partial = build_project_intake(
        mode="new",
        target_workspace=tmp_path / "new-app",
        product_goal="Build a workflow dashboard.",
        created_at="2026-06-28T00:00:00Z",
    )
    complete = build_project_intake(
        mode="new",
        target_workspace=tmp_path / "complete-app",
        product_goal="Build a workflow dashboard.",
        project_type="developer tool",
        target_users="maintainers",
        success_criteria="The first workflow can be completed.",
        first_milestone="Playable prototype.",
        created_at="2026-06-28T00:00:00Z",
    )
    existing = build_project_intake(
        mode="existing",
        target_workspace=tmp_path,
        created_at="2026-06-28T00:00:00Z",
    )

    assert missing_new_project_brief_field_keys(partial) == (
        "project_type",
        "target_users",
        "success_criteria",
        "first_milestone",
    )
    assert missing_new_project_brief_fields(partial) == (
        "type",
        "users",
        "success",
        "milestone",
    )
    assert missing_new_project_brief_fields(complete) == ()
    assert missing_new_project_brief_fields(existing) == ()


def test_write_project_intake_writes_json_and_markdown(tmp_path) -> None:
    intake = build_project_intake(
        mode="new",
        target_workspace=tmp_path / "new-app",
        product_goal="Build a terminal snake game.",
        project_type="terminal game",
        target_users="local CLI users",
        success_criteria="The game can be played with keyboard controls.",
        stack_preferences=("python", "textual"),
        first_milestone="Playable local prototype.",
        constraints=("No network dependency",),
        created_at="2026-06-28T00:00:00Z",
    )

    paths = write_project_intake(tmp_path / ".trinity", intake)

    data = json.loads(paths.json_path.read_text(encoding="utf-8"))
    markdown = paths.markdown_path.read_text(encoding="utf-8")
    assert data["mode"] == "new"
    assert data["target_workspace"] == str((tmp_path / "new-app").resolve())
    assert data["git_repo"] is False
    assert data["dev_commands"] == []
    assert data["build_commands"] == []
    assert data["entrypoints"] == []
    assert data["source_roots"] == []
    assert data["docs_found"] == []
    assert data["product_goal"] == "Build a terminal snake game."
    assert data["project_type"] == "terminal game"
    assert data["target_users"] == "local CLI users"
    assert data["success_criteria"] == (
        "The game can be played with keyboard controls."
    )
    assert data["stack_preferences"] == ["python", "textual"]
    assert data["first_milestone"] == "Playable local prototype."
    assert data["constraints"] == ["No network dependency"]
    assert paths.json_path.name == "project-intake.json"
    assert paths.markdown_path.name == "project-intake.md"
    assert "# Project Intake" in markdown
    assert "- Mode: new" in markdown
    assert "- Git repo: False" in markdown
    assert "- Dev commands: (none)" in markdown
    assert "- Entrypoints: (none)" in markdown
    assert "## Brief" in markdown
    assert "- Product goal: Build a terminal snake game." in markdown
    assert "- Project type: terminal game" in markdown
    assert "- Target users: local CLI users" in markdown
    assert "- Success criteria: The game can be played" in markdown
    assert "- Stack preferences: python, textual" in markdown
    assert "- First milestone: Playable local prototype." in markdown
    assert "- Constraints: No network dependency" in markdown


def test_load_project_intake_reads_persisted_json(tmp_path) -> None:
    intake = build_project_intake(
        mode="existing",
        target_workspace=tmp_path,
        notes="Use recorded context.",
        created_at="2026-06-28T00:00:00Z",
    )
    paths = write_project_intake(tmp_path / ".trinity", intake)

    loaded = load_project_intake(paths.json_path.parent)

    assert loaded is not None
    assert loaded.mode == "existing"
    assert loaded.target_workspace == tmp_path.resolve()
    assert loaded.created_at == "2026-06-28T00:00:00Z"
    assert loaded.dev_commands == ()
    assert loaded.build_commands == ()
    assert loaded.entrypoints == ()
    assert loaded.source_roots == ()
    assert loaded.docs_found == ()
    assert loaded.product_goal == ""
    assert loaded.project_type == ""
    assert loaded.target_users == ""
    assert loaded.success_criteria == ""
    assert loaded.stack_preferences == ()
    assert loaded.first_milestone == ""
    assert loaded.constraints == ()
    assert loaded.notes == "Use recorded context."


def test_load_project_intake_accepts_legacy_profile_fields_missing(tmp_path) -> None:
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "project-intake.json").write_text(
        json.dumps(
            {
                "mode": "existing",
                "target_workspace": str(tmp_path),
                "created_at": "2026-06-28T00:00:00Z",
                "git_repo": False,
                "branch": "(none)",
                "dirty_count": None,
                "untracked_count": None,
                "package_managers": [],
                "test_commands": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_project_intake(state)

    assert loaded is not None
    assert loaded.dev_commands == ()
    assert loaded.build_commands == ()
    assert loaded.entrypoints == ()
    assert loaded.source_roots == ()
    assert loaded.docs_found == ()
    assert loaded.product_goal == ""
    assert loaded.project_type == ""
    assert loaded.target_users == ""
    assert loaded.success_criteria == ""
    assert loaded.stack_preferences == ()
    assert loaded.first_milestone == ""
    assert loaded.constraints == ()


def test_project_intake_prompt_block_loads_and_truncates_markdown(tmp_path) -> None:
    state = tmp_path / ".trinity"
    state.mkdir()
    (state / "project-intake.md").write_text(
        "# Project Intake\n\n" + ("x" * 20),
        encoding="utf-8",
    )

    assert load_project_intake_markdown(state, max_chars=10).endswith("[truncated]")
    block = project_intake_prompt_block(state, max_chars=10)
    assert block.startswith("Project Intake Context:\n# Project")
    assert "[truncated]" in block


def test_project_intake_prompt_block_includes_existing_project_guidance(
    tmp_path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "README.md").write_text("# Customer App\n", encoding="utf-8")
    (target / "src").mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            product_goal="Improve customer onboarding.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    guidance = project_intake_guidance_block(state)
    block = project_intake_prompt_block(state)

    assert "existing project under discussion" in guidance
    assert "Read detected docs, entrypoints, and source roots" in block
    assert "Use recorded brief fields as user intent" in block
    assert "- Docs found: README.md" in block


def test_project_intake_prompt_block_includes_incomplete_new_project_guidance(
    tmp_path,
) -> None:
    target = tmp_path / "new-app"
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build a dashboard.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    guidance = project_intake_guidance_block(state)
    block = project_intake_prompt_block(state)

    assert "fresh project workspace" in guidance
    assert "new-project brief is incomplete" in block
    assert "type, users, success, milestone" in block
    assert "Do not treat framework, architecture, or UX choices as final" in block
    assert "- Mode: new" in block


def test_project_intake_prompt_block_includes_complete_new_project_guidance(
    tmp_path,
) -> None:
    target = tmp_path / "new-app"
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build a dashboard.",
            project_type="SaaS dashboard",
            target_users="support operators",
            success_criteria="Operators can complete onboarding.",
            stack_preferences=("python", "textual"),
            first_milestone="First safe patch.",
            constraints=("Keep tests green",),
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    guidance = project_intake_guidance_block(state)
    block = project_intake_prompt_block(state)

    assert "new-project brief is complete" in guidance
    assert "use the recorded goal, type, users, success criteria" in block
    assert "recorded success criteria and constraints" in block
    assert "- Success criteria: Operators can complete onboarding." in block


def test_project_intake_prompt_block_returns_empty_when_missing(tmp_path) -> None:
    assert project_intake_prompt_block(tmp_path / ".trinity") == ""
