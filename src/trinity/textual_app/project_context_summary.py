"""Project context summaries for pre-action confirmation surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trinity.project_intake import (
    ProjectIntake,
    load_project_intake,
    missing_new_project_brief_fields,
    project_intake_read_first_confirmation_needed,
    project_intake_validation_commands,
)


PROJECT_CONTEXT_LABELS = {
    "en": {
        "brief": "brief",
        "brief_complete": "complete",
        "brief_missing": "missing {fields}",
        "confirmed": "confirmed",
        "existing": "existing",
        "intake": "intake",
        "mismatch": "target mismatch",
        "missing": "missing",
        "new": "new",
        "not_recorded": "not recorded",
        "not_required": "not required",
        "read": "read",
        "read_first": "read-first",
        "scope": "scope",
        "starter": "starter",
        "target_root": "target root",
        "unreadable": "unreadable",
        "validation": "validation",
    },
    "ko": {
        "brief": "브리프",
        "brief_complete": "완료",
        "brief_missing": "누락 {fields}",
        "confirmed": "확인됨",
        "existing": "기존",
        "intake": "인테이크",
        "mismatch": "대상 불일치",
        "missing": "없음",
        "new": "신규",
        "not_recorded": "기록 없음",
        "not_required": "필요 없음",
        "read": "읽기",
        "read_first": "먼저 읽기",
        "scope": "범위",
        "starter": "스타터",
        "target_root": "대상 루트",
        "unreadable": "읽기 실패",
        "validation": "검증",
    },
}


@dataclass(frozen=True)
class ProjectContextSummary:
    """Compact project context displayed before agents plan or execute."""

    project_mode: str
    items: tuple[str, ...]


def build_project_context_summary(
    state_dir: Path,
    target_workspace: object | None,
    *,
    lang: str = "en",
) -> ProjectContextSummary:
    """Return project-intake context for a selected target workspace."""
    labels = PROJECT_CONTEXT_LABELS.get(lang, PROJECT_CONTEXT_LABELS["en"])
    target = _target_path(target_workspace)
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return ProjectContextSummary(
            project_mode=labels["unreadable"],
            items=(f"{labels['intake']}: {labels['unreadable']}",),
        )
    if intake is None:
        return ProjectContextSummary(
            project_mode=labels["not_recorded"],
            items=(f"{labels['intake']}: {labels['not_recorded']}",),
        )
    if target is not None and not _same_path(intake.target_workspace, target):
        return ProjectContextSummary(
            project_mode=labels["mismatch"],
            items=(
                f"{labels['intake']}: {labels['mismatch']}",
                f"{labels['scope']}: {labels['target_root']}",
            ),
        )
    if intake.mode == "new":
        return ProjectContextSummary(
            project_mode=labels["new"],
            items=_new_project_context_items(intake, labels),
        )
    return ProjectContextSummary(
        project_mode=labels["existing"],
        items=_existing_project_context_items(intake, labels),
    )


def _new_project_context_items(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    starter = intake.starter_profile.strip() or labels["missing"]
    missing_fields = missing_new_project_brief_fields(intake)
    if missing_fields:
        brief = labels["brief_missing"].format(fields=_format_values(missing_fields))
    else:
        brief = labels["brief_complete"]
    return (
        f"{labels['starter']}: {starter}",
        f"{labels['brief']}: {brief}",
        _validation_context_item(intake, labels),
    )


def _existing_project_context_items(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> tuple[str, ...]:
    scope = intake.selected_scope.strip() or labels["target_root"]
    if project_intake_read_first_confirmation_needed(intake):
        read_first = labels["missing"]
    elif intake.read_first_confirmed:
        read_first = labels["confirmed"]
    else:
        read_first = labels["not_required"]
    return (
        f"{labels['scope']}: {scope}",
        _read_anchor_context_item(intake, labels),
        f"{labels['read_first']}: {read_first}",
        _validation_context_item(intake, labels),
    )


def _read_anchor_context_item(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    anchors = tuple(
        dict.fromkeys((*intake.docs_found, *intake.source_roots, *intake.entrypoints))
    )
    value = _format_values(anchors) if anchors else labels["missing"]
    return f"{labels['read']}: {value}"


def _validation_context_item(
    intake: ProjectIntake,
    labels: dict[str, str],
) -> str:
    commands = project_intake_validation_commands(intake)
    value = _format_values(commands) if commands else labels["missing"]
    return f"{labels['validation']}: {value}"


def _target_path(target_workspace: object | None) -> Path | None:
    text = str(target_workspace or "").strip()
    return Path(text) if text else None


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser().absolute() == right.expanduser().absolute()


def _format_values(values: tuple[str, ...] | list[str], *, max_items: int = 2) -> str:
    cleaned = tuple(str(value).strip() for value in values if str(value).strip())
    if not cleaned:
        return ""
    visible = cleaned[:max_items]
    suffix = f", +{len(cleaned) - max_items}" if len(cleaned) > max_items else ""
    return ", ".join(visible) + suffix
