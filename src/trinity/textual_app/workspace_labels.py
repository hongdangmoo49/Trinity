"""Shared Textual labels for target workspace state."""

from __future__ import annotations

from pathlib import Path

from trinity.project_intake import ProjectIntake, load_project_intake


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
        "build": "build",
        "dev": "dev",
        "docs": "docs",
        "entrypoints": "entry",
        "summary": "Project intake: {mode}",
        "tests": "tests",
        "tests_none": "(none)",
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
        "build": "빌드",
        "dev": "개발",
        "docs": "문서",
        "entrypoints": "진입점",
        "summary": "프로젝트 인테이크: {mode}",
        "tests": "테스트",
        "tests_none": "(없음)",
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
) -> str:
    """Return a concise label for the saved project intake state."""
    labels = PROJECT_INTAKE_LABELS.get(lang, PROJECT_INTAKE_LABELS["en"])
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return labels["invalid"]
    if intake is None:
        return labels["missing"]
    return _format_project_intake_label(intake, lang=lang)


def _format_project_intake_label(intake: ProjectIntake, *, lang: str) -> str:
    labels = PROJECT_INTAKE_LABELS.get(lang, PROJECT_INTAKE_LABELS["en"])
    mode_labels = PROJECT_MODE_LABELS.get(lang, PROJECT_MODE_LABELS["en"])
    mode = mode_labels.get(intake.mode, intake.mode)
    parts = [
        labels["summary"].format(mode=mode),
        _format_project_intake_section(
            labels["tests"],
            intake.test_commands,
            empty_label=labels["tests_none"],
        ),
    ]
    for label_key, values in (
        ("dev", intake.dev_commands),
        ("build", intake.build_commands),
        ("entrypoints", intake.entrypoints),
        ("docs", intake.docs_found),
    ):
        if values:
            parts.append(_format_project_intake_section(labels[label_key], values))
    return " | ".join(parts)


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


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()
