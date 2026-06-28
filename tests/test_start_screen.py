from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Static

from trinity.config import TrinityConfig
from trinity.project_intake import build_project_intake, write_project_intake
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.workspace_labels import (
    project_intake_state_label,
    target_workspace_state_label,
)
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)


class StartScreenHarness(App[None]):
    def __init__(self, screen: StartScreen) -> None:
        super().__init__()
        self.target_screen = screen

    def on_mount(self) -> None:
        self.push_screen(self.target_screen)


class _DisplayPath:
    def __init__(self, text: str) -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text


def _run_git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_target_workspace_state_label_distinguishes_project_states(
    tmp_path: Path,
) -> None:
    control_repo = tmp_path / "Trinity"
    target = tmp_path / "customer-app"
    control_repo.mkdir()
    target.mkdir()

    assert (
        target_workspace_state_label(None, control_repo=control_repo)
        == "No target workspace selected"
    )
    assert target_workspace_state_label(
        target,
        control_repo=control_repo,
    ) == f"Planning target: {target}"
    assert target_workspace_state_label(
        control_repo,
        control_repo=control_repo,
    ) == (
        "Control repo selected; confirmation required before write: "
        f"{control_repo}"
    )
    assert target_workspace_state_label(
        target,
        control_repo=control_repo,
        lang="ko",
    ) == f"계획 대상: {target}"


def test_project_intake_state_label_summarizes_saved_intake(tmp_path: Path) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "pyproject.toml").write_text(
        "[project]\nname='customer-app'\n",
        encoding="utf-8",
    )
    (target / "uv.lock").write_text("", encoding="utf-8")
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert (
        project_intake_state_label(state)
        == "Project intake: existing | tests: uv run pytest | git: none"
    )
    assert (
        project_intake_state_label(state, lang="ko")
        == "프로젝트 인테이크: 기존 | 테스트: uv run pytest | git: 없음"
    )


def test_project_intake_state_label_includes_workspace_profile(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "package.json").write_text(
        (
            '{"scripts":{"build":"vite build","dev":"vite --host"},'
            '"main":"dist/index.js","bin":{"customer":"bin/customer.js"}}'
        ),
        encoding="utf-8",
    )
    (target / "README.md").write_text("# Customer App\n", encoding="utf-8")
    (target / "docs").mkdir()
    (target / "src").mkdir()
    (target / "tests").mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            product_goal="Launch customer onboarding.",
            project_type="SaaS dashboard",
            target_users="support operators",
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert project_intake_state_label(state) == (
        "Project intake: existing | tests: (none) | "
        "git: none | "
        "goal: Launch customer onboarding. | type: SaaS dashboard | "
        "users: support operators | dev: npm run dev | build: npm run build "
        "| src: src, tests "
        "| entry: dist/index.js, customer -> bin/customer.js | "
        "docs: README.md, docs"
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 인테이크: 기존 | 테스트: (없음) | "
        "git: 없음 | "
        "목표: Launch customer onboarding. | 유형: SaaS dashboard | "
        "사용자: support operators | 개발: npm run dev | 빌드: npm run build "
        "| 소스: src, tests "
        "| 진입점: dist/index.js, customer -> bin/customer.js | "
        "문서: README.md, docs"
    )


