"""Shared Textual labels for target workspace state."""

from __future__ import annotations

from pathlib import Path

from trinity.project_intake import (
    ProjectIntake,
    load_project_intake,
    missing_new_project_brief_field_keys,
)


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
        "goal": "goal",
        "constraints": "constraints",
        "first_milestone": "milestone",
        "project_type": "type",
        "source_roots": "src",
        "stack_preferences": "stack",
        "success_criteria": "success",
        "summary": "Project intake: {mode}",
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
        "goal": "목표",
        "constraints": "제약",
        "first_milestone": "마일스톤",
        "project_type": "유형",
        "source_roots": "소스",
        "stack_preferences": "스택",
        "success_criteria": "성공",
        "summary": "프로젝트 인테이크: {mode}",
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
    return _format_project_intake_label(
        intake,
        lang=lang,
        target_workspace=target_workspace,
    )


def _format_project_intake_label(
    intake: ProjectIntake,
    *,
    lang: str,
    target_workspace: object | None = None,
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
    updated = _format_project_intake_timestamp(intake.created_at)
    if updated:
        parts.append(f"{labels['updated']}: {updated}")
    parts.append(
        _format_project_intake_section(
            labels["tests"],
            intake.test_commands,
            empty_label=labels["tests_none"],
        )
    )
    if intake.mode == "new":
        parts.append(_format_new_project_brief_readiness(intake, labels))
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


def _format_optional_count(value: int | None) -> str:
    return str(value) if value is not None else "unknown"


def _format_project_intake_section(
    label: str,
    values: tuple[str, ...],
    *,
    empty_label: str = "",
) -> str:
    return f"{label}: {_format_project_intake_values(values, empty_label=empty_label)}"


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
    if _same_resolved_path(Path(target_text), intake.target_workspace):
        return ""
    intake_target = _format_project_intake_target(intake.target_workspace)
    return labels["target_mismatch"].format(target=intake_target)


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()
