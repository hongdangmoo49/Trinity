"""Shared Textual labels for target workspace state."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from trinity.project_intake import (
    ProjectIntake,
    existing_project_intake_drift_fields,
    load_project_intake,
    missing_new_project_brief_field_keys,
    project_intake_read_first_confirmation_needed,
    project_intake_validation_commands,
    project_intake_validation_missing,
)


PROJECT_INTAKE_STALE_AFTER_DAYS = 14

WORKSPACE_STATE_LABELS = {
    "en": {
        "not_selected": "No target workspace selected",
        "planning_target": "Planning target: {target}",
        "control_repo": (
            "Control repo selected; confirmation required before write: {target}"
        ),
    },
    "ko": {
        "not_selected": "대상 작업 폴더 없음",
        "planning_target": "계획 대상: {target}",
        "control_repo": "제어 저장소 선택됨; 쓰기 전 확인 필요: {target}",
    },
}


PROJECT_INTAKE_LABELS = {
    "en": {
        "invalid": (
            "Project intake: unreadable | fix .trinity/project-intake.json "
            "or rerun trinity project analyze [PATH]"
        ),
        "missing": (
            "Project intake: not recorded | existing: trinity project analyze [PATH] "
            "| new: trinity project new NAME"
        ),
        "missing_with_target": (
            "Project intake: not recorded | analyze: trinity project analyze {target} "
            "| new: trinity project new NAME"
        ),
        "build": "build",
        "brief_complete": "brief: complete",
        "brief_missing": "brief: missing {fields}",
        "choose_scope": "choose scope",
        "analysis_missing": "missing",
        "analysis_changed": "analysis: changed {fields}",
        "analysis_sparse": "analysis: sparse",
        "analysis_stale": "analysis: stale {days}d",
        "analysis_refresh": "refresh: trinity project analyze {target}",
        "dev": "dev",
        "docs": "docs",
        "entrypoints": "entry",
        "field_first_milestone": "milestone",
        "field_product_goal": "goal",
        "field_project_type": "type",
        "field_success_criteria": "success",
        "field_target_users": "users",
        "git_clean": "git: {branch} clean",
        "git_dirty": "git: {branch} dirty {dirty}, untracked {untracked}",
        "git_none": "git: none",
        "git": "git",
        "goal": "goal",
        "packages": "packages",
        "constraints": "constraints",
        "first_milestone": "milestone",
        "project_type": "type",
        "read_first": "read first",
        "selected_scope": "scope",
        "scope_candidates": "scopes",
        "source_roots": "src",
        "stack_preferences": "stack",
        "starter_profile": "starter",
        "success_criteria": "success",
        "summary": "Project intake: {mode}",
        "target": "target",
        "target_missing": "target missing: {target}",
        "target_users": "users",
        "target_mismatch": "target mismatch: intake {target}",
        "tests": "tests",
        "tests_none": "(none)",
        "updated": "updated",
    },
    "ko": {
        "invalid": (
            "프로젝트 인테이크: 읽을 수 없음 | .trinity/project-intake.json 수정 "
            "또는 trinity project analyze [PATH] 재실행"
        ),
        "missing": (
            "프로젝트 인테이크: 기록 없음 | 기존: trinity project analyze [PATH] "
            "| 신규: trinity project new NAME"
        ),
        "missing_with_target": (
            "프로젝트 인테이크: 기록 없음 | 분석: trinity project analyze {target} "
            "| 신규: trinity project new NAME"
        ),
        "build": "빌드",
        "brief_complete": "브리프: 완료",
        "brief_missing": "브리프: 누락 {fields}",
        "choose_scope": "범위 선택",
        "analysis_missing": "누락",
        "analysis_changed": "분석: 변경됨 {fields}",
        "analysis_sparse": "분석: 부족",
        "analysis_stale": "분석: 오래됨 {days}일",
        "analysis_refresh": "재분석: trinity project analyze {target}",
        "dev": "개발",
        "docs": "문서",
        "entrypoints": "진입점",
        "field_first_milestone": "마일스톤",
        "field_product_goal": "목표",
        "field_project_type": "유형",
        "field_success_criteria": "성공",
        "field_target_users": "사용자",
        "git_clean": "git: {branch} 변경 없음",
        "git_dirty": "git: {branch} 변경 {dirty}, 미추적 {untracked}",
        "git_none": "git: 없음",
        "git": "git",
        "goal": "목표",
        "packages": "패키지",
        "constraints": "제약",
        "first_milestone": "마일스톤",
        "project_type": "유형",
        "read_first": "먼저 읽기",
        "selected_scope": "선택 범위",
        "scope_candidates": "범위",
        "source_roots": "소스",
        "stack_preferences": "스택",
        "starter_profile": "스타터",
        "success_criteria": "성공",
        "summary": "프로젝트 인테이크: {mode}",
        "target": "대상",
        "target_missing": "대상 없음: {target}",
        "target_users": "사용자",
        "target_mismatch": "대상 불일치: 인테이크 {target}",
        "tests": "테스트",
        "tests_none": "(없음)",
        "updated": "갱신",
    },
}

PROJECT_MODE_LABELS = {
    "en": {
        "existing": "existing",
        "new": "new",
    },
    "ko": {
        "existing": "기존",
        "new": "신규",
    },
}

PROJECT_START_CHOICE_GUIDE_LABELS = {
    "en": {
        "analyze_selected_workspace": "Analyze Selected",
        "analyze_workspace": "Analyze Existing",
        "complete_brief": "Complete Brief",
        "confirm_read_first": "confirm read-first",
        "create_project": "Create New",
        "choose_scope": "choose scope",
        "edit_brief": "Edit Brief",
        "existing": "existing",
        "fix_intake": "fix intake",
        "mode": "mode",
        "new": "new",
        "next": "next",
        "plan_first": "Plan first",
        "record_validation": "record validation",
        "refresh_analysis": "Refresh Analysis",
        "summary": "Project start",
        "then": "then",
    },
    "ko": {
        "analyze_selected_workspace": "선택 대상 분석",
        "analyze_workspace": "기존 프로젝트 분석",
        "complete_brief": "브리프 완성",
        "confirm_read_first": "먼저 읽기 확인",
        "create_project": "새 프로젝트 생성",
        "choose_scope": "범위 선택",
        "edit_brief": "브리프 편집",
        "existing": "기존",
        "fix_intake": "인테이크 복구",
        "mode": "모드",
        "new": "신규",
        "next": "다음",
        "plan_first": "먼저 계획",
        "record_validation": "검증 기록",
        "refresh_analysis": "분석 갱신",
        "summary": "프로젝트 시작",
        "then": "이후",
    },
}

PROJECT_PLAN_PREVIEW_LABELS = {
    "en": {
        "constraints": "guardrails",
        "milestone": "milestone",
        "stack": "stack",
        "starter": "starter",
        "success": "success",
        "summary": "Initial plan preview",
        "users": "users",
    },
    "ko": {
        "constraints": "가드레일",
        "milestone": "마일스톤",
        "stack": "스택",
        "starter": "스타터",
        "success": "성공",
        "summary": "초기 계획 미리보기",
        "users": "사용자",
    },
}

PROJECT_GENERATION_PREVIEW_LABELS = {
    "en": {
        "conflicts": "conflicts",
        "create": "create",
        "guardrails": "guardrails",
        "summary": "Generation preview",
        "validate": "validate",
    },
    "ko": {
        "conflicts": "충돌",
        "create": "생성",
        "guardrails": "가드레일",
        "summary": "생성 미리보기",
        "validate": "검증",
    },
}

PROJECT_VALIDATION_PLAN_LABELS = {
    "en": {
        "fast": "fast",
        "full": "full",
        "full_existing": "full suite before merge",
        "full_new": "first scaffold smoke before release",
        "inspect_scope": "inspect changed scope",
        "record_required": "record required check before merge",
        "required": "required",
        "summary": "Validation plan",
    },
    "ko": {
        "fast": "빠른 확인",
        "full": "전체 확인",
        "full_existing": "병합 전 전체 스위트",
        "full_new": "릴리스 전 첫 스캐폴드 smoke",
        "inspect_scope": "변경 범위 점검",
        "record_required": "병합 전 필수 확인 기록",
        "required": "필수 확인",
        "summary": "검증 계획",
    },
}

PROJECT_READ_FIRST_CHECKLIST_LABELS = {
    "en": {
        "choose_scope": "choose",
        "entrypoints_missing": "entrypoints missing",
        "read_missing": "README/docs/source roots missing",
        "read": "read",
        "record_validation": "record validation command",
        "scope": "scope",
        "summary": "Read-first checklist",
        "target_root": "target root",
        "inspect": "inspect",
        "verify": "verify",
    },
    "ko": {
        "choose_scope": "선택",
        "entrypoints_missing": "진입점 없음",
        "read_missing": "README/docs/source roots 없음",
        "read": "읽기",
        "record_validation": "검증 명령 기록",
        "scope": "범위",
        "summary": "먼저 읽기 체크리스트",
        "target_root": "대상 루트",
        "inspect": "점검",
        "verify": "검증",
    },
}

PROJECT_EXISTING_DIAGNOSTIC_LABELS = {
    "en": {
        "summary": "Existing diagnosis",
        "read": "read",
        "read_missing": "README/docs/source roots missing",
        "tests": "tests",
        "dev": "dev",
        "build": "build",
        "none": "(none)",
        "scope": "scope",
        "choose_scope": "choose",
        "target_root": "target root",
        "git": "git",
    },
    "ko": {
        "summary": "기존 프로젝트 진단",
        "read": "읽기",
        "read_missing": "README/docs/source roots 없음",
        "tests": "테스트",
        "dev": "개발",
        "build": "빌드",
        "none": "(없음)",
        "scope": "범위",
        "choose_scope": "선택",
        "target_root": "대상 루트",
        "git": "git",
    },
}

PROJECT_MODE_RAIL_LABELS = {
    "en": {
        "execute_confirm": "confirm",
        "execute_label": "execute",
        "execute_locked": "locked",
        "execute_ready": "ready",
        "intake_brief_needed": "brief needed",
        "intake_check_target": "check target",
        "intake_label": "intake",
        "intake_needed": "needed",
        "intake_read_first_needed": "read-first needed",
        "intake_ready": "ready",
        "intake_refresh_needed": "refresh needed",
        "intake_scope_needed": "scope needed",
        "intake_unreadable": "unreadable",
        "intake_validation_needed": "validation needed",
        "intake_waiting": "waiting",
        "mode_existing": "existing",
        "mode_label": "mode",
        "mode_new": "new",
        "mode_none": "none",
        "next_analyze_or_create": "analyze existing or create new",
        "next_choose_scope": "choose scope",
        "next_edit_brief": "edit brief",
        "next_label": "next",
        "next_plan": "plan or execute",
        "next_confirm_read_first": "confirm read-first",
        "next_record_validation": "record validation",
        "next_recover_target": "recover target",
        "next_refresh_analysis": "refresh analysis",
        "next_select_workspace": "select workspace",
        "next_switch_or_analyze": "switch target or re-analyze",
        "plan_caution": "caution",
        "plan_label": "plan",
        "plan_locked": "locked",
        "plan_ready": "ready",
        "plan_ready_after_brief": "ready after brief",
        "summary": "Start flow",
        "target_label": "target",
        "target_missing": "missing",
        "target_mismatch": "mismatch",
        "target_needed": "needed",
        "target_ready": "ready",
    },
    "ko": {
        "execute_confirm": "확인 필요",
        "execute_label": "실행",
        "execute_locked": "잠김",
        "execute_ready": "준비됨",
        "intake_brief_needed": "브리프 필요",
        "intake_check_target": "대상 확인",
        "intake_label": "인테이크",
        "intake_needed": "필요",
        "intake_read_first_needed": "먼저 읽기 필요",
        "intake_ready": "준비됨",
        "intake_refresh_needed": "갱신 필요",
        "intake_scope_needed": "범위 필요",
        "intake_unreadable": "읽기 실패",
        "intake_validation_needed": "검증 필요",
        "intake_waiting": "대기",
        "mode_existing": "기존",
        "mode_label": "모드",
        "mode_new": "신규",
        "mode_none": "없음",
        "next_analyze_or_create": "기존 분석 또는 신규 생성",
        "next_choose_scope": "범위 선택",
        "next_edit_brief": "브리프 편집",
        "next_label": "다음",
        "next_plan": "계획 또는 실행",
        "next_confirm_read_first": "먼저 읽기 확인",
        "next_record_validation": "검증 기록",
        "next_recover_target": "대상 복구",
        "next_refresh_analysis": "분석 갱신",
        "next_select_workspace": "작업 폴더 선택",
        "next_switch_or_analyze": "대상 전환 또는 재분석",
        "plan_caution": "주의",
        "plan_label": "계획",
        "plan_locked": "잠김",
        "plan_ready": "준비됨",
        "plan_ready_after_brief": "브리프 후 준비",
        "summary": "시작 흐름",
        "target_label": "대상",
        "target_missing": "없음",
        "target_mismatch": "불일치",
        "target_needed": "필요",
        "target_ready": "준비됨",
    },
}

PROVIDER_EXECUTION_REVIEW_POLICY_LABELS = {
    "en": {
        "summary": "Provider policy",
        "active": "{count} active ({names})",
        "active_none": "0 active",
        "execution_label": "execution",
        "review_label": "review",
        "none": "none",
        "execution_unavailable": "unavailable",
        "review_unavailable": "unavailable",
        "single_executor": "single executor",
        "self_or_manual_review": "self-check/manual",
        "parallel_capable": "parallel capable",
        "one_peer_reviewer": "one peer reviewer",
        "peer_reviewer_pool": "peer reviewer pool",
    },
    "ko": {
        "summary": "프로바이더 정책",
        "active": "활성 {count}개({names})",
        "active_none": "활성 0개",
        "execution_label": "실행",
        "review_label": "리뷰",
        "none": "없음",
        "execution_unavailable": "불가",
        "review_unavailable": "불가",
        "single_executor": "단일 실행",
        "self_or_manual_review": "자체 확인/수동",
        "parallel_capable": "병렬 가능",
        "one_peer_reviewer": "동료 리뷰 1명",
        "peer_reviewer_pool": "동료 리뷰 풀",
    },
}

PROJECT_STARTUP_READINESS_LABELS = {
    "en": {
        "summary": "Startup readiness",
        "target_ok": "target ok",
        "target_missing": "target missing",
        "intake_ok": "intake ok",
        "intake_missing": "intake missing",
        "intake_check": "intake check",
        "providers_count": "providers {count} selected",
        "validation_planned": "validation planned",
        "validation_missing": "validation missing",
    },
    "ko": {
        "summary": "시작 준비",
        "target_ok": "대상 정상",
        "target_missing": "대상 없음",
        "intake_ok": "인테이크 정상",
        "intake_missing": "인테이크 없음",
        "intake_check": "인테이크 확인 필요",
        "providers_count": "프로바이더 {count}개 선택",
        "validation_planned": "검증 계획됨",
        "validation_missing": "검증 없음",
    },
}

PROVIDER_CLI_SETUP_LABELS = {
    "en": {
        "summary": "Provider CLI setup",
        "selected": "selected {count}",
        "found": "found",
        "missing": "missing",
        "next": "next: fix CLI command/PATH",
        "select_provider": "next: select at least one provider",
        "none": "none",
    },
    "ko": {
        "summary": "프로바이더 CLI 설정",
        "selected": "선택 {count}개",
        "found": "발견",
        "missing": "없음",
        "next": "다음: CLI 명령/PATH 수정",
        "select_provider": "다음: 프로바이더를 하나 이상 선택",
        "none": "없음",
    },
}


@dataclass(frozen=True)
class ProjectAnalyzeActionPresentation:
    """Workbench analyze action presentation values."""

    label_key: str
    variant: str


def target_workspace_state_label(
    target: object | None,
    *,
    control_repo: Path | None,
    lang: str = "en",
) -> str:
    """Return a concise user-facing label for the selected target workspace."""
    labels = WORKSPACE_STATE_LABELS.get(lang, WORKSPACE_STATE_LABELS["en"])
    target_text = str(target or "").strip()
    if not target_text:
        return labels["not_selected"]
    if control_repo is not None and _same_resolved_path(Path(target_text), control_repo):
        return labels["control_repo"].format(target=target_text)
    return labels["planning_target"].format(target=target_text)


def provider_execution_review_policy_label(
    agents: Mapping[str, object],
    *,
    selected_agents: Sequence[str] | None = None,
    lang: str = "en",
) -> str:
    """Return a compact execution/review policy label for active providers."""
    labels = PROVIDER_EXECUTION_REVIEW_POLICY_LABELS.get(
        lang,
        PROVIDER_EXECUTION_REVIEW_POLICY_LABELS["en"],
    )
    active_names = _active_provider_names(
        agents,
        selected_agents=selected_agents,
    )
    count = len(active_names)
    if count <= 0:
        active_label = labels["active_none"]
        execution = labels["execution_unavailable"]
        review = labels["review_unavailable"]
    else:
        active_label = labels["active"].format(
            count=count,
            names=_format_project_intake_values(
                active_names,
                empty_label=labels["none"],
                max_items=3,
            ),
        )
        if count == 1:
            execution = labels["single_executor"]
            review = labels["self_or_manual_review"]
        elif count == 2:
            execution = labels["parallel_capable"]
            review = labels["one_peer_reviewer"]
        else:
            execution = labels["parallel_capable"]
            review = labels["peer_reviewer_pool"]
    return (
        f"{labels['summary']}: {active_label} | "
        f"{labels['execution_label']}: {execution} | "
        f"{labels['review_label']}: {review}"
    )


def provider_cli_setup_label(
    agents: Mapping[str, object],
    *,
    selected_agents: Sequence[str] | None = None,
    lang: str = "en",
) -> str:
    """Return a lightweight CLI command availability label for selected providers."""
    labels = PROVIDER_CLI_SETUP_LABELS.get(
        lang,
        PROVIDER_CLI_SETUP_LABELS["en"],
    )
    active_names = _active_provider_names(
        agents,
        selected_agents=selected_agents,
    )
    found_names = tuple(
        name
        for name in active_names
        if _provider_cli_command_found(getattr(agents[name], "cli_command", ""))
    )
    missing_names = tuple(name for name in active_names if name not in found_names)
    parts = [
        labels["selected"].format(count=len(active_names)),
    ]
    if not active_names:
        parts.append(labels["select_provider"])
        return f"{labels['summary']}: {' | '.join(parts)}"
    if found_names:
        parts.append(
            f"{labels['found']}: "
            f"{_format_project_intake_values(found_names, max_items=3)}"
        )
    if missing_names:
        missing_entries = _provider_cli_missing_entries(agents, missing_names)
        parts.append(
            f"{labels['missing']}: "
            f"{_format_project_intake_values(missing_entries, max_items=2)}"
        )
        parts.append(labels["next"])
    if not found_names and not missing_names:
        parts.append(f"{labels['found']}: {labels['none']}")
    return f"{labels['summary']}: {' | '.join(parts)}"


def project_startup_readiness_label(
    state_dir: Path,
    agents: Mapping[str, object],
    *,
    selected_agents: Sequence[str] | None = None,
    lang: str = "en",
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return a compact first-run readiness summary for Start/Nexus."""
    labels = PROJECT_STARTUP_READINESS_LABELS.get(
        lang,
        PROJECT_STARTUP_READINESS_LABELS["en"],
    )
    target_label = (
        labels["target_ok"]
        if _format_project_intake_target(target_workspace)
        else labels["target_missing"]
    )
    intake_label = labels[
        _project_startup_readiness_intake_key(
            state_dir,
            target_workspace=target_workspace,
            today=today,
        )
    ]
    provider_count = len(
        _active_provider_names(agents, selected_agents=selected_agents)
    )
    validation_label = (
        labels["validation_missing"]
        if _project_intake_validation_missing_for_state(
            state_dir,
            target_workspace=target_workspace,
        )
        else labels["validation_planned"]
    )
    return (
        f"{labels['summary']}: {target_label} | {intake_label} | "
        f"{labels['providers_count'].format(count=provider_count)} | "
        f"{validation_label}"
    )


