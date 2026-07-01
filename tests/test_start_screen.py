from __future__ import annotations

from datetime import date
import subprocess
import sys
from pathlib import Path

import pytest
from textual.app import App
from textual.css.query import NoMatches
from textual.widgets import Button, Static

from trinity.config import TrinityConfig
from trinity.project_intake import build_project_intake, write_project_intake
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.workspace_labels import (
    format_project_intake_label,
    project_existing_diagnostic_label,
    project_generation_preview_label,
    project_diagnostic_readiness_label,
    project_intake_state_label,
    project_plan_preview_label,
    provider_cli_setup_label,
    provider_execution_review_policy_label,
    project_read_first_checklist_label,
    project_validation_plan_label,
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
    _ = tmp_path
    control_repo = Path("Trinity")
    target = Path("customer-app")

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


def test_target_workspace_state_label_compacts_long_paths(tmp_path: Path) -> None:
    control_repo = tmp_path / "Trinity"
    long_target = (
        tmp_path
        / "very-long-workspace-root-name"
        / "deeply-nested-projects"
        / "customer-onboarding-automation"
    )

    label = target_workspace_state_label(long_target, control_repo=control_repo)
    target_text = label.removeprefix("Planning target: ")

    assert label.startswith("Planning target: ")
    assert "..." in target_text
    assert len(target_text) <= 96
    assert target_text.startswith(str(long_target)[:10])
    assert target_text.endswith("customer-onboarding-automation")


def test_start_and_nexus_labels_use_visible_copy(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    ko_config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")

    start = StartScreen(config)
    nexus = NexusScreen(config)
    ko_start = StartScreen(ko_config, lang="ko")
    ko_nexus = NexusScreen(ko_config)

    assert start.label_text("placeholder") == "What should Trinity work on?"
    assert nexus.label_text("composer_placeholder") == (
        "Reply, refine direction, or type / for commands"
    )
    assert ko_start.label_text("placeholder") == "Trinity가 무엇을 진행하면 될까요?"
    assert ko_nexus.label_text("composer_placeholder") == "답변, 방향 조정 또는 /로 명령 입력"


def test_provider_execution_review_policy_label_handles_provider_counts(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    assert provider_execution_review_policy_label(config.agents) == (
        "Provider policy: 1 active (claude) | "
        "execution: single executor | review: self-check/manual"
    )

    config.agents["codex"].enabled = True
    assert provider_execution_review_policy_label(config.agents) == ""
    assert provider_execution_review_policy_label(
        config.agents,
        selected_agents=("claude",),
    ) == (
        "Provider policy: 1 active (claude) | "
        "execution: single executor | review: self-check/manual"
    )
    assert provider_execution_review_policy_label(
        config.agents,
        selected_agents=(),
    ) == (
        "Provider policy: 0 active | execution: unavailable | "
        "review: unavailable"
    )

    config.agents["antigravity"].enabled = True
    assert provider_execution_review_policy_label(config.agents) == ""
    assert provider_execution_review_policy_label(config.agents, lang="ko") == ""


def test_provider_cli_setup_label_reports_selected_cli_commands(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].cli_command = sys.executable

    assert provider_cli_setup_label(config.agents) == ""

    config.agents["codex"].enabled = True
    config.agents["codex"].cli_command = "trinity-missing-cli-for-test"

    assert provider_cli_setup_label(config.agents) == (
        "Provider CLI setup: missing: codex(trinity-missing-cli-for-test) | "
        "next: fix CLI command/PATH"
    )
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=("codex",),
    ) == (
        "Provider CLI setup: missing: codex(trinity-missing-cli-for-test) | "
        "next: fix CLI command/PATH"
    )
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=(),
    ) == "Provider CLI setup: selected 0 | next: select at least one provider"
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=(),
        lang="ko",
    ) == "프로바이더 CLI 설정: 선택 0개 | 다음: 프로바이더를 하나 이상 선택"

    config.agents["antigravity"].enabled = True
    config.agents["antigravity"].cli_command = "agy-missing-for-test"
    assert provider_cli_setup_label(config.agents, lang="ko") == (
        "프로바이더 CLI 설정: 없음: codex(trinity-missing-cli-for-test), "
        "antigravity(agy-missing-for-test) | "
        "다음: CLI 명령/PATH 수정"
    )

    config.agents["claude"].cli_command = "claude-missing-for-test"
    assert provider_cli_setup_label(config.agents) == (
        "Provider CLI setup: missing: claude(claude-missing-for-test), "
        "codex(trinity-missing-cli-for-test) +1 | "
        "next: fix CLI command/PATH"
    )

    quoted_cli = tmp_path / "custom cli"
    quoted_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    config.agents["claude"].cli_command = f'"{quoted_cli}" --profile work'
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=("claude",),
    ) == ""
    config.agents["codex"].cli_command = f'"{tmp_path / "missing cli"}" --profile work'
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=("codex",),
    ) == (
        "Provider CLI setup: missing: codex(missing cli) | next: fix CLI command/PATH"
    )


