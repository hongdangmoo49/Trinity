from __future__ import annotations

from datetime import date
import subprocess
import sys
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Button, Static

from trinity.config import TrinityConfig
from trinity.project_intake import build_project_intake, write_project_intake
from trinity.textual_app.screens.nexus import NexusScreen
from trinity.textual_app.screens.start import StartScreen
from trinity.textual_app.snapshot import WorkflowNexusSnapshot
from trinity.textual_app.workspace_labels import (
    project_analyze_action_label_key,
    project_analyze_action_presentation,
    project_analyze_action_variant,
    project_brief_action_label_key,
    project_brief_action_variant,
    project_create_action_variant,
    project_generation_preview_label,
    project_intake_state_label,
    project_mode_rail_label,
    project_plan_preview_label,
    project_startup_readiness_label,
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


def test_start_and_nexus_project_actions_use_mode_specific_labels(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    ko_config = TrinityConfig.default_config(project_dir=tmp_path, lang="ko")

    start = StartScreen(config)
    nexus = NexusScreen(config)
    ko_start = StartScreen(ko_config, lang="ko")
    ko_nexus = NexusScreen(ko_config)

    assert start._label("analyze_workspace") == "Analyze Existing"
    assert start._label("create_project") == "Create New"
    assert nexus._label("analyze_workspace") == "Analyze Existing"
    assert nexus._label("create_project") == "Create New"
    assert start._label("refresh_analysis") == "Refresh Analysis"
    assert nexus._label("refresh_analysis") == "Refresh Analysis"
    assert start._label("analyze_selected_workspace") == "Analyze Selected"
    assert nexus._label("analyze_selected_workspace") == "Analyze Selected"
    assert ko_start._label("analyze_workspace") == "기존 프로젝트 분석"
    assert ko_start._label("create_project") == "새 프로젝트 생성"
    assert ko_nexus._label("analyze_workspace") == "기존 프로젝트 분석"
    assert ko_nexus._label("create_project") == "새 프로젝트 생성"
    assert ko_start._label("refresh_analysis") == "분석 갱신"
    assert ko_nexus._label("refresh_analysis") == "분석 갱신"
    assert ko_start._label("analyze_selected_workspace") == "선택 대상 분석"
    assert ko_nexus._label("analyze_selected_workspace") == "선택 대상 분석"


def test_provider_execution_review_policy_label_handles_provider_counts(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)

    assert provider_execution_review_policy_label(config.agents) == (
        "Provider policy: 1 active (claude) | "
        "execution: single executor | review: self-check/manual"
    )

    config.agents["codex"].enabled = True
    assert provider_execution_review_policy_label(config.agents) == (
        "Provider policy: 2 active (claude, codex) | "
        "execution: parallel capable | review: one peer reviewer"
    )
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
    assert provider_execution_review_policy_label(config.agents) == (
        "Provider policy: 3 active (claude, codex, antigravity) | "
        "execution: parallel capable | review: peer reviewer pool"
    )
    assert provider_execution_review_policy_label(config.agents, lang="ko") == (
        "프로바이더 정책: 활성 3개(claude, codex, antigravity) | "
        "실행: 병렬 가능 | 리뷰: 동료 리뷰 풀"
    )


def test_provider_cli_setup_label_reports_selected_cli_commands(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    config.agents["claude"].cli_command = sys.executable

    assert provider_cli_setup_label(config.agents) == (
        "Provider CLI setup: selected 1 | found: claude"
    )

    config.agents["codex"].enabled = True
    config.agents["codex"].cli_command = "trinity-missing-cli-for-test"

    assert provider_cli_setup_label(config.agents) == (
        "Provider CLI setup: selected 2 | found: claude | "
        "missing: codex(trinity-missing-cli-for-test) | "
        "next: fix CLI command/PATH"
    )
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=("codex",),
    ) == (
        "Provider CLI setup: selected 1 | "
        "missing: codex(trinity-missing-cli-for-test) | "
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
        "프로바이더 CLI 설정: 선택 3개 | 발견: claude | "
        "없음: codex(trinity-missing-cli-for-test), "
        "antigravity(agy-missing-for-test) | "
        "다음: CLI 명령/PATH 수정"
    )

    config.agents["claude"].cli_command = "claude-missing-for-test"
    assert provider_cli_setup_label(config.agents) == (
        "Provider CLI setup: selected 3 | "
        "missing: claude(claude-missing-for-test), "
        "codex(trinity-missing-cli-for-test) +1 | "
        "next: fix CLI command/PATH"
    )

    quoted_cli = tmp_path / "custom cli"
    quoted_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    config.agents["claude"].cli_command = f'"{quoted_cli}" --profile work'
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=("claude",),
    ) == "Provider CLI setup: selected 1 | found: claude"
    config.agents["codex"].cli_command = f'"{tmp_path / "missing cli"}" --profile work'
    assert provider_cli_setup_label(
        config.agents,
        selected_agents=("codex",),
    ) == (
        "Provider CLI setup: selected 1 | missing: codex(missing cli) | "
        "next: fix CLI command/PATH"
    )


def test_project_startup_readiness_label_summarizes_first_run_state(
    tmp_path: Path,
) -> None:
    config = TrinityConfig.default_config(project_dir=tmp_path)
    state = tmp_path / ".trinity"
    target = tmp_path / "customer-app"
    target.mkdir()

    assert project_startup_readiness_label(
        state,
        config.agents,
        target_workspace=target,
    ) == (
        "Startup readiness: target ok | intake missing | "
        "providers 1 selected | validation missing"
    )
    assert project_startup_readiness_label(
        state,
        config.agents,
        selected_agents=(),
        target_workspace=target,
    ) == (
        "Startup readiness: target ok | intake missing | "
        "providers 0 selected | validation missing"
    )

    write_project_intake(
        state,
        build_project_intake(mode="new", target_workspace=target),
    )

    assert project_startup_readiness_label(
        state,
        config.agents,
        target_workspace=target,
    ) == (
        "Startup readiness: target ok | intake check | "
        "providers 1 selected | validation planned"
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

    assert project_startup_readiness_label(
        state,
        config.agents,
        target_workspace=target,
    ) == (
        "Startup readiness: target ok | intake ok | "
        "providers 1 selected | validation planned"
    )
    assert project_startup_readiness_label(
        state,
        config.agents,
        lang="ko",
        target_workspace=target,
    ) == (
        "시작 준비: 대상 정상 | 인테이크 정상 | "
        "프로바이더 1개 선택 | 검증 계획됨"
    )


def test_project_startup_readiness_label_checks_existing_project_intake(
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
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert project_startup_readiness_label(
        state,
        config.agents,
        target_workspace=target,
        today=date(2026, 6, 28),
    ) == (
        "Startup readiness: target ok | intake ok | "
        "providers 1 selected | validation planned"
    )
    assert project_startup_readiness_label(
        state,
        config.agents,
        target_workspace=tmp_path / "other-app",
        today=date(2026, 6, 28),
    ) == (
        "Startup readiness: target ok | intake check | "
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
            "Project intake: existing | target: customer-app | "
            "updated: 2026-06-28 | tests: uv run pytest | git: none"
        )
    )
    assert (
        project_intake_state_label(state, lang="ko", today=date(2026, 6, 28))
        == (
            "프로젝트 인테이크: 기존 | 대상: customer-app | "
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


def test_project_mode_rail_label_guides_missing_intake(tmp_path: Path) -> None:
    state = tmp_path / ".trinity"
    target = tmp_path / "target-app"
    target.mkdir()

    assert project_mode_rail_label(state) == (
        "Start flow: target: needed -> intake: waiting -> plan: locked -> "
        "execute: locked | mode: none | next: select workspace"
    )
    assert project_mode_rail_label(state, target_workspace=target) == (
        "Start flow: target: ready -> intake: needed -> plan: locked -> "
        "execute: locked | mode: none | next: analyze existing or create new"
    )


def test_project_mode_rail_label_guides_new_project_brief(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    target.mkdir()
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(mode="new", target_workspace=target),
    )

    assert project_mode_rail_label(state, target_workspace=target) == (
        "Start flow: target: ready -> intake: brief needed -> "
        "plan: ready after brief -> execute: locked | mode: new | "
        "next: edit brief"
    )
    assert project_mode_rail_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "시작 흐름: 대상: 준비됨 -> 인테이크: 브리프 필요 -> "
        "계획: 브리프 후 준비 -> 실행: 잠김 | 모드: 신규 | 다음: 브리프 편집"
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

    assert project_mode_rail_label(state, target_workspace=target) == (
        "Start flow: target: ready -> intake: ready -> plan: ready -> "
        "execute: ready | mode: new | next: plan or execute"
    )


def test_project_mode_rail_label_guides_existing_project_refresh(
    tmp_path: Path,
) -> None:
    target = tmp_path / "existing-app"
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

    assert project_mode_rail_label(
        state,
        target_workspace=target,
        today=date(2026, 6, 28),
    ) == (
        "Start flow: target: ready -> intake: refresh needed -> "
        "plan: caution -> execute: confirm | mode: existing | "
        "next: refresh analysis"
    )


def test_project_mode_rail_label_prioritizes_target_mismatch(
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
            product_goal="Build onboarding.",
            project_type="SaaS app",
            target_users="operators",
            success_criteria="Operators complete onboarding.",
            first_milestone="First workflow.",
        ),
    )

    assert project_mode_rail_label(state, target_workspace=other) == (
        "Start flow: target: mismatch -> intake: check target -> "
        "plan: locked -> execute: locked | mode: new | "
        "next: switch target or re-analyze"
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

    assert project_intake_state_label(state, today=date(2026, 6, 28)) == (
        "Project intake: existing | target: customer-app | "
        "updated: 2026-06-28 | tests: (none) | "
        "read first: README.md, docs, src +1 | git: none | "
        "goal: Launch customer onboarding. | type: SaaS dashboard | "
        "users: support operators | dev: npm run dev | build: npm run build "
        "| src: src, tests "
        "| entry: dist/index.js, customer -> bin/customer.js | "
        "docs: README.md, docs"
    )
    assert project_intake_state_label(state, lang="ko", today=date(2026, 6, 28)) == (
        "프로젝트 인테이크: 기존 | 대상: customer-app | "
        "갱신: 2026-06-28 | 테스트: (없음) | "
        "먼저 읽기: README.md, docs, src +1 | git: 없음 | "
        "목표: Launch customer onboarding. | 유형: SaaS dashboard | "
        "사용자: support operators | 개발: npm run dev | 빌드: npm run build "
        "| 소스: src, tests "
        "| 진입점: dist/index.js, customer -> bin/customer.js | "
        "문서: README.md, docs"
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

    assert "scope: apps/web" in project_intake_state_label(
        state,
        today=date(2026, 6, 28),
    )
    assert "scopes: apps/web, packages/core" in project_intake_state_label(
        state,
        today=date(2026, 6, 28),
    )
    assert "선택 범위: apps/web" in project_intake_state_label(
        state,
        lang="ko",
        today=date(2026, 6, 28),
    )
    assert "범위: apps/web, packages/core" in project_intake_state_label(
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
    assert "choose scope: apps/web, packages/core" in label
    assert "scopes: apps/web, packages/core" not in label

    ko_label = project_intake_state_label(
        state,
        lang="ko",
        today=date(2026, 6, 28),
    )
    assert "범위 선택: apps/web, packages/core" in ko_label
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
        "Project intake: existing | target: empty-app | "
        "updated: 2026-06-28 | tests: (none) | "
        "analysis: sparse | missing: tests, src, docs | git: none"
    )
    assert project_intake_state_label(state, lang="ko", today=date(2026, 6, 28)) == (
        "프로젝트 인테이크: 기존 | 대상: empty-app | "
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
        "Project intake: existing | target: customer-app | "
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
        "프로젝트 인테이크: 기존 | 대상: customer-app | "
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


def test_project_analyze_action_label_key_marks_refreshable_intake(
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

    assert (
        project_analyze_action_label_key(
            state,
            target_workspace=target,
            today=date(2026, 6, 28),
        )
        == "analyze_workspace"
    )
    presentation = project_analyze_action_presentation(
        state,
        target_workspace=target,
        today=date(2026, 6, 28),
    )
    assert presentation.label_key == "analyze_workspace"
    assert presentation.variant == "default"

    (target / "src").mkdir()

    presentation = project_analyze_action_presentation(
        state,
        target_workspace=target,
        today=date(2026, 6, 28),
    )
    assert presentation.label_key == "refresh_analysis"
    assert presentation.variant == "warning"
    assert (
        project_analyze_action_label_key(
            state,
            target_workspace=target,
            today=date(2026, 6, 28),
        )
        == "refresh_analysis"
    )
    assert (
        project_analyze_action_label_key(
            state,
            target_workspace=tmp_path / "other-app",
            today=date(2026, 6, 28),
        )
        == "analyze_selected_workspace"
    )


def test_project_analyze_action_label_key_marks_sparse_and_stale_as_refresh(
    tmp_path: Path,
) -> None:
    sparse_target = tmp_path / "sparse-app"
    sparse_target.mkdir()
    sparse_state = tmp_path / ".trinity-sparse"
    write_project_intake(
        sparse_state,
        build_project_intake(
            mode="existing",
            target_workspace=sparse_target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert (
        project_analyze_action_label_key(
            sparse_state,
            target_workspace=sparse_target,
            today=date(2026, 6, 28),
        )
        == "refresh_analysis"
    )
    sparse_presentation = project_analyze_action_presentation(
        sparse_state,
        target_workspace=sparse_target,
        today=date(2026, 6, 28),
    )
    assert sparse_presentation.label_key == "refresh_analysis"
    assert sparse_presentation.variant == "warning"

    stale_target = tmp_path / "stale-app"
    stale_target.mkdir()
    (stale_target / "pyproject.toml").write_text(
        "[project]\nname='stale-app'\n",
        encoding="utf-8",
    )
    (stale_target / "uv.lock").write_text("", encoding="utf-8")
    stale_state = tmp_path / ".trinity-stale"
    write_project_intake(
        stale_state,
        build_project_intake(
            mode="existing",
            target_workspace=stale_target,
            created_at="2026-06-01T00:00:00Z",
        ),
    )

    assert (
        project_analyze_action_label_key(
            stale_state,
            target_workspace=stale_target,
            today=date(2026, 6, 28),
        )
        == "refresh_analysis"
    )
    stale_presentation = project_analyze_action_presentation(
        stale_state,
        target_workspace=stale_target,
        today=date(2026, 6, 28),
    )
    assert stale_presentation.label_key == "refresh_analysis"
    assert stale_presentation.variant == "warning"


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
        "Project intake: existing | "
        "target: saved-app | "
        f"target mismatch: intake {saved_target} | "
        "updated: 2026-06-28"
    )
    assert project_intake_state_label(
        state,
        lang="ko",
        target_workspace=selected_target,
    ).startswith(
        "프로젝트 인테이크: 기존 | "
        "대상: saved-app | "
        f"대상 불일치: 인테이크 {saved_target} | "
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
        "Project intake: existing | "
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
        "프로젝트 인테이크: 기존 | "
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
        "Project intake: new | target: new-app | "
        "updated: 2026-06-28 | tests: (none) | "
        "brief: missing type, users +2 | goal: Build a dashboard."
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 인테이크: 신규 | 대상: new-app | "
        "갱신: 2026-06-28 | 테스트: (없음) | "
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
            stack_preferences=("React", "FastAPI", "PostgreSQL"),
            first_milestone="First safe patch.",
            constraints=("No cloud lock-in", "Keep tests green", "CLI-first"),
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert project_intake_state_label(state) == (
        "Project intake: new | target: new-app | "
        "updated: 2026-06-28 | tests: (none) | "
        "brief: complete | "
        "goal: Build a dashboard. | type: SaaS dashboard | "
        "users: support operators | "
        "success: Operators can complete onboarding. | "
        "milestone: First safe patch. | stack: React, FastAPI +1 | "
        "constraints: No cloud lock-in, Keep tests green +1"
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 인테이크: 신규 | 대상: new-app | "
        "갱신: 2026-06-28 | 테스트: (없음) | "
        "브리프: 완료 | "
        "목표: Build a dashboard. | 유형: SaaS dashboard | "
        "사용자: support operators | "
        "성공: Operators can complete onboarding. | "
        "마일스톤: First safe patch. | 스택: React, FastAPI +1 | "
        "제약: No cloud lock-in, Keep tests green +1"
    )


def test_project_brief_action_variant_warns_for_incomplete_new_brief(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    other_target = tmp_path / "other-app"
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

    assert (
        project_brief_action_variant(state, target_workspace=target)
        == "warning"
    )
    assert (
        project_brief_action_label_key(state, target_workspace=target)
        == "complete_brief"
    )
    assert (
        project_brief_action_variant(state, target_workspace=other_target)
        == "default"
    )
    assert (
        project_brief_action_label_key(state, target_workspace=other_target)
        == "edit_brief"
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

    assert (
        project_brief_action_variant(state, target_workspace=target)
        == "default"
    )
    assert (
        project_brief_action_label_key(state, target_workspace=target)
        == "edit_brief"
    )


def test_project_action_variants_prioritize_intake_recovery(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    state = tmp_path / ".trinity"

    assert (
        project_analyze_action_variant(state, target_workspace=target)
        == "warning"
    )
    assert (
        project_analyze_action_variant(state, target_workspace=None)
        == "default"
    )
    assert (
        project_create_action_variant(state, target_workspace=target)
        == "default"
    )

    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-01T00:00:00Z",
        ),
    )
    assert (
        project_analyze_action_variant(
            state,
            target_workspace=target,
            today=date(2026, 6, 28),
        )
        == "warning"
    )

    (target / "pyproject.toml").write_text(
        "[project]\nname='customer-app'\n",
        encoding="utf-8",
    )
    (target / "uv.lock").write_text("", encoding="utf-8")
    write_project_intake(
        state,
        build_project_intake(
            mode="existing",
            target_workspace=target,
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    assert (
        project_analyze_action_variant(
            state,
            target_workspace=target,
            today=date(2026, 6, 28),
        )
        == "default"
    )

    (target / "src").mkdir()
    assert (
        project_analyze_action_variant(
            state,
            target_workspace=target,
            today=date(2026, 6, 28),
        )
        == "warning"
    )

    other_target = tmp_path / "other-app"
    other_target.mkdir()
    assert (
        project_analyze_action_variant(state, target_workspace=other_target)
        == "warning"
    )


def test_project_create_action_variant_warns_for_missing_new_target(
    tmp_path: Path,
) -> None:
    missing_target = tmp_path / "missing-new"
    state = tmp_path / ".trinity"
    write_project_intake(
        state,
        build_project_intake(
            mode="new",
            target_workspace=missing_target,
            product_goal="Build app.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )

    assert (
        project_create_action_variant(state, target_workspace=missing_target)
        == "warning"
    )
    assert (
        project_analyze_action_variant(state, target_workspace=missing_target)
        == "default"
    )


def test_project_intake_state_label_guides_missing_intake(tmp_path: Path) -> None:
    state = tmp_path / ".trinity"
    target = tmp_path / "customer-app"

    assert project_intake_state_label(state) == (
        "Project intake: not recorded | existing: trinity project analyze [PATH] "
        "| new: trinity project new NAME"
    )
    assert project_intake_state_label(state, lang="ko") == (
        "프로젝트 인테이크: 기록 없음 | 기존: trinity project analyze [PATH] "
        "| 신규: trinity project new NAME"
    )
    assert project_intake_state_label(state, target_workspace=target) == (
        "Project intake: not recorded | "
        f"analyze: trinity project analyze {target} | "
        "new: trinity project new NAME"
    )
    assert project_intake_state_label(
        state,
        lang="ko",
        target_workspace=target,
    ) == (
        "프로젝트 인테이크: 기록 없음 | "
        f"분석: trinity project analyze {target} | "
        "신규: trinity project new NAME"
    )


def test_start_and_nexus_missing_project_intake_use_selected_workspace(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    start = StartScreen(config, workspace_candidate=target)
    nexus = NexusScreen(config)
    nexus.snapshot = WorkflowNexusSnapshot(target_workspace=str(target))

    assert f"trinity project analyze {target}" in start._project_intake_label()
    assert f"trinity project analyze {target}" in nexus._project_intake_label()


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
    start = StartScreen(config, workspace_candidate=selected_target)
    nexus = NexusScreen(config)
    nexus.snapshot = WorkflowNexusSnapshot(target_workspace=str(selected_target))

    assert "target mismatch" in start._project_intake_label()
    assert "target mismatch" in nexus._project_intake_label()
    presentation = project_analyze_action_presentation(
        config.effective_state_dir,
        target_workspace=selected_target,
    )
    assert presentation.label_key == "analyze_selected_workspace"
    assert presentation.variant == "warning"


@pytest.mark.asyncio
async def test_start_and_nexus_show_reanalyze_cta_when_target_mismatches(
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

    start = StartScreen(config, workspace_candidate=selected_target)
    start_app = StartScreenHarness(start)
    async with start_app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert str(start.query_one("#analyze-workspace", Button).label) == (
            "Analyze Selected"
        )
        assert start.query_one("#analyze-workspace", Button).variant == "warning"

    nexus = NexusScreen(config)
    nexus.snapshot = WorkflowNexusSnapshot(target_workspace=str(selected_target))
    nexus_app = StartScreenHarness(nexus)  # type: ignore[arg-type]
    async with nexus_app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()

        assert str(nexus.query_one("#nexus-analyze-workspace", Button).label) == (
            "Analyze Selected"
        )
        assert nexus.query_one("#nexus-analyze-workspace", Button).variant == "warning"


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
            "Project intake: existing | target: customer-app | "
            "updated: 2026-06-28 | tests: uv run pytest | git: none"
        )
        assert str(screen.query_one("#project-read-first-checklist", Static).content) == (
            "Read-first checklist: scope: target root | "
            "read: README/docs/source roots missing | "
            "inspect: entrypoints missing | verify: uv run pytest"
        )
        assert screen.query_one("#analyze-workspace", Button).variant == "default"
        assert screen.query_one("#create-project", Button).variant == "default"


@pytest.mark.asyncio
async def test_start_screen_updates_provider_policy_from_recipient_selection(
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

        assert str(screen.query_one("#start-provider-policy", Static).content) == (
            "Provider policy: 2 active (claude, codex) | "
            "execution: parallel capable | review: one peer reviewer"
        )
        assert str(
            screen.query_one("#start-provider-cli-setup", Static).content
        ) == (
            "Provider CLI setup: selected 2 | found: claude | "
            "missing: codex(trinity-missing-cli-for-test) | "
            "next: fix CLI command/PATH"
        )
        assert str(
            screen.query_one("#project-startup-readiness", Static).content
        ) == (
            "Startup readiness: target missing | intake missing | "
            "providers 2 selected | validation missing"
        )

        selector = screen.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(("claude",))
        screen.on_agent_recipient_model_selector_selection_changed(
            AgentRecipientModelSelector.SelectionChanged(selector.selected_agents())
        )
        await pilot.pause()

        assert str(screen.query_one("#start-provider-policy", Static).content) == (
            "Provider policy: 1 active (claude) | "
            "execution: single executor | review: self-check/manual"
        )
        assert str(
            screen.query_one("#start-provider-cli-setup", Static).content
        ) == "Provider CLI setup: selected 1 | found: claude"
        assert str(
            screen.query_one("#project-startup-readiness", Static).content
        ) == (
            "Startup readiness: target missing | intake missing | "
            "providers 1 selected | validation missing"
        )


@pytest.mark.asyncio
async def test_nexus_screen_shows_read_first_checklist(tmp_path: Path) -> None:
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

        assert str(
            screen.query_one("#nexus-project-read-first-checklist", Static).content
        ) == (
            "Read-first checklist: scope: services/api | read: README.md, src | "
            "inspect: entrypoints missing | verify: record validation command"
        )
        assert str(
            screen.query_one("#nexus-project-startup-readiness", Static).content
        ) == (
            "Startup readiness: target ok | intake ok | "
            "providers 1 selected | validation planned"
        )


@pytest.mark.asyncio
async def test_nexus_screen_shows_provider_policy_from_selected_agents(
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

        assert str(screen.query_one("#nexus-provider-policy", Static).content) == (
            "Provider policy: 2 active (claude, codex) | "
            "execution: parallel capable | review: one peer reviewer"
        )
        assert str(
            screen.query_one("#nexus-provider-cli-setup", Static).content
        ) == (
            "Provider CLI setup: selected 2 | found: claude | "
            "missing: codex(trinity-missing-cli-for-test) | "
            "next: fix CLI command/PATH"
        )
        assert str(
            screen.query_one("#nexus-project-startup-readiness", Static).content
        ) == (
            "Startup readiness: target missing | intake missing | "
            "providers 2 selected | validation missing"
        )

        screen.set_agent_selection(("claude", "antigravity"), {})
        await pilot.pause()

        assert str(screen.query_one("#nexus-provider-policy", Static).content) == (
            "Provider policy: 2 active (claude, antigravity) | "
            "execution: parallel capable | review: one peer reviewer"
        )
        assert str(
            screen.query_one("#nexus-provider-cli-setup", Static).content
        ) == "Provider CLI setup: selected 2 | found: claude, antigravity"
        assert str(
            screen.query_one("#nexus-project-startup-readiness", Static).content
        ) == (
            "Startup readiness: target missing | intake missing | "
            "providers 2 selected | validation missing"
        )

        selector = screen.query_one(AgentRecipientModelSelector)
        selector.set_selected_agents(("claude",))
        screen.on_agent_recipient_model_selector_selection_changed(
            AgentRecipientModelSelector.SelectionChanged(selector.selected_agents())
        )
        await pilot.pause()

        assert str(screen.query_one("#nexus-provider-policy", Static).content) == (
            "Provider policy: 1 active (claude) | "
            "execution: single executor | review: self-check/manual"
        )
        assert str(
            screen.query_one("#nexus-provider-cli-setup", Static).content
        ) == "Provider CLI setup: selected 1 | found: claude"
        assert str(
            screen.query_one("#nexus-project-startup-readiness", Static).content
        ) == (
            "Startup readiness: target missing | intake missing | "
            "providers 1 selected | validation missing"
        )


@pytest.mark.asyncio
async def test_start_screen_highlights_edit_brief_for_incomplete_new_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    target.mkdir()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build a dashboard.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    screen = StartScreen(config, workspace_candidate=target)
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert (
            screen.query_one("#edit-project-brief", Button).variant
            == "warning"
        )
        assert str(screen.query_one("#edit-project-brief", Button).label) == (
            "Complete Brief"
        )
        assert screen.query_one("#analyze-workspace", Button).variant == "default"
        assert screen.query_one("#create-project", Button).variant == "default"


@pytest.mark.asyncio
async def test_start_screen_highlights_project_intake_recovery_actions(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    config = TrinityConfig.default_config(project_dir=tmp_path)
    screen = StartScreen(config, workspace_candidate=target)
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert screen.query_one("#analyze-workspace", Button).variant == "warning"
        assert screen.query_one("#create-project", Button).variant == "default"


@pytest.mark.asyncio
async def test_start_screen_refreshes_analyze_action_label_for_changed_intake(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "README.md").write_text("docs\n", encoding="utf-8")
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

        assert str(screen.query_one("#analyze-workspace", Button).label) == (
            "Analyze Existing"
        )

        (target / "src").mkdir()
        screen.refresh_project_intake_summary()
        await pilot.pause()

        assert str(screen.query_one("#analyze-workspace", Button).label) == (
            "Refresh Analysis"
        )
        assert screen.query_one("#analyze-workspace", Button).variant == "warning"


@pytest.mark.asyncio
async def test_nexus_highlights_missing_new_project_target_creation(
    tmp_path: Path,
) -> None:
    target = tmp_path / "missing-new"
    config = TrinityConfig.default_config(project_dir=tmp_path)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build app.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    screen = NexusScreen(config)
    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(target))
    app = StartScreenHarness(screen)  # type: ignore[arg-type]

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert (
            screen.query_one("#nexus-create-project", Button).variant
            == "warning"
        )
        assert (
            screen.query_one("#nexus-analyze-workspace", Button).variant
            == "default"
        )

        write_project_intake(
            config.effective_state_dir,
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
        screen.refresh_project_intake_summary()

        assert (
            screen.query_one("#nexus-edit-project-brief", Button).variant
            == "default"
        )
        assert str(screen.query_one("#nexus-edit-project-brief", Button).label) == (
            "Edit Brief"
        )
        assert (
            screen.query_one("#nexus-create-project", Button).variant
            == "warning"
        )


@pytest.mark.asyncio
async def test_nexus_refreshes_analyze_action_label_for_changed_intake(
    tmp_path: Path,
) -> None:
    target = tmp_path / "customer-app"
    target.mkdir()
    (target / "README.md").write_text("docs\n", encoding="utf-8")
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
    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(target))
    app = StartScreenHarness(screen)  # type: ignore[arg-type]

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert str(screen.query_one("#nexus-analyze-workspace", Button).label) == (
            "기존 프로젝트 분석"
        )

        (target / "src").mkdir()
        screen.refresh_project_intake_summary()
        await pilot.pause()

        assert str(screen.query_one("#nexus-analyze-workspace", Button).label) == (
            "분석 갱신"
        )
        assert screen.query_one("#nexus-analyze-workspace", Button).variant == (
            "warning"
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
        ) == (
            "프로젝트 인테이크: 기존 | 대상: customer-app | "
            "갱신: 2026-06-28 | 테스트: uv run pytest | git: 없음"
        )


@pytest.mark.asyncio
async def test_nexus_screen_highlights_edit_brief_for_incomplete_new_project(
    tmp_path: Path,
) -> None:
    target = tmp_path / "new-app"
    config = TrinityConfig.default_config(project_dir=tmp_path)
    write_project_intake(
        config.effective_state_dir,
        build_project_intake(
            mode="new",
            target_workspace=target,
            product_goal="Build a dashboard.",
            created_at="2026-06-28T00:00:00Z",
        ),
    )
    screen = NexusScreen(config)
    screen.snapshot = WorkflowNexusSnapshot(target_workspace=str(target))
    app = StartScreenHarness(screen)

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()

        assert (
            screen.query_one("#nexus-edit-project-brief", Button).variant
            == "warning"
        )
        assert str(screen.query_one("#nexus-edit-project-brief", Button).label) == (
            "Complete Brief"
        )


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
