"""Pure helpers for project diagnostic slash-command presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from trinity.textual_app.workspace_labels import (
    project_existing_diagnostic_label,
    project_generation_preview_label,
    project_intake_state_label,
    project_mode_rail_label,
    project_plan_preview_label,
    project_read_first_checklist_label,
    project_start_choice_guide_label,
    project_startup_readiness_label,
    project_validation_plan_label,
)


@dataclass(frozen=True)
class ProjectCommandPresentation:
    """Prepared local `/project` command result."""

    title: str
    body: str
    severity: str = "info"
    action_hint: str = ""


def project_command_presentation(
    state_dir: Path,
    agents: Mapping[str, object],
    *,
    selected_agents: Sequence[str] | None = None,
    lang: str = "en",
    target_workspace: object | None = None,
) -> ProjectCommandPresentation:
    """Return the project startup/intake diagnostics as a local command result."""
    title = "프로젝트 진단" if lang == "ko" else "Project Diagnostics"
    target_label = "대상 워크스페이스" if lang == "ko" else "Target workspace"
    missing_target = "선택 안 됨" if lang == "ko" else "not selected"
    lines = [
        f"{target_label}: {str(target_workspace or '').strip() or missing_target}",
        project_startup_readiness_label(
            state_dir,
            agents,
            selected_agents=selected_agents,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_intake_state_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_existing_diagnostic_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_start_choice_guide_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_mode_rail_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_plan_preview_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_generation_preview_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_validation_plan_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
        project_read_first_checklist_label(
            state_dir,
            lang=lang,
            target_workspace=target_workspace,
        ),
    ]
    body = "\n".join(f"- {line}" for line in lines if line.strip())
    action_hint = (
        "시작/Nexus 화면의 긴 프로젝트 진단은 /project에서 확인합니다."
        if lang == "ko"
        else "Long Start/Nexus project diagnostics are available from /project."
    )
    return ProjectCommandPresentation(
        title=title,
        body=body,
        action_hint=action_hint,
    )