def test_project_diagnostic_readiness_label_summarizes_first_run_state(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    state = tmp_path / ".trinity"
    target = tmp_path / "customer-app"
    target.mkdir()

    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        target_workspace=target,
    ) == (
        "Readiness: target ok | context missing | "
        "providers 1 selected | validation missing"
    )
    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        selected_agents=(),
        target_workspace=target,
    ) == (
        "Readiness: target ok | context missing | "
        "providers 0 selected | validation missing"
    )

    write_project_intake(
        state,
        build_project_intake(mode="new", target_workspace=target),
    )

    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        target_workspace=target,
    ) == (
        "Readiness: target ok | context check | "
        "providers 1 selected | validation missing"
    )

    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build onboarding.",
            project_type="SaaS app",
            target_users="operators",
            success_criteria="Operators complete onboarding.",
            first_milestone="First workflow.",
        ),
    )

    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        target_workspace=target,
    ) == (
        "Readiness: target ok | context check | "
        "providers 1 selected | validation missing"
    )

    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build onboarding.",
            project_type="SaaS app",
            target_users="operators",
            success_criteria="Operators complete onboarding.",
            first_milestone="First workflow.",
            validation_commands=("uv run pytest",),
        ),
    )

    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        target_workspace=target,
    ) == (
        "Readiness: target ok | context ok | "
        "providers 1 selected | validation planned"
    )
    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        lang="ko",
        target_workspace=target,
    ) == (
        "준비 상태: 대상 정상 | 컨텍스트 정상 | "
        "프로바이더 1개 선택 | 검증 계획됨"
    )


def test_project_diagnostic_readiness_label_checks_existing_project_intake(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    state = tmp_path / ".trinity"
    target = tmp_path / "existing-app"
    target.mkdir()
    (target / "README.md").write_text("# Existing\n", encoding="utf-8")
    (target / "src").mkdir()
    (target / "package.json").write_text(
        '{"scripts":{"test":"vitest run","build":"vite build"}}',
        encoding="utf-8",
    )
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            read_first_confirmed=True,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        target_workspace=target,
        today=date(2026, 6, 28),
    ) == (
        "Readiness: target ok | context ok | "
        "providers 1 selected | validation planned"
    )
    assert project_diagnostic_readiness_label(
        state,
        config.agents,
        target_workspace=tmp_path / "other-app",
        today=date(2026, 6, 28),
    ) == (
        "Readiness: target ok | context check | "
        "providers 1 selected | validation missing"
    )


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
        project_intake_state_label(state, today=date(2026, 6, 28))
        == (
            "Project context: recorded | target: customer-app | "
            "updated: 2026-06-28 | tests: uv run pytest | git: none"
        )
    )
    assert (
        project_intake_state_label(state, lang="ko", today=date(2026, 6, 28))
        == (
            "프로젝트 컨텍스트: 기록됨 | 대상: customer-app | "
            "갱신: 2026-06-28 | 테스트: uv run pytest | git: 없음"
        )
    )


def test_project_plan_preview_label_summarizes_new_project_brief(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build customer onboarding.",
            project_type="SaaS dashboard",
            starter_profile="Textual TUI",
            target_users="support operators",
            success_criteria="Operators can complete onboarding safely.",
            stack_preferences=("python", "sqlite", "textual"),
            first_milestone="First usable onboarding workflow.",
            constraints=("Keep setup simple", "No paid APIs"),
        ),
    )

    assert project_plan_preview_label(state, target_workspace=target) == (
        "Initial plan preview: starter: Textual TUI | "
        "milestone: First usable onboarding workflow. | "
        "stack: python, sqlite, textual | "
        "success: Operators can complete onboarding safely. | "
        "users: support operators | guardrails: Keep setup simple, No paid APIs"
    )
    assert project_plan_preview_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "초기 계획 미리보기: 스타터: Textual TUI | "
        "마일스톤: First usable onboarding workflow. | "
        "스택: python, sqlite, textual | "
        "성공: Operators can complete onboarding safely. | "
        "사용자: support operators | 가드레일: Keep setup simple, No paid APIs"
    )
    assert project_plan_preview_label(
        state,
        target_workspace=tmp_path / "other-app",
    ) == ""