def test_project_intake_state_label_includes_existing_project_git_state(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    _run_git(target, "init")
    _run_git(target, "config", "user.email", "test@example.com")
    _run_git(target, "config", "user.name", "Trinity Test")
    (target / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _run_git(target, "add", "tracked.txt")
    _run_git(target, "commit", "-m", "initial")
    (target / "tracked.txt").write_text("changed\n", encoding="utf-8")
    (target / "notes.txt").write_text("new\n", encoding="utf-8")
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    branch = project_intake_state_label(state).split("git: ", 1)[1].split(" ", 1)[0]

    assert f"git: {branch} dirty 1, untracked 1" in project_intake_state_label(state)
    assert (
        f"git: {branch} 변경 1, 미추적 1"
        in project_intake_state_label(state, lang="ko")
    )


def test_project_intake_state_label_shows_new_project_brief_readiness(
    tmp_path: Path,
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

    assert project_intake_state_label(state) == (
        "Project intake: new | tests: (none) | "
        "brief: missing type, users +2 | goal: Build a dashboard."
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 인테이크: 신규 | 테스트: (없음) | "
        "브리프: 누락 유형, 사용자 +2 | 목표: Build a dashboard."
    )

    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build a dashboard.",
            project_type="SaaS dashboard",
            target_users="support operators",
            success_criteria="Operators can complete onboarding.",
            first_milestone="First safe patch.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert "brief: complete" in project_intake_state_label(state)


def test_project_intake_state_label_guides_missing_intake(tmp_path: Path) -> None:
    state = tmp_path / ".trinity"

    assert project_intake_state_label(state) == (
        "Project intake: not recorded | existing: trinity project analyze [PATH] "
        "| new: trinity project new NAME"
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 인테이크: 기록 없음 | 기존: trinity project analyze [PATH] "
        "| 신규: trinity project new NAME"
    )


def test_nexus_workspace_label_uses_target_state_helper(tmp_path: Path) -> None:
    control_repo = tmp_path / "Trinity"
    target = tmp_path / "customer-app"
    control_repo.mkdir()
    target.mkdir()
    screen = NexusScreen(TrinityConfig.default_config(project_dir=control_repo))

    assert screen._workspace_label() == "No target workspace selected"

    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(target))
    assert screen._workspace_label() == f"Planning target: {target}"

    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(control_repo))
    assert screen._workspace_label() == (
        "Control repo selected; confirmation required before write: "
        f"{control_repo}"
    )


@pytest.mark.asyncio
async def test_start_screen_shows_project_intake_summary(tmp_path: Path) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "pyproject.toml").write_text(
        "[project]\nname='customer-app'\n",
        encoding="utf-8",
    )
    (target / "uv.lock").write_text("", encoding="utf-8")
    config = TrinityConfig.default_config(project_dir=tmp_path)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    screen = StartScreen(config, workspace_candidate=target)
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert str(screen.query_one("#project-intake-summary", Static).content) == (
            "Project intake: existing | tests: uv run pytest | git: none"
        )


@pytest.mark.asyncio
async def test_nexus_screen_shows_project_intake_summary(tmp_path: Path) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "pyproject.toml").write_text(
        "[project]\nname='customer-app'\n",
        encoding="utf-8",
    )
    (target / "uv.lock").write_text("", encoding="utf-8")
    config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    screen = NexusScreen(config)
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert str(
            screen.query_one("#nexus-project-intake-summary", Static).content
        ) == "프로젝트 인테이크: 기존 | 테스트: uv run pytest | git: 없음"


@pytest.mark.asyncio
async def test_start_workspace_label_skips_unchanged_update(tmp_path: Path) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    next_target = tmp_path / "next"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        label = screen.query_one("#workspace-candidate", Static)
        updates: list[str] = []
        original_update = label.update

        def counted_update(content) -> None:
            updates.append(str(content))
            original_update(content)

        label.update = counted_update

        screen.set_workspace_candidate(target)
        await pilot.pause()
        assert updates == []

        screen.set_workspace_candidate(next_target)
        await pilot.pause()
        assert updates == [f"Planning target: {next_target}"]


@pytest.mark.asyncio
async def test_start_workspace_candidate_skips_unchanged_widget_query(
    tmp_path: Path,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    next_target = tmp_path / "next"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        queries: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        screen.query_one = counted_query_one

        screen.set_workspace_candidate(Path(str(target)))
        await pilot.pause()
        assert queries == []

        screen.set_workspace_candidate(next_target)
        await pilot.pause()
        assert queries == []


@pytest.mark.asyncio
async def test_start_workspace_label_skips_query_when_rendered_label_matches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    control_repo.mkdir()
    target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        queries: list[str] = []
        original_query_one = screen.query_one

        def counted_query_one(selector, *args, **kwargs):
            queries.append(str(selector))
            return original_query_one(selector, *args, **kwargs)

        monkeypatch.setattr(screen, "query_one", counted_query_one)

        screen.set_workspace_candidate(_DisplayPath(str(target)))
        await pilot.pause()

        assert queries == []


@pytest.mark.asyncio
async def test_start_screen_reuses_composed_action_widgets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    control_repo = tmp_path / "control"
    target = tmp_path / "target"
    next_target = tmp_path / "next"
    control_repo.mkdir()
    target.mkdir()
    next_target.mkdir()
    screen = StartScreen(
        TrinityConfig.default_config(project_dir=control_repo),
        workspace_candidate=target,
    )
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        queries: list[object] = []
        original_query_one = screen.query_one
        fixed_selectors = {
            "#start-composer",
            "#workspace-candidate",
            AgentRecipientModelSelector,
        }

        def counted_query_one(selector, *args, **kwargs):
            if selector in fixed_selectors:
                queries.append(selector)
            return original_query_one(selector, *args, **kwargs)

        monkeypatch.setattr(screen, "query_one", counted_query_one)

        screen.set_workspace_candidate(next_target)
        screen.action_submit()
        screen._submit("/status")
        screen._submit("Plan the API")
        await pilot.pause()

        assert queries == []