def project_start_choice_guide_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return a compact guide for choosing the new/existing project start path."""
    labels = PROJECT_START_CHOICE_GUIDE_LABELS.get(
        lang,
        PROJECT_START_CHOICE_GUIDE_LABELS["en"],
    )
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return (
            f"{labels['summary']}: {labels['next']} -> {labels['fix_intake']} | "
            f"{labels['then']} {labels['plan_first']}"
        )

    analyze_label = labels[
        project_analyze_action_presentation(
            state_dir,
            target_workspace=target_workspace,
            today=today,
        ).label_key
    ]
    if intake is None or not _project_intake_targets_match(
        intake,
        target_workspace,
    ):
        return (
            f"{labels['summary']}: {labels['existing']} -> {analyze_label} | "
            f"{labels['new']} -> {labels['create_project']} | "
            f"{labels['then']} {labels['plan_first']}"
        )

    mode_label = labels.get(intake.mode, intake.mode)
    next_action = _project_start_choice_next_action(
        intake,
        labels,
        analyze_label,
        state_dir=state_dir,
        target_workspace=target_workspace,
    )
    return (
        f"{labels['summary']}: {labels['mode']} {mode_label} | "
        f"{labels['next']} -> {next_action} | "
        f"{labels['then']} {labels['plan_first']}"
    )


def _project_start_choice_next_action(
    intake: ProjectIntake,
    labels: dict[str, str],
    analyze_label: str,
    *,
    state_dir: Path,
    target_workspace: object | None,
) -> str:
    if intake.mode == "new":
        if _project_intake_target_missing(intake):
            return labels["create_project"]
        if missing_new_project_brief_field_keys(intake):
            return labels[
                project_brief_action_label_key(
                    state_dir,
                    target_workspace=target_workspace,
                )
            ]
        if project_intake_validation_missing(intake):
            return labels["record_validation"]
        return labels["plan_first"]
    if project_analyze_action_presentation(
        state_dir,
        target_workspace=target_workspace,
    ).variant == "warning":
        return analyze_label
    if _project_intake_scope_choice_needed(intake):
        return labels["choose_scope"]
    if project_intake_read_first_confirmation_needed(intake):
        return labels["confirm_read_first"]
    if project_intake_validation_missing(intake):
        return labels["record_validation"]
    return labels["plan_first"]


def project_intake_state_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return a concise label for the saved project intake state."""
    labels = PROJECT_INTAKE_LABELS.get(lang, PROJECT_INTAKE_LABELS["en"])
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return labels["invalid"]
    if intake is None:
        target = _format_project_intake_target(target_workspace)
        if target:
            return labels["missing_with_target"].format(target=target)
        return labels["missing"]
    return format_project_intake_label(
        intake,
        lang=lang,
        target_workspace=target_workspace,
        today=today,
    )