def test_project_plan_preview_label_skips_existing_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            product_goal="Improve docs.",
            first_milestone="Review README.",
        ),
    )

    assert project_plan_preview_label(state, target_workspace=target) == ""


def test_project_generation_preview_label_summarizes_new_project_shape(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            project_type="SaaS dashboard",
            starter_profile="Textual TUI",
            stack_preferences=("python", "textual"),
            constraints=("Keep setup simple", "No paid APIs"),
        ),
    )

    assert project_generation_preview_label(state, target_workspace=target) == (
        "Generation preview: create: README.md, pyproject.toml, src/ +1 | "
        "validate: uv run pytest | "
        "guardrails: Keep setup simple, No paid APIs"
    )
    assert project_generation_preview_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "생성 미리보기: 생성: README.md, pyproject.toml, src/ +1 | "
        "검증: uv run pytest | "
        "가드레일: Keep setup simple, No paid APIs"
    )
    assert project_generation_preview_label(
        state,
        target_workspace=tmp_path / "other-app",
    ) == ""


def test_project_generation_preview_label_warns_about_existing_paths(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    target.mkdir()
    (target / "README.md").write_text("# Existing\n", encoding="utf-8")
    (target / "src").mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            project_type="SaaS dashboard",
            starter_profile="Textual TUI",
            stack_preferences=("python", "textual"),
        ),
    )

    assert project_generation_preview_label(state, target_workspace=target) == (
        "Generation preview: create: README.md, pyproject.toml, src/ +1 | "
        "validate: uv run pytest | conflicts: README.md, src/"
    )
    assert project_generation_preview_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "생성 미리보기: 생성: README.md, pyproject.toml, src/ +1 | "
        "검증: uv run pytest | 충돌: README.md, src/"
    )


def test_project_generation_preview_label_skips_existing_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            product_goal="Improve docs.",
        ),
    )

    assert project_generation_preview_label(state, target_workspace=target) == ""


def test_project_validation_plan_label_summarizes_new_project_checks(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            starter_profile="Textual TUI",
            stack_preferences=("python", "textual"),
        ),
    )

    assert project_validation_plan_label(state, target_workspace=target) == (
        "Validation plan: fast: uv run pytest | "
        "required: record required check before merge | "
        "full: first scaffold smoke before release"
    )
    assert project_validation_plan_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "검증 계획: 빠른 확인: uv run pytest | "
        "필수 확인: 병합 전 필수 확인 기록 | "
        "전체 확인: 릴리스 전 첫 스캐폴드 smoke"
    )


def test_project_validation_plan_label_summarizes_existing_project_checks(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing-app"
    target.mkdir()
    (target / "package.json").write_text(
        '{"scripts":{"test":"vitest run","build":"vite build"}}',
        encoding="utf-8",
    )
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
        ),
    )

    assert project_validation_plan_label(state, target_workspace=target) == (
        "Validation plan: fast: npm test | "
        "required: npm test | full: npm run build"
    )


def test_project_read_first_checklist_label_summarizes_existing_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing-app"
    target.mkdir()
    (target / "README.md").write_text("# Existing\n", encoding="utf-8")
    (target / "src").mkdir()
    (target / "package.json").write_text(
        '{"scripts":{"test":"vitest run"},"main":"src/index.js"}',
        encoding="utf-8",
    )
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            selected_scope="apps/web",
        ),
    )

    assert project_read_first_checklist_label(state, target_workspace=target) == (
        "Read-first checklist: scope: apps/web | read: README.md, src | "
        "inspect: src/index.js | verify: npm test"
    )
    assert project_read_first_checklist_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "먼저 읽기 체크리스트: 범위: apps/web | 읽기: README.md, src | "
        "점검: src/index.js | 검증: npm test"
    )


