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
        "invalid": "Project intake: could not read",
        "missing": "Project intake: not recorded",
        "summary": "Project intake: {mode} | tests: {tests}",
        "tests_none": "(none)",
    },
    "ko": {
        "invalid": "프로젝트 인테이크: 읽을 수 없음",
        "missing": "프로젝트 인테이크: 기록 없음",
        "summary": "프로젝트 인테이크: {mode} | 테스트: {tests}",
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
    tests = (
        ", ".join(intake.test_commands)
        if intake.test_commands
        else labels["tests_none"]
    )
    return labels["summary"].format(mode=mode, tests=tests)


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()
