"""Pure project-start decisions shared by Start and Nexus screens."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from trinity.project_intake import (
    ProjectIntake,
    load_project_intake,
    missing_new_project_brief_field_keys,
)


ProjectStartNextAction = Literal[
    "workspace",
    "analyze",
    "create",
    "brief",
    "plan",
    "execute",
]
ProjectStartReadyAction = Literal["plan", "execute"]


def project_setup_next_action(
    state_dir: Path,
    target_workspace: object | None,
    *,
    ready_action: ProjectStartReadyAction,
    analyze_variant: str = "default",
) -> ProjectStartNextAction:
    """Return the next safe setup action for a new/existing project journey."""
    target = project_start_target_path(target_workspace)
    if target is None:
        return "workspace"
    try:
        intake = load_project_intake(state_dir)
    except ValueError:
        return "analyze"
    if intake is None or not project_intake_matches_workspace(intake, target):
        return "analyze"
    if intake.mode == "new":
        if project_intake_target_missing(intake):
            return "create"
        if missing_new_project_brief_field_keys(intake):
            return "brief"
        return ready_action
    if analyze_variant == "warning":
        return "analyze"
    if intake.scope_candidates and not intake.selected_scope.strip():
        return "analyze"
    return ready_action


def project_start_target_path(target_workspace: object | None) -> Path | None:
    """Normalize screen target state into a path or no target."""
    text = str(target_workspace or "").strip()
    if not text:
        return None
    return Path(text)


def project_intake_matches_workspace(
    intake: ProjectIntake,
    target_workspace: object | None,
) -> bool:
    """Return whether saved intake belongs to the current target workspace."""
    target = project_start_target_path(target_workspace)
    if target is None:
        return True
    try:
        return target.expanduser().resolve() == intake.target_workspace.expanduser().resolve()
    except OSError:
        return (
            target.expanduser().absolute()
            == intake.target_workspace.expanduser().absolute()
        )


def project_intake_target_missing(intake: ProjectIntake) -> bool:
    """Return whether a saved intake target can no longer be found."""
    try:
        return not intake.target_workspace.exists()
    except OSError:
        return True