def test_project_existing_diagnostic_label_summarizes_existing_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing-app"
    target.mkdir()
    (target / "README.md").write_text("# Existing\n", encoding="utf-8")
    (target / "src").mkdir()
    (target / "package.json").write_text(
        '{"scripts":{"test":"vitest run","dev":"vite","build":"vite build"}}',
        encoding="utf-8",
    )
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            selected_scope="apps/web",
        ),
    )

    assert project_existing_diagnostic_label(state, target_workspace=target) == (
        "Existing diagnosis: read: README.md, src | "
        "tests: npm test | dev: npm run dev | build: npm run build | "
        "scope: apps/web | git: none"
    )
    assert project_existing_diagnostic_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "기존 프로젝트 진단: 읽기: README.md, src | "
        "테스트: npm test | 개발: npm run dev | 빌드: npm run build | "
        "범위: apps/web | git: 없음"
    )


def test_project_existing_diagnostic_label_skips_new_or_mismatched_intake(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    other = tmp_path / "other-app"
    target.mkdir()
    other.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build app.",
        ),
    )

    assert project_existing_diagnostic_label(state, target_workspace=target) == ""
    assert project_existing_diagnostic_label(state, target_workspace=other) == ""


def test_project_read_first_checklist_label_prompts_scope_choice(
    tmp_path: Path,
) -> None:
    target = tmp_path / "monorepo"
    target.mkdir()
    (target / "README.md").write_text("# Monorepo\n", encoding="utf-8")
    (target / "src").mkdir()
    (target / "apps" / "web").mkdir(parents=True)
    (target / "apps" / "web" / "package.json").write_text("{}", encoding="utf-8")
    (target / "packages" / "core").mkdir(parents=True)
    (target / "packages" / "core" / "pyproject.toml").write_text(
        "[project]\nname='core'\n",
        encoding="utf-8",
    )
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
        ),
    )

    assert project_read_first_checklist_label(state, target_workspace=target) == (
        "Read-first checklist: scope: choose apps/web, packages/core | "
        "read: README.md, src, packages | inspect: entrypoints missing | "
        "verify: record validation command"
    )
    assert project_read_first_checklist_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "먼저 읽기 체크리스트: 범위: 선택 apps/web, packages/core | "
        "읽기: README.md, src, packages | 점검: 진입점 없음 | "
        "검증: 검증 명령 기록"
    )


def test_project_read_first_checklist_label_handles_sparse_existing_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
        ),
    )

    assert project_read_first_checklist_label(state, target_workspace=target) == (
        "Read-first checklist: scope: target root | "
        "read: README/docs/source roots missing | "
        "inspect: entrypoints missing | verify: record validation command"
    )


def test_project_read_first_checklist_label_skips_new_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build app.",
        ),
    )

    assert project_read_first_checklist_label(state, target_workspace=target) == ""


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

    assert project_intake_state_label(state, today=date(2026, 6, 28)) == (
        "Project context: recorded | target: customer-app | "
        "updated: 2026-06-28 | tests: (none) | git: none"
    )
    assert project_intake_state_label(state, lang="ko", today=date(2026, 6, 28)) == (
        "프로젝트 컨텍스트: 기록됨 | 대상: customer-app | "
        "갱신: 2026-06-28 | 테스트: (없음) | git: 없음"
    )


def test_project_intake_state_label_includes_scope_candidates(
    tmp_path: Path,
) -> None:
    target = tmp_path / "monorepo"
    target.mkdir()
    (target / "README.md").write_text("# Monorepo\n", encoding="utf-8")
    (target / "apps" / "web").mkdir(parents=True)
    (target / "apps" / "web" / "package.json").write_text("{}", encoding="utf-8")
    (target / "packages" / "core").mkdir(parents=True)
    (target / "packages" / "core" / "pyproject.toml").write_text(
        "[project]\nname='core'\n",
        encoding="utf-8",
    )
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            selected_scope="apps/web",
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert "scope: apps/web" not in project_intake_state_label(
        state,
        today=date(2026, 6, 28),
    )
    assert "scopes: apps/web, packages/core" not in project_intake_state_label(
        state,
        today=date(2026, 6, 28),
    )
    assert "선택 범위: apps/web" not in project_intake_state_label(
        state,
        lang="ko",
        today=date(2026, 6, 28),
    )
    assert "범위: apps/web, packages/core" not in project_intake_state_label(
        state,
        lang="ko",
        today=date(2026, 6, 28),
    )


