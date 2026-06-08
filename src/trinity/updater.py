"""Startup update checks for the Trinity CLI.

The updater is intentionally conservative: it detects whether the running
package belongs to a Git worktree with an upstream branch, checks whether that
branch has new commits, and applies updates with a fast-forward-only pull.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


DEFAULT_CHECK_TIMEOUT_SECONDS = 4.0
DEFAULT_APPLY_TIMEOUT_SECONDS = 60.0

_FALSE_VALUES = {"0", "false", "no", "off"}
_VERSION_RE = re.compile(r'(?m)^version\s*=\s*"([^"]+)"\s*$')


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result used by the updater."""

    returncode: int
    stdout: str = ""
    stderr: str = ""

    @property
    def output(self) -> str:
        """Return stdout/stderr combined for user-facing diagnostics."""
        return "\n".join(
            part for part in (self.stdout.strip(), self.stderr.strip()) if part
        )


@dataclass(frozen=True)
class StartupUpdate:
    """A detected startup update candidate."""

    source: str
    current_version: str
    latest_version: str
    detail: str
    repo_root: Path
    upstream: str
    behind_count: int
    command: tuple[str, ...]


@dataclass(frozen=True)
class StartupUpdateResult:
    """Result of applying a startup update."""

    succeeded: bool
    message: str
    output: str = ""


CommandRunner = Callable[[Sequence[str], float], CommandResult]


def startup_update_check_disabled(env: dict[str, str] | None = None) -> bool:
    """Return True when startup update checks are disabled by environment."""
    source = os.environ if env is None else env

    skip_value = source.get("TRINITY_SKIP_UPDATE_CHECK")
    if skip_value is not None and skip_value.strip().lower() not in _FALSE_VALUES:
        return True

    check_value = source.get("TRINITY_UPDATE_CHECK")
    if check_value is not None:
        return check_value.strip().lower() in _FALSE_VALUES

    return False


def run_command(args: Sequence[str], timeout: float) -> CommandResult:
    """Run a command with captured text output and timeout protection."""
    try:
        completed = subprocess.run(
            list(args),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return CommandResult(127, stderr=str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = _coerce_timeout_output(exc.stdout)
        stderr = _coerce_timeout_output(exc.stderr)
        return CommandResult(
            124,
            stdout=stdout,
            stderr=(stderr + "\nCommand timed out.").strip(),
        )
    except OSError as exc:
        return CommandResult(1, stderr=str(exc))

    return CommandResult(
        completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def check_for_startup_update(
    current_version: str,
    *,
    start_path: Path | None = None,
    runner: CommandRunner = run_command,
    timeout: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
) -> StartupUpdate | None:
    """Check whether the current Git upstream has updates available.

    Returns None when the package is not in a Git worktree, has no upstream,
    cannot reach the remote quickly, or is already up to date.
    """
    start = (
        Path(start_path)
        if start_path is not None
        else Path(__file__).resolve().parent
    )
    repo_root = _detect_git_repo(start, runner, timeout)
    if repo_root is None:
        return None

    upstream = _git(
        repo_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        runner=runner,
        timeout=timeout,
    )
    if upstream.returncode != 0:
        return None

    upstream_name = upstream.stdout.strip()
    if not upstream_name:
        return None

    remote_name = upstream_name.split("/", 1)[0] if "/" in upstream_name else "origin"
    fetch = _git(
        repo_root,
        "fetch",
        "--quiet",
        "--tags",
        "--prune",
        remote_name,
        runner=runner,
        timeout=timeout,
    )
    if fetch.returncode != 0:
        return None

    behind = _git(
        repo_root,
        "rev-list",
        "--count",
        "HEAD..@{u}",
        runner=runner,
        timeout=timeout,
    )
    if behind.returncode != 0:
        return None

    behind_count = _parse_positive_int(behind.stdout)
    if behind_count <= 0:
        return None

    latest_version = _read_upstream_version(
        repo_root,
        current_version,
        upstream_name,
        behind_count,
        runner=runner,
        timeout=timeout,
    )
    commit_label = "commit" if behind_count == 1 else "commits"
    detail = f"{upstream_name} has {behind_count} new {commit_label}."

    return StartupUpdate(
        source="git",
        current_version=current_version,
        latest_version=latest_version,
        detail=detail,
        repo_root=repo_root,
        upstream=upstream_name,
        behind_count=behind_count,
        command=("git", "-C", str(repo_root), "pull", "--ff-only"),
    )


def apply_startup_update(
    update: StartupUpdate,
    *,
    runner: CommandRunner = run_command,
    timeout: float = DEFAULT_APPLY_TIMEOUT_SECONDS,
) -> StartupUpdateResult:
    """Apply an update candidate.

    Only Git fast-forward updates are supported. Dirty worktrees are refused so
    startup never hides or overwrites local work.
    """
    if update.source != "git":
        return StartupUpdateResult(False, f"Unsupported update source: {update.source}")

    dirty = _git(
        update.repo_root,
        "status",
        "--porcelain",
        runner=runner,
        timeout=DEFAULT_CHECK_TIMEOUT_SECONDS,
    )
    if dirty.returncode != 0:
        return StartupUpdateResult(
            False,
            "Could not inspect the Git worktree before updating.",
            dirty.output,
        )
    if dirty.stdout.strip():
        return StartupUpdateResult(
            False,
            "The Git worktree has local changes. "
            "Commit, stash, or discard them before updating.",
            dirty.stdout.strip(),
        )

    applied = runner(update.command, timeout)
    if applied.returncode != 0:
        return StartupUpdateResult(False, "Update failed.", applied.output)

    return StartupUpdateResult(True, "Update completed.", applied.output)


def _detect_git_repo(
    start_path: Path,
    runner: CommandRunner,
    timeout: float,
) -> Path | None:
    result = runner(
        ("git", "-C", str(start_path), "rev-parse", "--show-toplevel"),
        timeout,
    )
    if result.returncode != 0:
        return None

    repo_text = result.stdout.strip()
    if not repo_text:
        return None
    return Path(repo_text)


def _git(
    repo_root: Path,
    *args: str,
    runner: CommandRunner,
    timeout: float,
) -> CommandResult:
    return runner(("git", "-C", str(repo_root), *args), timeout)


def _read_upstream_version(
    repo_root: Path,
    current_version: str,
    upstream: str,
    behind_count: int,
    *,
    runner: CommandRunner,
    timeout: float,
) -> str:
    result = _git(
        repo_root,
        "show",
        f"{upstream}:pyproject.toml",
        runner=runner,
        timeout=timeout,
    )
    version = _parse_project_version(result.stdout) if result.returncode == 0 else ""
    if not version:
        return f"{upstream} (+{behind_count})"
    if version == current_version:
        return f"{version} (+{behind_count})"
    return version


def _parse_project_version(pyproject_text: str) -> str:
    match = _VERSION_RE.search(pyproject_text)
    return match.group(1).strip() if match else ""


def _parse_positive_int(value: str) -> int:
    try:
        return max(0, int(value.strip()))
    except ValueError:
        return 0


def _coerce_timeout_output(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    if isinstance(value, str):
        return value
    return ""