def project_plan_preview_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Return a compact first-plan preview for saved new-project intake."""
    labels = PROJECT_PLAN_PREVIEW_LABELS.get(
        lang,
        PROJECT_PLAN_PREVIEW_LABELS["en"],
    )
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ""
    if intake is None or intake.mode != "new":
        return ""
    if not _project_intake_targets_match(intake, target_workspace):
        return ""
    sections: list[str] = []
    if intake.starter_profile.strip():
        sections.append(
            f"{labels['starter']}: "
            f"{_format_project_intake_text(intake.starter_profile)}"
        )
    if intake.first_milestone.strip():
        sections.append(
            f"{labels['milestone']}: "
            f"{_format_project_intake_text(intake.first_milestone)}"
        )
    if intake.stack_preferences:
        sections.append(
            _format_project_intake_section(
                labels["stack"],
                intake.stack_preferences,
                max_items=3,
            )
        )
    if intake.success_criteria.strip():
        sections.append(
            f"{labels['success']}: "
            f"{_format_project_intake_text(intake.success_criteria)}"
        )
    if intake.target_users.strip():
        sections.append(
            f"{labels['users']}: "
            f"{_format_project_intake_text(intake.target_users)}"
        )
    if intake.constraints:
        sections.append(
            _format_project_intake_section(
                labels["constraints"],
                intake.constraints,
                max_items=2,
            )
        )
    if not sections:
        return ""
    return f"{labels['summary']}: {' | '.join(sections)}"


def project_generation_preview_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Return a compact first-generation preview for saved new-project intake."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ""
    if intake is None:
        return ""
    return format_project_generation_preview_label(
        intake,
        lang=lang,
        target_workspace=target_workspace,
    )


def format_project_generation_preview_label(
    intake: ProjectIntake,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Format a compact first-generation preview for a new-project intake."""
    labels = PROJECT_GENERATION_PREVIEW_LABELS.get(
        lang,
        PROJECT_GENERATION_PREVIEW_LABELS["en"],
    )
    if intake.mode != "new":
        return ""
    if not _project_intake_targets_match(intake, target_workspace):
        return ""
    generation_files = _new_project_generation_files(intake)
    sections = [
        _format_project_intake_section(
            labels["create"],
            generation_files,
            max_items=3,
        ),
        _format_project_intake_section(
            labels["validate"],
            _new_project_generation_validation(intake),
            max_items=2,
        ),
    ]
    if intake.constraints:
        sections.append(
            _format_project_intake_section(
                labels["guardrails"],
                intake.constraints,
                max_items=2,
            )
        )
    conflicts = _new_project_generation_conflicts(intake, generation_files)
    if conflicts:
        sections.append(
            _format_project_intake_section(
                labels["conflicts"],
                conflicts,
                max_items=3,
            )
        )
    return f"{labels['summary']}: {' | '.join(sections)}"