def test_project_intake_state_label_prompts_scope_choice_when_unselected(
    tmp_path: Path,
) -> None:
    target = tmp_path / "monorepo"
    target.mkdir()
    (target / "README.md").write_text("# Monorepo\n", encoding="utf-8")
    (target / "apps" / "web").mkdir(parents=True)
    (target / "apps" / "web" / "package.json").write_text("{}", encoding="utf-8")
    (target / "packages" / "core").mkdir(parents=True)
    (target / "packages" / "core" / "pyproject.toml").write_text(
        "[project]\nname='core'\n",
        encoding="utf-8",
    )
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    label = project_intake_state_label(state, today=date(2026, 6, 28))
    assert "choose scope: apps/web, packages/core" not in label
    assert "scopes: apps/web, packages/core" not in label

    ko_label = project_intake_state_label(
        state,
        lang="ko",
        today=date(2026, 6, 28),
    )
    assert "범위 선택: apps/web, packages/core" not in ko_label
    assert "범위: apps/web, packages/core" not in ko_label


def test_project_intake_state_label_warns_for_sparse_existing_analysis(
    tmp_path: Path,
) -> None:
    target = tmp_path / "empty-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert project_intake_state_label(state, today=date(2026, 6, 28)) == (
        "Project context: recorded | target: empty-app | "
        "updated: 2026-06-28 | tests: (none) | "
        "analysis: sparse | missing: tests, src, docs | git: none"
    )
    assert project_intake_state_label(state, lang="ko", today=date(2026, 6, 28)) == (
        "프로젝트 컨텍스트: 기록됨 | 대상: empty-app | "
        "갱신: 2026-06-28 | 테스트: (없음) | "
        "분석: 부족 | 누락: 테스트, 소스, 문서 | git: 없음"
    )


def test_project_intake_state_label_warns_for_stale_existing_analysis(
    tmp_path: Path,
) -> None:
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
            created_at="2026-06-01T00:00:00Z",
        ),
    )

    assert project_intake_state_label(state, today=date(2026, 6, 28)) == (
        "Project context: recorded | target: customer-app | "
        "updated: 2026-06-01 | "
        "analysis: stale 27d | "
        f"refresh: trinity project analyze {target} | "
        "tests: uv run pytest | git: none"
    )
    assert project_intake_state_label(
        state,
        lang="ko",
        today=date(2026, 6, 28),
    ) == (
        "프로젝트 컨텍스트: 기록됨 | 대상: customer-app | "
        "갱신: 2026-06-01 | "
        "분석: 오래됨 27일 | "
        f"재분석: trinity project analyze {target} | "
        "테스트: uv run pytest | git: 없음"
    )


def test_project_intake_state_label_warns_for_changed_existing_analysis(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "README.md").write_text("docs\n", encoding="utf-8")
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    (target / "src").mkdir()

    label = project_intake_state_label(
        state,
        target_workspace=target,
        today=date(2026, 6, 28),
    )
    assert "analysis: changed src" in label
    assert f"refresh: trinity project analyze {target}" in label

    ko_label = project_intake_state_label(
        state,
        lang="ko",
        target_workspace=target,
        today=date(2026, 6, 28),
    )
    assert "분석: 변경됨 소스" in ko_label
    assert f"재분석: trinity project analyze {target}" in ko_label


def test_project_intake_state_label_warns_when_target_mismatches(
    tmp_path: Path,
) -> None:
    saved_target = tmp_path / "saved-app"
    selected_target = tmp_path / "selected-app"
    saved_target.mkdir()
    selected_target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=saved_target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert project_intake_state_label(
        state,
        target_workspace=selected_target,
    ).startswith(
        "Project context: recorded | "
        "target: saved-app | "
        f"target mismatch: saved target {saved_target} | "
        "updated: 2026-06-28"
    )
    assert project_intake_state_label(
        state,
        lang="ko",
        target_workspace=selected_target,
    ).startswith(
        "프로젝트 컨텍스트: 기록됨 | "
        "대상: saved-app | "
        f"대상 불일치: 저장된 대상 {saved_target} | "
        "갱신: 2026-06-28"
    )
    assert "target mismatch" not in project_intake_state_label(
        state,
        target_workspace=saved_target,
    )


