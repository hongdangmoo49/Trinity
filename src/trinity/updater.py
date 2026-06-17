"""Startup update checks for the Trinity CLI.

The updater is intentionally conservative: source checkouts update from their
Git upstream with a fast-forward-only pull, while regular package installs
check PyPI and update through the current Python interpreter's pip.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


DEFAULT_CHECK_TIMEOUT_SECONDS = 4.0
DEFAULT_APPLY_TIMEOUT_SECONDS = 60.0
PYPI_PACKAGE_NAME = "trinity-agent"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE_NAME}/json"

_FALSE_VALUES = {"0", "false", "no", "off"}
_VERSION_RE = re.compile(r'(?m)^version\s*=\s*"([^"]+)"\s*$')
_VERSION_RELEASE_RE = re.compile(r"^\s*v?(\d+(?:\.\d+)*)")


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
    command: tuple[str, ...]
    repo_root: Path | None = None
    upstream: str = ""
    behind_count: int = 0


@dataclass(frozen=True)
class StartupUpdateResult:
    """Result of applying a startup update."""

    succeeded: bool
    message: str
    output: str = ""


CommandRunner = Callable[[Sequence[str], float], CommandResult]
PypiMetadataFetcher = Callable[[str, float], str]


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


def fetch_pypi_metadata(url: str, timeout: float) -> str:
    """Fetch PyPI JSON metadata with a short timeout."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "trinity-agent-update-check",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def check_for_startup_update(
    current_version: str,
    *,
    start_path: Path | None = None,
    runner: CommandRunner = run_command,
    pypi_fetcher: PypiMetadataFetcher = fetch_pypi_metadata,
    timeout: float = DEFAULT_CHECK_TIMEOUT_SECONDS,
) -> StartupUpdate | None:
    """Check whether a startup update is available.

    Source checkouts are updated from Git. Regular package installs do not have
    a Git worktree, so they fall back to PyPI version metadata.
    """
    start = (
        Path(start_path)
        if start_path is not None
        else Path(__file__).resolve().parent
    )
    repo_root = _detect_git_repo(start, runner, timeout)
    if repo_root is None:
        return _check_pypi_update(
            current_version,
            pypi_fetcher=pypi_fetcher,
            timeout=timeout,
        )

    return _check_git_upstream_update(
        current_version,
        repo_root,
        runner=runner,
        timeout=timeout,
    )


def _check_git_upstream_update(
    current_version: str,
    repo_root: Path,
    *,
    runner: CommandRunner,
    timeout: float,
) -> StartupUpdate | None:
    """Check whether the current Git upstream has updates available."""

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
        command=("git", "-C", str(repo_root), "pull", "--ff-only"),
        repo_root=repo_root,
        upstream=upstream_name,
        behind_count=behind_count,
    )


def _check_pypi_update(
    current_version: str,
    *,
    pypi_fetcher: PypiMetadataFetcher,
    timeout: float,
) -> StartupUpdate | None:
    """Check PyPI for a newer released package version."""
    try:
        metadata_text = pypi_fetcher(PYPI_JSON_URL, timeout)
    except (
        OSError,
        TimeoutError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        ValueError,
    ):
        return None

    latest_version = _parse_pypi_latest_version(metadata_text)
    if not latest_version or not _is_newer_version(latest_version, current_version):
        return None

    return StartupUpdate(
        source="pypi",
        current_version=current_version,
        latest_version=latest_version,
        detail=f"{PYPI_PACKAGE_NAME} {latest_version} is available on PyPI.",
        command=(
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            PYPI_PACKAGE_NAME,
        ),
    )


def apply_startup_update(
    update: StartupUpdate,
    *,
    runner: CommandRunner = run_command,
    timeout: float = DEFAULT_APPLY_TIMEOUT_SECONDS,
) -> StartupUpdateResult:
    """Apply an update candidate.

    Git fast-forward updates refuse dirty worktrees. PyPI updates run through
    the current Python interpreter's pip.
    """
    if update.source == "pypi":
        applied = runner(update.command, timeout)
        if applied.returncode != 0:
            return StartupUpdateResult(False, "Update failed.", applied.output)
        return StartupUpdateResult(True, "Update completed.", applied.output)

    if update.source != "git":
        return StartupUpdateResult(False, f"Unsupported update source: {update.source}")
    if update.repo_root is None:
        return StartupUpdateResult(False, "Missing Git repository for update.")

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


def _parse_pypi_latest_version(metadata_text: str) -> str:
    try:
        metadata = json.loads(metadata_text)
    except (TypeError, ValueError):
        return ""
    info = metadata.get("info") if isinstance(metadata, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    return str(version).strip() if version else ""


def _is_newer_version(candidate: str, current: str) -> bool:
    candidate_release = _parse_version_release(candidate)
    current_release = _parse_version_release(current)
    if candidate_release is None or current_release is None:
        return False

    candidate_parts, candidate_prerelease = candidate_release
    current_parts, current_prerelease = current_release
    width = max(len(candidate_parts), len(current_parts))
    padded_candidate = candidate_parts + (0,) * (width - len(candidate_parts))
    padded_current = current_parts + (0,) * (width - len(current_parts))
    if padded_candidate != padded_current:
        return padded_candidate > padded_current
    return current_prerelease and not candidate_prerelease


def _parse_version_release(version: str) -> tuple[tuple[int, ...], bool] | None:
    match = _VERSION_RELEASE_RE.match(version)
    if not match:
        return None
    release = tuple(int(part) for part in match.group(1).split("."))
    suffix = version[match.end() :].lower()
    is_prerelease = any(tag in suffix for tag in ("a", "b", "rc", "dev"))
    return release, is_prerelease


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
