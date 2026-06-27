"""Pure helpers for Textual target workspace handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

TargetWorkspacePrepareError = Literal["not_directory", "os_error"]


@dataclass(frozen=True)
class TargetWorkspacePreparation:
    """Result of preparing a target workspace path for use."""

    resolved_path: Path | None = None
    error: TargetWorkspacePrepareError | None = None
    message: str = ""


@dataclass(frozen=True)
class WorkspacePreflightContinuation:
    """Controller action to run after workspace preflight is confirmed."""

    preflight: Any
    control_repo_confirmed: bool
    retry_selector: str = ""
    retry_package_ids: tuple[str, ...] = ()

    @property
    def use_retry(self) -> bool:
        """Return whether execution retry should be confirmed instead of fresh execution."""
        return bool(self.retry_selector)


@dataclass(frozen=True)
class WorkspacePreflightEffect:
    """UI effects derived from a workspace preflight execution outcome."""

    execution_recovery_snapshot: Any | None = None
    execution_recovery_message: str = ""
    execution_preflight: Any | None = None
    execution_snapshot: Any | None = None

    @property
    def show_execution(self) -> bool:
        """Return whether the execution route should be shown."""
        return self.execution_snapshot is not None


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


def workspace_preflight_continuation(
    preflight: Any,
    *,
    control_repo_confirmed: bool,
    pending_retry: Any | None = None,
) -> WorkspacePreflightContinuation:
    """Return the controller action to run after workspace preflight succeeds."""
    if pending_retry is None:
        return WorkspacePreflightContinuation(
            preflight=preflight,
            control_repo_confirmed=control_repo_confirmed,
        )
    return WorkspacePreflightContinuation(
        preflight=preflight,
        control_repo_confirmed=control_repo_confirmed,
        retry_selector=str(pending_retry.selector),
        retry_package_ids=tuple(pending_retry.package_ids),
    )


def workspace_preflight_effect(
    preflight: Any,
    outcome: Any,
) -> WorkspacePreflightEffect:
    """Return the UI effects after continuing execution from preflight."""
    if getattr(outcome, "execution_recovery_required", False):
        return WorkspacePreflightEffect(
            execution_recovery_snapshot=outcome.snapshot,
            execution_recovery_message=getattr(outcome, "message", ""),
        )
    return WorkspacePreflightEffect(
        execution_preflight=preflight,
        execution_snapshot=outcome.snapshot,
    )


def absolute_path(path: Path) -> Path:
    """Best-effort absolute path that tolerates non-existing or invalid paths."""
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return path.expanduser().absolute()