def test_project_intake_state_label_warns_when_saved_target_is_missing(
    tmp_path: Path,
) -> None:
    missing_target = tmp_path / "missing-app"
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=missing_target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert project_intake_state_label(state, today=date(2026, 6, 28)) == (
        "Project context: recorded | "
        "target: missing-app | "
        f"target missing: {missing_target} | "
        "updated: 2026-06-28 | tests: (none) | "
        "analysis: sparse | missing: tests, src, docs | git: none"
    )
    assert project_intake_state_label(
        state,
        lang="ko",
        today=date(2026, 6, 28),
    ) == (
        "프로젝트 컨텍스트: 기록됨 | "
        "대상: missing-app | "
        f"대상 없음: {missing_target} | "
        "갱신: 2026-06-28 | 테스트: (없음) | "
        "분석: 부족 | 누락: 테스트, 소스, 문서 | git: 없음"
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
    target.mkdir()
    state = tmp_path / ".trinity"
    partial_intake = build_project_intake(
        mode="new",
        target_workspace=target,
        product_goal="Build a dashboard.",
        created_at="2026-06-28T00:00:00Z",
    )
    write_project_intake(
        state,
        partial_intake,
    )

    assert project_intake_state_label(state) == (
        "Project context: recorded | target: new-app | "
        "updated: 2026-06-28 | tests: (none)"
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 컨텍스트: 기록됨 | 대상: new-app | "
        "갱신: 2026-06-28 | 테스트: (없음)"
    )
    assert "prompt: missing type, users +2" in format_project_intake_label(
        partial_intake
    )

    complete_intake = build_project_intake(
        mode="new",
        target_workspace=target,
        product_goal="Build a dashboard.",
        project_type="SaaS dashboard",
        target_users="support operators",
        success_criteria="Operators can complete onboarding.",
        stack_preferences=("React", "FastAPI", "PostgreSQL"),
        first_milestone="First safe patch.",
        constraints=("No cloud lock-in", "Keep tests green", "CLI-first"),
        created_at="2026-06-28T00:00:00Z",
    )
    write_project_intake(
        state,
        complete_intake,
    )

    assert project_intake_state_label(state) == (
        "Project context: recorded | target: new-app | "
        "updated: 2026-06-28 | tests: (none)"
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 컨텍스트: 기록됨 | 대상: new-app | "
        "갱신: 2026-06-28 | 테스트: (없음)"
    )
    assert "prompt: complete" in format_project_intake_label(complete_intake)


def test_project_intake_state_label_guides_missing_intake(tmp_path: Path) -> None:
    state = tmp_path / ".trinity"
    target = tmp_path / "customer-app"

    assert project_intake_state_label(state) == (
        "Project context: not recorded | next: type the analysis or work request"
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 컨텍스트: 기록 없음 | 다음: 분석이나 작업 요청 입력"
    )
    assert project_intake_state_label(state, target_workspace=target) == (
        "Project context: not recorded | next: type the analysis or work request"
    )
    assert project_intake_state_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "프로젝트 컨텍스트: 기록 없음 | 다음: 분석이나 작업 요청 입력"
    )


def test_start_and_nexus_missing_project_intake_stays_prompt_driven(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    label = project_intake_state_label(
        config.effective_state_dir,
        target_workspace=target,
    )

    assert label == (
        "Project context: not recorded | next: type the analysis or work request"
    )
    assert str(target) not in label
    assert "trinity project new" not in label


def test_start_and_nexus_project_intake_warn_when_target_mismatches(
    tmp_path: Path,
) -> None:
    saved_target = tmp_path / "saved-app"
    selected_target = tmp_path / "selected-app"
    saved_target.mkdir()
    selected_target.mkdir()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=saved_target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    assert "target mismatch" in project_intake_state_label(
        config.effective_state_dir,
        target_workspace=selected_target,
    )


def test_nexus_workspace_label_uses_target_state_helper(tmp_path: Path) -> None:
    control_repo = tmp_path / "Trinity"
    target = tmp_path / "customer-app"
    control_repo.mkdir()
    target.mkdir()
    screen = NexusScreen(TrinityConfig.default_config(project_dir=control_repo))

    assert screen.workspace_label() == "No target workspace selected"

    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(target))
    assert screen.workspace_label() == target_workspace_state_label(
        target,
        control_repo=control_repo,
    )

    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(control_repo))
    assert screen.workspace_label() == target_workspace_state_label(
        control_repo,
        control_repo=control_repo,
    )


