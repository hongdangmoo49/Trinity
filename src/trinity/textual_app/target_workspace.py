"""Pure helpers for Textual target workspace handling."""

from __future__ import annotations

from pathlib import Path


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


def absolute_path(path: Path) -> Path:
    """Best-effort absolute path that tolerates non-existing or invalid paths."""
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return path.expanduser().absolute()
