"""Shared Textual labels for target workspace state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from trinity.project_intake import (
    ProjectIntake,
    existing_project_intake_drift_fields,
    load_project_intake,
    missing_new_project_brief_field_keys,
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
        "create": "create",
        "guardrails": "guardrails",
        "summary": "Generation preview",
        "validate": "validate",
    },
    "ko": {
        "create": "생성",
        "guardrails": "가드레일",
        "summary": "생성 미리보기",
        "validate": "검증",
    },
}

PROJECT_MODE_RAIL_LABELS = {
    "en": {
        "invalid": "intake unreadable",
        "mode_existing": "existing",
        "mode_new": "new",
        "mode_none": "none",
        "next_analyze_or_create": "analyze existing or create new",
        "next_edit_brief": "edit brief",
        "next_plan": "plan or execute",
        "next_recover_target": "recover target",
        "next_refresh_analysis": "refresh analysis",
        "next_select_workspace": "select workspace",
        "next_switch_or_analyze": "switch target or re-analyze",
        "state_analysis_changed": "analysis changed",
        "state_analysis_sparse": "analysis sparse",
        "state_analysis_stale": "analysis stale",
        "state_brief_missing": "brief missing",
        "state_intake_missing": "intake missing",
        "state_ready": "ready",
        "state_target_missing": "target missing",
        "state_target_mismatch": "target mismatch",
        "state_target_unselected": "target not selected",
        "summary": "Mode rail",
        "state_label": "state",
        "next_label": "next",
    },
    "ko": {
        "invalid": "인테이크 읽기 실패",
        "mode_existing": "기존",
        "mode_new": "신규",
        "mode_none": "없음",
        "next_analyze_or_create": "기존 분석 또는 신규 생성",
        "next_edit_brief": "브리프 편집",
        "next_plan": "계획 또는 실행",
        "next_recover_target": "대상 복구",
        "next_refresh_analysis": "분석 갱신",
        "next_select_workspace": "작업 폴더 선택",
        "next_switch_or_analyze": "대상 전환 또는 재분석",
        "state_analysis_changed": "분석 변경됨",
        "state_analysis_sparse": "분석 부족",
        "state_analysis_stale": "분석 오래됨",
        "state_brief_missing": "브리프 누락",
        "state_intake_missing": "인테이크 없음",
        "state_ready": "준비됨",
        "state_target_missing": "대상 없음",
        "state_target_mismatch": "대상 불일치",
        "state_target_unselected": "대상 미선택",
        "summary": "모드 레일",
        "state_label": "상태",
        "next_label": "다음",
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
    sections = [
        _format_project_intake_section(
            labels["create"],
            _new_project_generation_files(intake),
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
    return f"{labels['summary']}: {' | '.join(sections)}"


def project_mode_rail_label(
    state_dir: Path,
    *,
    lang: str = "en",
    target_workspace: object | None = None,
    today: date | None = None,
) -> str:
    """Return the current project journey mode and next action label."""
    labels = PROJECT_MODE_RAIL_LABELS.get(lang, PROJECT_MODE_RAIL_LABELS["en"])
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return _format_project_mode_rail(
            labels,
            mode=labels["mode_none"],
            state=labels["invalid"],
            next_action=labels["next_analyze_or_create"],
        )

    target_text = str(target_workspace or "").strip()
    if intake is None:
        if not target_text:
            return _format_project_mode_rail(
                labels,
                mode=labels["mode_none"],
                state=labels["state_target_unselected"],
                next_action=labels["next_select_workspace"],
            )
        return _format_project_mode_rail(
            labels,
            mode=labels["mode_none"],
            state=labels["state_intake_missing"],
            next_action=labels["next_analyze_or_create"],
        )

    mode = labels["mode_new"] if intake.mode == "new" else labels["mode_existing"]
    if target_text and not _project_intake_targets_match(intake, target_workspace):
        return _format_project_mode_rail(
            labels,
            mode=mode,
            state=labels["state_target_mismatch"],
            next_action=labels["next_switch_or_analyze"],
        )
    if _project_intake_target_missing(intake):
        return _format_project_mode_rail(
            labels,
            mode=mode,
            state=labels["state_target_missing"],
            next_action=labels["next_recover_target"],
        )
    if intake.mode == "new":
        if missing_new_project_brief_field_keys(intake):
            return _format_project_mode_rail(
                labels,
                mode=mode,
                state=labels["state_brief_missing"],
                next_action=labels["next_edit_brief"],
            )
        return _format_project_mode_rail(
            labels,
            mode=mode,
            state=labels["state_ready"],
            next_action=labels["next_plan"],
        )
    if _project_intake_analysis_is_sparse(intake):
        return _format_project_mode_rail(
            labels,
            mode=mode,
            state=labels["state_analysis_sparse"],
            next_action=labels["next_refresh_analysis"],
        )
    if _project_intake_analysis_stale_days(intake, today=today) is not None:
        return _format_project_mode_rail(
            labels,
            mode=mode,
            state=labels["state_analysis_stale"],
            next_action=labels["next_refresh_analysis"],
        )
    if _project_intake_analysis_changed_fields(
        intake,
        target_workspace,
        today=today,
    ):
        return _format_project_mode_rail(
            labels,
            mode=mode,
            state=labels["state_analysis_changed"],
            next_action=labels["next_refresh_analysis"],
        )
    return _format_project_mode_rail(
        labels,
        mode=mode,
        state=labels["state_ready"],
        next_action=labels["next_plan"],
    )


def _format_project_mode_rail(
    labels: dict[str, str],
    *,
    mode: str,
    state: str,
    next_action: str,
) -> str:
    return (
        f"{labels['summary']}: {mode} | "
        f"{labels['state_label']}: {state} | "
        f"{labels['next_label']}: {next_action}"
    )


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
        return ProjectAnalyzeActionPresentation("analyze_workspace", "warning")
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
    for label_key, values in (
        ("selected_scope", (intake.selected_scope,) if intake.selected_scope else ()),
        ("scope_candidates", intake.scope_candidates),
        ("dev", intake.dev_commands),
        ("build", intake.build_commands),
        ("source_roots", intake.source_roots),
        ("entrypoints", intake.entrypoints),
        ("docs", intake.docs_found),
    ):
        if values:
            parts.append(_format_project_intake_section(labels[label_key], values))
    return " | ".join(parts)


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


def _new_project_generation_validation(intake: ProjectIntake) -> tuple[str, ...]:
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


def _project_intake_analysis_is_sparse(intake: ProjectIntake) -> bool:
    if intake.mode != "existing":
        return False
    return not (
        intake.test_commands
        or intake.source_roots
        or intake.scope_candidates
        or intake.docs_found
    )


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
