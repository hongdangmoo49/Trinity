"""Pure helpers for Textual target workspace handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TargetWorkspacePrepareError = Literal["not_directory", "os_error"]


@dataclass(frozen=True)
class TargetWorkspacePreparation:
    """Result of preparing a target workspace path for use."""

    resolved_path: Path | None = None
    error: TargetWorkspacePrepareError | None = None
    message: str = ""


def default_launch_cwd(launch_cwd: Path | None = None) -> Path:
    """Return the directory Trinity was launched from for target defaults."""
    try:
        return (launch_cwd or Path.cwd()).expanduser().resolve()
    except OSError:
        return (launch_cwd or Path.cwd()).expanduser()


def resolve_target_path(value: str, base_dir: Path) -> Path:
    """Resolve a user-provided target path against the control project."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path


def is_control_repo_target(path: Path, control_repo: Path) -> bool:
    """Return whether a target path points inside the Trinity control repo."""
    target = absolute_path(path)
    control = absolute_path(control_repo)
    return target == control or control in target.parents


def safe_start_target_workspace(path: Path | None, control_repo: Path) -> Path | None:
    """Return a start-screen target that can be persisted without confirmation."""
    if path is None:
        return None
    if is_control_repo_target(path, control_repo):
        return None
    return path


def prepare_target_workspace(path: Path) -> TargetWorkspacePreparation:
    """Create and resolve a target workspace directory if possible."""
    try:
        if path.exists() and not path.is_dir():
            return TargetWorkspacePreparation(
                error="not_directory",
                message=str(path),
            )
        path.mkdir(parents=True, exist_ok=True)
        return TargetWorkspacePreparation(resolved_path=path.resolve())
    except OSError as exc:
        return TargetWorkspacePreparation(error="os_error", message=str(exc))


def absolute_path(path: Path) -> Path:
    """Best-effort absolute path that tolerates non-existing or invalid paths."""
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return path.expanduser().absolute()
