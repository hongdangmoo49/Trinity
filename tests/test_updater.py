"""Tests for Trinity startup update detection."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from trinity.updater import (
    CommandResult,
    StartupUpdate,
    apply_startup_update,
    check_for_startup_update,
    startup_update_check_disabled,
)


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], CommandResult]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: Sequence[str], timeout: float) -> CommandResult:
        key = tuple(args)
        self.calls.append(key)
        return self.responses.get(key, CommandResult(99, stderr=f"unexpected: {key}"))


def test_startup_update_check_disabled_env() -> None:
    assert startup_update_check_disabled({"TRINITY_SKIP_UPDATE_CHECK": "1"})
    assert startup_update_check_disabled({"TRINITY_UPDATE_CHECK": "0"})
    assert not startup_update_check_disabled({"TRINITY_SKIP_UPDATE_CHECK": "0"})
    assert not startup_update_check_disabled({"TRINITY_UPDATE_CHECK": "1"})


def test_check_for_startup_update_detects_git_upstream(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    start = repo / "src" / "trinity"
    start.mkdir(parents=True)

    runner = FakeRunner(
        {
            ("git", "-C", str(start), "rev-parse", "--show-toplevel"): CommandResult(
                0,
                stdout=f"{repo}\n",
            ),
            (
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{u}",
            ): CommandResult(0, stdout="origin/main\n"),
            (
                "git",
                "-C",
                str(repo),
                "fetch",
                "--quiet",
                "--tags",
                "--prune",
                "origin",
            ): CommandResult(0),
            (
                "git",
                "-C",
                str(repo),
                "rev-list",
                "--count",
                "HEAD..@{u}",
            ): CommandResult(0, stdout="2\n"),
            (
                "git",
                "-C",
                str(repo),
                "show",
                "origin/main:pyproject.toml",
            ): CommandResult(0, stdout='[project]\nversion = "0.12.0"\n'),
        }
    )

    update = check_for_startup_update("0.11.1", start_path=start, runner=runner)

    assert update is not None
    assert update.latest_version == "0.12.0"
    assert update.behind_count == 2
    assert update.command == ("git", "-C", str(repo), "pull", "--ff-only")


def test_check_for_startup_update_returns_none_when_current_branch_is_up_to_date(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    start = repo / "src" / "trinity"
    start.mkdir(parents=True)

    runner = FakeRunner(
        {
            ("git", "-C", str(start), "rev-parse", "--show-toplevel"): CommandResult(
                0,
                stdout=f"{repo}\n",
            ),
            (
                "git",
                "-C",
                str(repo),
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{u}",
            ): CommandResult(0, stdout="origin/main\n"),
            (
                "git",
                "-C",
                str(repo),
                "fetch",
                "--quiet",
                "--tags",
                "--prune",
                "origin",
            ): CommandResult(0),
            (
                "git",
                "-C",
                str(repo),
                "rev-list",
                "--count",
                "HEAD..@{u}",
            ): CommandResult(0, stdout="0\n"),
        }
    )

    assert check_for_startup_update("0.11.1", start_path=start, runner=runner) is None


def test_apply_startup_update_refuses_dirty_worktree(tmp_path: Path) -> None:
    update = StartupUpdate(
        source="git",
        current_version="0.11.1",
        latest_version="0.11.2",
        detail="origin/main has 1 new commit.",
        repo_root=tmp_path,
        upstream="origin/main",
        behind_count=1,
        command=("git", "-C", str(tmp_path), "pull", "--ff-only"),
    )
    runner = FakeRunner(
        {
            (
                "git",
                "-C",
                str(tmp_path),
                "status",
                "--porcelain",
            ): CommandResult(0, stdout=" M src/trinity/cli.py\n"),
        }
    )

    result = apply_startup_update(update, runner=runner)

    assert result.succeeded is False
    assert "local changes" in result.message
    assert update.command not in runner.calls


def test_apply_startup_update_runs_fast_forward_pull(tmp_path: Path) -> None:
    update = StartupUpdate(
        source="git",
        current_version="0.11.1",
        latest_version="0.11.2",
        detail="origin/main has 1 new commit.",
        repo_root=tmp_path,
        upstream="origin/main",
        behind_count=1,
        command=("git", "-C", str(tmp_path), "pull", "--ff-only"),
    )
    runner = FakeRunner(
        {
            (
                "git",
                "-C",
                str(tmp_path),
                "status",
                "--porcelain",
            ): CommandResult(0),
            update.command: CommandResult(0, stdout="Fast-forward\n"),
        }
    )

    result = apply_startup_update(update, runner=runner)

    assert result.succeeded is True
    assert update.command in runner.calls
