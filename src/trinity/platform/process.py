"""Cross-platform subprocess execution helpers."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from trinity.platform.capabilities import OSName, normalize_os_name


@dataclass(frozen=True)
class CommandSpec:
    """A command execution contract independent from shell syntax."""

    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.argv:
            raise ValueError("CommandSpec.argv must not be empty")
        object.__setattr__(self, "cwd", Path(self.cwd))


class ProcessRunner:
    """Run commands using argv/env/cwd instead of shell strings."""

    def run(self, command: CommandSpec) -> subprocess.CompletedProcess[str]:
        """Run a command and capture text output."""
        self._validate_cwd(command.cwd)
        return subprocess.run(
            list(command.argv),
            cwd=command.cwd,
            env=self._merged_env(command.env),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=command.timeout_seconds,
        )

    def stream_interactive(self, command: CommandSpec) -> int:
        """Run a command connected to the current terminal."""
        self._validate_cwd(command.cwd)
        completed = subprocess.run(
            list(command.argv),
            cwd=command.cwd,
            env=self._merged_env(command.env),
            timeout=command.timeout_seconds,
        )
        return completed.returncode

    @staticmethod
    def _merged_env(overrides: Mapping[str, str]) -> dict[str, str] | None:
        if not overrides:
            return None
        env = os.environ.copy()
        env.update({key: str(value) for key, value in overrides.items()})
        return env

    @staticmethod
    def _validate_cwd(cwd: Path) -> None:
        if not cwd.exists():
            raise FileNotFoundError(f"Command cwd does not exist: {cwd}")
        if not cwd.is_dir():
            raise NotADirectoryError(f"Command cwd is not a directory: {cwd}")


def render_command(
    argv: Sequence[str],
    *,
    os_name: OSName | str | None = None,
) -> str:
    """Render argv for display only; never feed this string back to subprocess."""
    normalized = normalize_os_name(os_name)
    if normalized == "windows":
        return subprocess.list2cmdline([str(arg) for arg in argv])
    return shlex.join(str(arg) for arg in argv)