@pytest.mark.asyncio
async def test_start_screen_does_not_render_project_diagnostics(
    tmp_path: Path,
) -> None:
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

        for selector in (
            "#project-startup-readiness",
            "#project-intake-summary",
            "#project-existing-diagnostic",
            "#project-start-choice-guide",
            "#project-plan-preview",
            "#project-generation-preview",
            "#project-validation-plan",
            "#project-read-first-checklist",
        ):
            with pytest.raises(NoMatches):
                screen.query_one(selector, Static)


@pytest.mark.asyncio
async def test_start_screen_target_change_does_not_render_project_context(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    other = tmp_path / "other-app"
    target.mkdir()
    other.mkdir()
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
    screen = StartScreen(config, workspace_candidate=other)
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        with pytest.raises(NoMatches):
            screen.query_one("#project-intake-summary", Static)

        screen.set_workspace_candidate(target)
        await pilot.pause()

        assert screen.workspace_candidate == target
        with pytest.raises(NoMatches):
            screen.query_one("#project-intake-summary", Static)


@pytest.mark.asyncio
async def test_start_screen_does_not_render_inline_provider_notices(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].cli_command = sys.executable
    config.agents["codex"].enabled = True
    config.agents["codex"].cli_command = "trinity-missing-cli-for-test"
    screen = StartScreen(config)
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        with pytest.raises(NoMatches):
            screen.query_one("#start-provider-policy", Static)
        with pytest.raises(NoMatches):
            screen.query_one("#start-provider-cli-setup", Static)

        selector = screen.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(("claude",))
        screen.on_agent_recipient_model_selector_selection_changed(
            AgentRecipientModelSelector.SelectionChanged(selector.selected_agents())
        )
        await pilot.pause()

        with pytest.raises(NoMatches):
            screen.query_one("#start-provider-policy", Static)
        with pytest.raises(NoMatches):
            screen.query_one("#start-provider-cli-setup", Static)
        with pytest.raises(NoMatches):
            screen.query_one("#project-startup-readiness", Static)


@pytest.mark.asyncio
async def test_nexus_screen_does_not_render_project_diagnostics(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "README.md").write_text("# Customer App\n", encoding="utf-8")
    (target / "src").mkdir()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            selected_scope="services/api",
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    screen = NexusScreen(config)
    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(target))
    app = StartScreenHarness(screen)  # type: ignore[arg-type]

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()

        for selector in (
            "#nexus-project-startup-readiness",
            "#nexus-project-intake-summary",
            "#nexus-project-read-first-checklist",
            "#nexus-project-existing-diagnostic",
            "#nexus-project-plan-preview",
            "#nexus-project-generation-preview",
            "#nexus-project-validation-plan",
        ):
            with pytest.raises(NoMatches):
                screen.query_one(selector, Static)


@pytest.mark.asyncio
async def test_nexus_screen_does_not_render_inline_provider_notices(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].cli_command = sys.executable
    config.agents["codex"].enabled = True
    config.agents["codex"].cli_command = "trinity-missing-cli-for-test"
    config.agents["antigravity"].enabled = True
    config.agents["antigravity"].cli_command = sys.executable
    screen = NexusScreen(config)
    screen.set_agent_selection(("claude", "codex"), {})
    app = StartScreenHarness(screen)  # type: ignore[arg-type]

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()

        with pytest.raises(NoMatches):
            screen.query_one("#nexus-provider-policy", Static)
        with pytest.raises(NoMatches):
            screen.query_one("#nexus-provider-cli-setup", Static)

        screen.set_agent_selection(("claude", "antigravity"), {})
        await pilot.pause()

        with pytest.raises(NoMatches):
            screen.query_one("#nexus-provider-policy", Static)
        with pytest.raises(NoMatches):
            screen.query_one("#nexus-provider-cli-setup", Static)

        selector = screen.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(("claude",))
        screen.on_agent_recipient_model_selector_selection_changed(
            AgentRecipientModelSelector.SelectionChanged(selector.selected_agents())
        )
        await pilot.pause()

        with pytest.raises(NoMatches):
            screen.query_one("#nexus-provider-policy", Static)
        with pytest.raises(NoMatches):
            screen.query_one("#nexus-provider-cli-setup", Static)
        with pytest.raises(NoMatches):
            screen.query_one("#nexus-project-startup-readiness", Static)


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
        assert updates == [
            target_workspace_state_label(next_target, control_repo=control_repo)
        ]


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
        assert "#project-intake-summary" not in queries


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