def project_validation_plan_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Return a compact validation plan preview for saved project intake."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ""
    if intake is None:
        return ""
    return format_project_validation_plan_label(
        intake,
        lang=lang,
        target_workspace=target_workspace,
    )


def format_project_validation_plan_label(
    intake: ProjectIntake,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Format fast/required/full validation tiers for project intake."""
    if not _project_intake_targets_match(intake, target_workspace):
        return ""
    labels = PROJECT_VALIDATION_PLAN_LABELS.get(
        lang,
        PROJECT_VALIDATION_PLAN_LABELS["en"],
    )
    sections = (
        _format_project_intake_section(
            labels["fast"],
            _validation_fast_commands(intake, labels),
            max_items=1,
        ),
        _format_project_intake_section(
            labels["required"],
            _validation_required_commands(intake, labels),
            max_items=2,
        ),
        _format_project_intake_section(
            labels["full"],
            _validation_full_commands(intake, labels),
            max_items=2,
        ),
    )
    return f"{labels['summary']}: {' | '.join(sections)}"


def project_read_first_checklist_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Return a compact read-first checklist for saved existing-project intake."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ""
    if intake is None:
        return ""
    return format_project_read_first_checklist_label(
        intake,
        lang=lang,
        target_workspace=target_workspace,
    )


def project_existing_diagnostic_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Return a compact diagnostic summary for saved existing-project intake."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ""
    if intake is None:
        return ""
    return format_project_existing_diagnostic_label(
        intake,
        lang=lang,
        target_workspace=target_workspace,
    )


def format_project_existing_diagnostic_label(
    intake: ProjectIntake,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Format detected existing-project anchors into one scannable summary."""
    if intake.mode != "existing":
        return ""
    if not _project_intake_targets_match(intake, target_workspace):
        return ""
    labels = PROJECT_EXISTING_DIAGNOSTIC_LABELS.get(
        lang,
        PROJECT_EXISTING_DIAGNOSTIC_LABELS["en"],
    )
    sections = (
        _format_project_intake_section(
            labels["read"],
            _existing_diagnostic_read_items(intake, labels),
            max_items=3,
        ),
        _format_project_intake_section(
            labels["tests"],
            intake.test_commands,
            empty_label=labels["none"],
            max_items=2,
        ),
        _format_project_intake_section(
            labels["dev"],
            intake.dev_commands,
            empty_label=labels["none"],
            max_items=2,
        ),
        _format_project_intake_section(
            labels["build"],
            intake.build_commands,
            empty_label=labels["none"],
            max_items=2,
        ),
        _format_existing_diagnostic_scope_section(intake, labels),
        _format_existing_project_git_state(
            intake,
            PROJECT_INTAKE_LABELS.get(lang, PROJECT_INTAKE_LABELS["en"]),
        ),
    )
    return f"{labels['summary']}: {' | '.join(sections)}"


def format_project_read_first_checklist_label(
    intake: ProjectIntake,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
) -> str:
    """Format the minimum read-first checklist for existing-project intake."""
    if intake.mode != "existing":
        return ""
    if not _project_intake_targets_match(intake, target_workspace):
        return ""
    labels = PROJECT_READ_FIRST_CHECKLIST_LABELS.get(
        lang,
        PROJECT_READ_FIRST_CHECKLIST_LABELS["en"],
    )
    sections = (
        _format_read_first_scope_section(intake, labels),
        _format_project_intake_section(
            labels["read"],
            _read_first_read_items(intake, labels),
            max_items=3,
        ),
        _format_project_intake_section(
            labels["inspect"],
            _read_first_inspect_items(intake, labels),
            max_items=2,
        ),
        _format_project_intake_section(
            labels["verify"],
            _read_first_verify_items(intake, labels),
            max_items=2,
        ),
    )
    return f"{labels['summary']}: {' | '.join(sections)}"


def _existing_diagnostic_read_items(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    items = tuple(
        dict.fromkeys(
            (*intake.docs_found, *intake.source_roots, *intake.entrypoints)
        )
    )
    return items or (labels["read_missing"],)


def _format_existing_diagnostic_scope_section(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    selected_scope = intake.selected_scope.strip()
    if selected_scope:
        return _format_project_intake_section(labels["scope"], (selected_scope,))
    if intake.scope_candidates:
        values = _format_project_intake_values(intake.scope_candidates, max_items=2)
        return f"{labels['scope']}: {labels['choose_scope']} {values}"
    return _format_project_intake_section(
        labels["scope"],
        (labels["target_root"],),
    )


def _format_read_first_scope_section(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    selected_scope = intake.selected_scope.strip()
    if selected_scope:
        return _format_project_intake_section(labels["scope"], (selected_scope,))
    if intake.scope_candidates:
        values = _format_project_intake_values(intake.scope_candidates, max_items=2)
        return f"{labels['scope']}: {labels['choose_scope']} {values}"
    return _format_project_intake_section(
        labels["scope"],
        (labels["target_root"],),
    )


def project_mode_rail_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return the current project journey as a compact stage rail."""
    labels = PROJECT_MODE_RAIL_LABELS.get(lang, PROJECT_MODE_RAIL_LABELS["en"])
    target_text = str(target_workspace or "").strip()
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"] if target_text else labels["target_needed"],
            intake=labels["intake_unreadable"],
            plan=labels["plan_locked"],
            execute=labels["execute_locked"],
            mode=labels["mode_none"],
            next_action=labels["next_analyze_or_create"],
        )

    if intake is None:
        if not target_text:
            return _format_project_mode_rail(
                labels,
                target=labels["target_needed"],
                intake=labels["intake_waiting"],
                plan=labels["plan_locked"],
                execute=labels["execute_locked"],
                mode=labels["mode_none"],
                next_action=labels["next_select_workspace"],
            )
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_needed"],
            plan=labels["plan_locked"],
            execute=labels["execute_locked"],
            mode=labels["mode_none"],
            next_action=labels["next_analyze_or_create"],
        )

    mode = labels["mode_new"] if intake.mode == "new" else labels["mode_existing"]
    if target_text and not _project_intake_targets_match(intake, target_workspace):
        return _format_project_mode_rail(
            labels,
            target=labels["target_mismatch"],
            intake=labels["intake_check_target"],
            plan=labels["plan_locked"],
            execute=labels["execute_locked"],
            mode=mode,
            next_action=labels["next_switch_or_analyze"],
        )
    if _project_intake_target_missing(intake):
        return _format_project_mode_rail(
            labels,
            target=labels["target_missing"],
            intake=labels["intake_check_target"],
            plan=labels["plan_locked"],
            execute=labels["execute_locked"],
            mode=mode,
            next_action=labels["next_recover_target"],
        )
    if intake.mode == "new":
        if missing_new_project_brief_field_keys(intake):
            return _format_project_mode_rail(
                labels,
                target=labels["target_ready"],
                intake=labels["intake_brief_needed"],
                plan=labels["plan_ready_after_brief"],
                execute=labels["execute_locked"],
                mode=mode,
                next_action=labels["next_edit_brief"],
            )
        if project_intake_validation_missing(intake):
            return _format_project_mode_rail(
                labels,
                target=labels["target_ready"],
                intake=labels["intake_validation_needed"],
                plan=labels["plan_caution"],
                execute=labels["execute_locked"],
                mode=mode,
                next_action=labels["next_record_validation"],
            )
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_ready"],
            plan=labels["plan_ready"],
            execute=labels["execute_ready"],
            mode=mode,
            next_action=labels["next_plan"],
        )
    if _project_intake_analysis_is_sparse(intake):
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_refresh_needed"],
            plan=labels["plan_caution"],
            execute=labels["execute_confirm"],
            mode=mode,
            next_action=labels["next_refresh_analysis"],
        )
    if _project_intake_analysis_stale_days(intake, today=today) is not None:
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_refresh_needed"],
            plan=labels["plan_caution"],
            execute=labels["execute_confirm"],
            mode=mode,
            next_action=labels["next_refresh_analysis"],
        )
    if _project_intake_analysis_changed_fields(
        intake,
        target_workspace,
        today=today,
    ):
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_refresh_needed"],
            plan=labels["plan_caution"],
            execute=labels["execute_confirm"],
            mode=mode,
            next_action=labels["next_refresh_analysis"],
        )
    if _project_intake_scope_choice_needed(intake):
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_scope_needed"],
            plan=labels["plan_caution"],
            execute=labels["execute_confirm"],
            mode=mode,
            next_action=labels["next_choose_scope"],
        )
    if project_intake_read_first_confirmation_needed(intake):
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_read_first_needed"],
            plan=labels["plan_caution"],
            execute=labels["execute_confirm"],
            mode=mode,
            next_action=labels["next_confirm_read_first"],
        )
    if project_intake_validation_missing(intake):
        return _format_project_mode_rail(
            labels,
            target=labels["target_ready"],
            intake=labels["intake_validation_needed"],
            plan=labels["plan_caution"],
            execute=labels["execute_confirm"],
            mode=mode,
            next_action=labels["next_record_validation"],
        )
    return _format_project_mode_rail(
        labels,
        target=labels["target_ready"],
        intake=labels["intake_ready"],
        plan=labels["plan_ready"],
        execute=labels["execute_ready"],
        mode=mode,
        next_action=labels["next_plan"],
    )


def _format_project_mode_rail(
    labels: dict[str, str],
    *,
    target: str,
    intake: str,
    plan: str,
    execute: str,
    mode: str,
    next_action: str,
) -> str:
    return (
        f"{labels['summary']}: "
        f"{labels['target_label']}: {target} -> "
        f"{labels['intake_label']}: {intake} -> "
        f"{labels['plan_label']}: {plan} -> "
        f"{labels['execute_label']}: {execute} | "
        f"{labels['mode_label']}: {mode} | "
        f"{labels['next_label']}: {next_action}"
    )


def _project_startup_readiness_intake_key(
    state_dir: Path,
    *,
    target_workspace: object | None,
    today: date | None,
) -> str:
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return "intake_check"
    if intake is None:
        return "intake_missing"
    if not _project_intake_targets_match(intake, target_workspace):
        return "intake_check"
    if _project_intake_target_missing(intake):
        return "intake_check"
    if intake.mode == "new":
        if missing_new_project_brief_field_keys(intake):
            return "intake_check"
        if project_intake_validation_missing(intake):
            return "intake_check"
        return "intake_ok"
    if _project_intake_analysis_is_sparse(intake):
        return "intake_check"
    if _project_intake_analysis_stale_days(intake, today=today) is not None:
        return "intake_check"
    if _project_intake_analysis_changed_fields(
        intake,
        target_workspace,
        today=today,
    ):
        return "intake_check"
    if _project_intake_scope_choice_needed(intake):
        return "intake_check"
    if project_intake_read_first_confirmation_needed(intake):
        return "intake_check"
    if project_intake_validation_missing(intake):
        return "intake_check"
    return "intake_ok"


def _project_intake_validation_missing_for_state(
    state_dir: Path,
    *,
    target_workspace: object | None,
) -> bool:
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return True
    if intake is None:
        return True
    if not _project_intake_targets_match(intake, target_workspace):
        return True
    if _project_intake_target_missing(intake):
        return True
    return project_intake_validation_missing(intake)


def project_brief_action_variant(
    state_dir: Path,
    *,
    target_workspace: object | None = None,
) -> str:
    """Return the Workbench Edit Brief button variant for saved intake state."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return "default"
    if intake is None:
        return "default"
    if not _project_intake_targets_match(intake, target_workspace):
        return "default"
    if intake.mode == "new" and missing_new_project_brief_field_keys(intake):
        return "warning"
    return "default"


def project_brief_action_label_key(
    state_dir: Path,
    *,
    target_workspace: object | None = None,
) -> str:
    """Return the Workbench brief action label key for saved intake state."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return "edit_brief"
    if intake is None:
        return "edit_brief"
    if not _project_intake_targets_match(intake, target_workspace):
        return "edit_brief"
    if intake.mode == "new" and missing_new_project_brief_field_keys(intake):
        return "complete_brief"
    return "edit_brief"


def project_analyze_action_variant(
    state_dir: Path,
    *,
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return the Workbench Analyze Workspace button variant."""
    return project_analyze_action_presentation(
        state_dir,
        target_workspace=target_workspace,
        today=today,
    ).variant


def project_analyze_action_label_key(
    state_dir: Path,
    *,
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return the Workbench analyze action label key for saved intake state."""
    return project_analyze_action_presentation(
        state_dir,
        target_workspace=target_workspace,
        today=today,
    ).label_key


def project_analyze_action_presentation(
    state_dir: Path,
    *,
    target_workspace: object | None = None,
    today: date | None = None,
) -> ProjectAnalyzeActionPresentation:
    """Return label and variant for the Workbench analyze action."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ProjectAnalyzeActionPresentation("analyze_workspace", "warning")
    if intake is None:
        if _format_project_intake_target(target_workspace):
            return ProjectAnalyzeActionPresentation("analyze_workspace", "warning")
        return ProjectAnalyzeActionPresentation("analyze_workspace", "default")
    if not _project_intake_targets_match(intake, target_workspace):
        return ProjectAnalyzeActionPresentation(
            "analyze_selected_workspace",
            "warning",
        )
    if _project_intake_target_missing(intake):
        variant = "warning" if intake.mode != "new" else "default"
        return ProjectAnalyzeActionPresentation("analyze_workspace", variant)
    if intake.mode != "existing":
        return ProjectAnalyzeActionPresentation("analyze_workspace", "default")
    if _project_intake_analysis_is_sparse(intake):
        return ProjectAnalyzeActionPresentation("refresh_analysis", "warning")
    if _project_intake_analysis_stale_days(intake, today=today) is not None:
        return ProjectAnalyzeActionPresentation("refresh_analysis", "warning")
    if _project_intake_analysis_changed_fields(intake, target_workspace, today=today):
        return ProjectAnalyzeActionPresentation("refresh_analysis", "warning")
    return ProjectAnalyzeActionPresentation("analyze_workspace", "default")


def project_create_action_variant(
    state_dir: Path,
    *,
    target_workspace: object | None = None,
) -> str:
    """Return the Workbench Create Project button variant."""
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return "default"
    if intake is None:
        return "default"
    if not _project_intake_targets_match(intake, target_workspace):
        return "default"
    if intake.mode == "new" and _project_intake_target_missing(intake):
        return "warning"
    return "default"


def format_project_intake_label(
    intake: ProjectIntake,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return a concise label for a loaded project intake value."""
    return _format_project_intake_label(
        intake,
        lang=lang,
        target_workspace=target_workspace,
        today=today,
    )


def _format_project_intake_label(
    intake: ProjectIntake,
    *,
    lang: str,
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    labels = PROJECT_INTAKE_LABELS.get(lang, PROJECT_INTAKE_LABELS["en"])
    mode_labels = PROJECT_MODE_LABELS.get(lang, PROJECT_MODE_LABELS["en"])
    mode = mode_labels.get(intake.mode, intake.mode)
    parts = [
        labels["summary"].format(mode=mode),
    ]
    target_name = _format_project_intake_target_name(intake.target_workspace)
    if target_name:
        parts.append(f"{labels['target']}: {target_name}")
    mismatch = _format_project_intake_target_mismatch(
        intake,
        target_workspace,
        labels,
    )
    if mismatch:
        parts.append(mismatch)
    missing_target = _format_project_intake_target_missing(intake, labels)
    if missing_target:
        parts.append(missing_target)
    updated = _format_project_intake_timestamp(intake.created_at)
    if updated:
        parts.append(f"{labels['updated']}: {updated}")
    stale_days = _project_intake_analysis_stale_days(intake, today=today)
    if stale_days is not None:
        parts.append(labels["analysis_stale"].format(days=stale_days))
        parts.append(
            labels["analysis_refresh"].format(
                target=_format_project_intake_target(intake.target_workspace)
            )
        )
    changed_fields = _project_intake_analysis_changed_fields(
        intake,
        target_workspace,
        today=today,
    )
    if changed_fields:
        parts.append(
            labels["analysis_changed"].format(
                fields=_format_project_intake_values(
                    _project_intake_changed_field_labels(changed_fields, labels),
                    max_items=3,
                )
            )
        )
        parts.append(
            labels["analysis_refresh"].format(
                target=_format_project_intake_target(intake.target_workspace)
            )
        )
    parts.append(
        _format_project_intake_section(
            labels["tests"],
            intake.test_commands,
            empty_label=labels["tests_none"],
        )
    )
    if intake.mode == "new":
        parts.append(_format_new_project_brief_readiness(intake, labels))
    if _project_intake_analysis_is_sparse(intake):
        parts.append(labels["analysis_sparse"])
        parts.append(
            _format_project_intake_section(
                labels["analysis_missing"],
                _project_intake_missing_analysis_anchors(intake, labels),
                max_items=3,
            )
        )
    read_preview = _format_existing_project_read_preview(intake, labels)
    if read_preview:
        parts.append(read_preview)
    git_state = _format_existing_project_git_state(intake, labels)
    if git_state:
        parts.append(git_state)
    if intake.product_goal.strip():
        parts.append(
            f"{labels['goal']}: {_format_project_intake_text(intake.product_goal)}"
        )
    if intake.project_type.strip():
        value = _format_project_intake_text(intake.project_type)
        parts.append(
            f"{labels['project_type']}: {value}"
        )
    if intake.starter_profile.strip():
        value = _format_project_intake_text(intake.starter_profile)
        parts.append(
            f"{labels['starter_profile']}: {value}"
        )
    if intake.target_users.strip():
        value = _format_project_intake_text(intake.target_users)
        parts.append(
            f"{labels['target_users']}: {value}"
        )
    if intake.success_criteria.strip():
        value = _format_project_intake_text(intake.success_criteria)
        parts.append(
            f"{labels['success_criteria']}: {value}"
        )
    if intake.first_milestone.strip():
        value = _format_project_intake_text(intake.first_milestone)
        parts.append(
            f"{labels['first_milestone']}: {value}"
        )
    for label_key, values in (
        ("stack_preferences", intake.stack_preferences),
        ("constraints", intake.constraints),
    ):
        if values:
            parts.append(_format_project_intake_section(labels[label_key], values))
    parts.extend(_format_existing_project_scope_summary(intake, labels))
    for label_key, values in (
        ("dev", intake.dev_commands),
        ("build", intake.build_commands),
        ("source_roots", intake.source_roots),
        ("entrypoints", intake.entrypoints),
        ("docs", intake.docs_found),
    ):
        if values:
            parts.append(_format_project_intake_section(labels[label_key], values))
    return " | ".join(parts)


def _format_existing_project_scope_summary(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    if intake.mode != "existing":
        return ()
    selected_scope = intake.selected_scope.strip()
    if selected_scope:
        sections = [
            _format_project_intake_section(labels["selected_scope"], (selected_scope,))
        ]
        if intake.scope_candidates:
            sections.append(
                _format_project_intake_section(
                    labels["scope_candidates"],
                    intake.scope_candidates,
                )
            )
        return tuple(sections)
    if intake.scope_candidates:
        return (
            _format_project_intake_section(
                labels["choose_scope"],
                intake.scope_candidates,
            ),
        )
    return ()


def _format_existing_project_git_state(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    if intake.mode != "existing":
        return ""
    if not intake.git_repo:
        return labels["git_none"]
    dirty = _format_optional_count(intake.dirty_count)
    untracked = _format_optional_count(intake.untracked_count)
    branch = intake.branch or "unknown"
    if dirty == "0" and untracked == "0":
        return labels["git_clean"].format(branch=branch)
    return labels["git_dirty"].format(
        branch=branch,
        dirty=dirty,
        untracked=untracked,
    )


def _format_existing_project_read_preview(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    if intake.mode != "existing":
        return ""
    anchors = tuple(dict.fromkeys((*intake.docs_found, *intake.source_roots)))
    if not anchors:
        return ""
    return _format_project_intake_section(
        labels["read_first"],
        anchors,
        max_items=3,
    )


def _format_new_project_brief_readiness(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    missing = missing_new_project_brief_field_keys(intake)
    if not missing:
        return labels["brief_complete"]
    field_labels = tuple(labels[f"field_{field_name}"] for field_name in missing)
    return labels["brief_missing"].format(
        fields=_format_project_intake_values(field_labels)
    )


def _new_project_generation_files(intake: ProjectIntake) -> tuple[str, ...]:
    text = _new_project_generation_signal_text(intake)
    if "docs" in text or "documentation" in text:
        return ("README.md", "docs/")
    if any(
        token in text
        for token in ("react", "vite", "frontend", "web", "node", "javascript", "typescript")
    ):
        return ("README.md", "package.json", "src/", "tests/")
    if any(
        token in text
        for token in ("python", "textual", "fastapi", "cli", "package")
    ):
        return ("README.md", "pyproject.toml", "src/", "tests/")
    return ("README.md", "src/", "tests/")


def _new_project_generation_conflicts(
    intake: ProjectIntake,
    paths: tuple[str, ...],
) -> tuple[str, ...]:
    target = intake.target_workspace
    conflicts: list[str] = []
    for item in paths:
        relative = item.strip()
        if not relative:
            continue
        candidate = target / relative.rstrip("/")
        try:
            exists = candidate.exists()
        except OSError:
            exists = False
        if exists:
            conflicts.append(relative)
    return tuple(conflicts)


def _new_project_generation_validation(intake: ProjectIntake) -> tuple[str, ...]:
    if intake.validation_commands:
        return intake.validation_commands
    if intake.test_commands:
        return intake.test_commands
    text = _new_project_generation_signal_text(intake)
    if "pnpm" in text:
        return ("pnpm test",)
    if any(
        token in text
        for token in ("react", "vite", "frontend", "web", "node", "npm", "javascript", "typescript")
    ):
        return ("npm test",)
    if any(
        token in text
        for token in ("python", "textual", "fastapi", "cli", "package")
    ):
        return ("uv run pytest",)
    return ("define first smoke check",)


def _new_project_generation_signal_text(intake: ProjectIntake) -> str:
    values = (
        intake.starter_profile,
        intake.project_type,
        intake.product_goal,
        *intake.stack_preferences,
    )
    return " ".join(value.strip().lower() for value in values if value.strip())


def _validation_fast_commands(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    commands = project_intake_validation_commands(intake)
    if commands:
        return (commands[0],)
    if intake.test_commands:
        return (intake.test_commands[0],)
    if intake.mode == "new":
        return _new_project_generation_validation(intake)
    return (labels["inspect_scope"],)


def _validation_required_commands(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    if intake.validation_commands:
        return intake.validation_commands
    if intake.test_commands:
        return intake.test_commands
    if intake.build_commands:
        return intake.build_commands
    return (labels["record_required"],)


def _validation_full_commands(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    if intake.test_commands and intake.build_commands:
        return intake.build_commands
    if intake.mode == "new":
        return (labels["full_new"],)
    return (labels["full_existing"],)


def _read_first_read_items(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    anchors = tuple(dict.fromkeys((*intake.docs_found, *intake.source_roots)))
    return anchors or (labels["read_missing"],)


def _read_first_inspect_items(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    return intake.entrypoints or (labels["entrypoints_missing"],)


def _read_first_verify_items(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    if intake.test_commands:
        return intake.test_commands
    if intake.build_commands:
        return intake.build_commands
    return (labels["record_validation"],)


def _project_intake_analysis_is_sparse(intake: ProjectIntake) -> bool:
    if intake.mode != "existing":
        return False
    return not (
        intake.test_commands
        or intake.source_roots
        or intake.scope_candidates
        or intake.docs_found
    )


def _project_intake_scope_choice_needed(intake: ProjectIntake) -> bool:
    if intake.mode != "existing":
        return False
    return bool(intake.scope_candidates and not intake.selected_scope.strip())


def _project_intake_analysis_stale_days(
    intake: ProjectIntake,
    *,
    today: date | None = None,
) -> int | None:
    if intake.mode != "existing":
        return None
    created_on = _project_intake_created_date(intake.created_at)
    if created_on is None:
        return None
    current_date = today or date.today()
    age_days = (current_date - created_on).days
    if age_days <= PROJECT_INTAKE_STALE_AFTER_DAYS:
        return None
    return age_days


def _project_intake_analysis_changed_fields(
    intake: ProjectIntake,
    target_workspace: object | None,
    *,
    today: date | None = None,
) -> tuple[str, ...]:
    if intake.mode != "existing":
        return ()
    if not _project_intake_targets_match(intake, target_workspace):
        return ()
    if _project_intake_target_missing(intake):
        return ()
    if _project_intake_analysis_is_sparse(intake):
        return ()
    if _project_intake_analysis_stale_days(intake, today=today) is not None:
        return ()
    return existing_project_intake_drift_fields(intake, intake.target_workspace)


def _project_intake_changed_field_labels(
    fields: tuple[str, ...],
    labels: dict[str, str],
) -> tuple[str, ...]:
    label_keys = {
        "git_repo": "git",
        "branch": "git",
        "dirty_count": "git",
        "untracked_count": "git",
        "package_managers": "packages",
        "test_commands": "tests",
        "dev_commands": "dev",
        "build_commands": "build",
        "entrypoints": "entrypoints",
        "source_roots": "source_roots",
        "scope_candidates": "scope_candidates",
        "docs_found": "docs",
    }
    field_labels = [
        labels[label_key]
        for field in fields
        if (label_key := label_keys.get(field)) is not None
    ]
    return tuple(dict.fromkeys(field_labels))


def _project_intake_created_date(value: str) -> date | None:
    text = value.strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _project_intake_missing_analysis_anchors(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    if intake.mode != "existing":
        return ()
    missing: list[str] = []
    if not intake.test_commands:
        missing.append(labels["tests"])
    if not intake.source_roots:
        missing.append(labels["source_roots"])
    if not intake.docs_found:
        missing.append(labels["docs"])
    return tuple(missing)


def _format_optional_count(value: int | None) -> str:
    return str(value) if value is not None else "unknown"


def _active_provider_names(
    agents: Mapping[str, object],
    *,
    selected_agents: Sequence[str] | None = None,
) -> tuple[str, ...]:
    enabled_names = tuple(
        name
        for name, spec in agents.items()
        if bool(getattr(spec, "enabled", False))
    )
    if selected_agents is None:
        return enabled_names
    requested = {
        str(name).strip()
        for name in selected_agents
        if str(name).strip()
    }
    return tuple(name for name in enabled_names if name in requested)


def _provider_cli_command_found(command: object) -> bool:
    executable = _provider_cli_executable(command)
    if not executable:
        return False
    if _looks_like_path(executable):
        path = Path(executable).expanduser()
        return path.exists() and path.is_file()
    return shutil.which(executable) is not None


def _provider_cli_missing_entries(
    agents: Mapping[str, object],
    names: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        _provider_cli_missing_entry(
            name,
            getattr(agents[name], "cli_command", ""),
        )
        for name in names
    )


def _provider_cli_missing_entry(name: str, command: object) -> str:
    display_command = _provider_cli_display_command(command)
    if not display_command or display_command.lower() == name.lower():
        return name
    return f"{name}({display_command})"


def _provider_cli_display_command(command: object) -> str:
    executable = _provider_cli_executable(command)
    if not executable:
        return ""
    return executable.replace("\\", "/").rsplit("/", 1)[-1]


def _provider_cli_executable(command: object) -> str:
    raw = str(command or "").strip()
    quoted = _provider_cli_quoted_executable(raw)
    if quoted:
        return quoted
    if _looks_like_path(raw):
        return raw
    return raw.split(maxsplit=1)[0] if raw else ""


def _provider_cli_quoted_executable(command: str) -> str:
    if len(command) < 2 or command[0] not in {"'", '"'}:
        return ""
    quote = command[0]
    end_index = command.find(quote, 1)
    if end_index < 0:
        return ""
    return command[1:end_index].strip()


def _looks_like_path(value: str) -> bool:
    if not value:
        return False
    separators = {os.sep, "/", "\\"}
    if os.altsep:
        separators.add(os.altsep)
    return any(separator and separator in value for separator in separators)


def _format_project_intake_section(
    label: str,
    values: tuple[str, ...],
    *,
    empty_label: str = "",
    max_items: int = 2,
) -> str:
    formatted = _format_project_intake_values(
        values,
        empty_label=empty_label,
        max_items=max_items,
    )
    return f"{label}: {formatted}"


def _format_project_intake_values(
    values: tuple[str, ...],
    *,
    empty_label: str = "",
    max_items: int = 2,
) -> str:
    if not values:
        return empty_label
    visible = values[:max_items]
    suffix = (
        f" +{len(values) - len(visible)}"
        if len(values) > len(visible)
        else ""
    )
    return f"{', '.join(visible)}{suffix}"


def _format_project_intake_text(value: str, *, max_chars: int = 64) -> str:
    text = " ".join(value.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _format_project_intake_timestamp(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return _format_project_intake_text(text, max_chars=24)


def _format_project_intake_target(target: object | None) -> str:
    text = str(target or "").strip()
    if not text:
        return ""
    if any(char.isspace() for char in text) or '"' in text:
        escaped = text.replace('"', r"\"")
        return f'"{escaped}"'
    return text


def _format_project_intake_target_name(target: object | None) -> str:
    text = str(target or "").strip()
    if not text:
        return ""
    normalized = text.rstrip("\\/")
    if "\\" in normalized:
        name = normalized.replace("\\", "/").split("/")[-1]
    else:
        name = Path(normalized).name
    return _format_project_intake_text(name or text, max_chars=40)


def _format_project_intake_target_mismatch(
    intake: ProjectIntake,
    target: object | None,
    labels: dict[str, str],
) -> str:
    target_text = str(target or "").strip()
    if not target_text:
        return ""
    if _project_intake_targets_match(intake, target):
        return ""
    intake_target = _format_project_intake_target(intake.target_workspace)
    return labels["target_mismatch"].format(target=intake_target)


def _format_project_intake_target_missing(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    if not _project_intake_target_missing(intake):
        return ""
    target = _format_project_intake_target(intake.target_workspace)
    return labels["target_missing"].format(target=target)


def _project_intake_target_missing(intake: ProjectIntake) -> bool:
    try:
        return not intake.target_workspace.exists()
    except OSError:
        return True


def _project_intake_targets_match(
    intake: ProjectIntake,
    target: object | None,
) -> bool:
    target_text = str(target or "").strip()
    if not target_text:
        return True
    return _same_resolved_path(Path(target_text), intake.target_workspace)


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()
