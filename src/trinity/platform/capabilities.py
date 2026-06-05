"""Platform and terminal capability detection.

The functions in this module avoid provider-specific behavior. They provide a
small, testable surface that CLI, TUI, bootstrap, and doctor commands can share
when deciding how much terminal UI is appropriate.
"""

from __future__ import annotations

import os
import platform as py_platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Literal, Mapping

OSName = Literal["windows", "macos", "linux", "unknown"]
ColorSystem = Literal["truecolor", "256color", "standard", "none"]
RenderMode = Literal["modern", "unicode", "ascii", "plain"]


@dataclass(frozen=True)
class PlatformInfo:
    """Basic OS, shell, terminal, and execution-context facts."""

    os_name: OSName
    shell_name: str
    terminal_name: str
    is_tty: bool
    is_ci: bool

    @property
    def is_windows(self) -> bool:
        return self.os_name == "windows"

    @property
    def is_macos(self) -> bool:
        return self.os_name == "macos"

    @property
    def is_linux(self) -> bool:
        return self.os_name == "linux"


@dataclass(frozen=True)
class TerminalCapabilities:
    """Rendering capabilities for the active terminal."""

    color_system: ColorSystem
    supports_unicode: bool
    supports_emoji: bool
    supports_box_drawing: bool
    supports_live_render: bool
    width: int
    height: int

    @property
    def render_mode(self) -> RenderMode:
        """Choose the most expressive safe rendering profile."""
        if not self.supports_live_render or self.color_system == "none":
            return "plain"
        if self.supports_emoji and self.supports_box_drawing:
            return "modern"
        if self.supports_unicode:
            return "unicode"
        return "ascii"

    @property
    def is_narrow(self) -> bool:
        return self.width < 80

    @property
    def is_compact(self) -> bool:
        return 80 <= self.width < 110


def normalize_os_name(system: str | None = None) -> OSName:
    """Normalize `platform.system()` style names into Trinity OS buckets."""
    value = (system or py_platform.system() or "").strip().lower()
    if value.startswith(("win", "msys", "mingw", "cygwin")):
        return "windows"
    if value in {"darwin", "mac", "macos", "osx"}:
        return "macos"
    if value == "linux":
        return "linux"
    return "unknown"


def detect_platform_info(
    *,
    env: Mapping[str, str] | None = None,
    stdin_is_tty: bool | None = None,
    stdout_is_tty: bool | None = None,
    system: str | None = None,
) -> PlatformInfo:
    """Detect platform facts with overridable inputs for deterministic tests."""
    env_map = env or os.environ
    os_name = normalize_os_name(system)
    stdin_tty = sys.stdin.isatty() if stdin_is_tty is None else stdin_is_tty
    stdout_tty = sys.stdout.isatty() if stdout_is_tty is None else stdout_is_tty
    return PlatformInfo(
        os_name=os_name,
        shell_name=_detect_shell_name(env_map, os_name),
        terminal_name=_detect_terminal_name(env_map),
        is_tty=bool(stdin_tty and stdout_tty),
        is_ci=_detect_ci(env_map),
    )


def detect_terminal_capabilities(
    platform_info: PlatformInfo | None = None,
    *,
    env: Mapping[str, str] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> TerminalCapabilities:
    """Detect color, character, and live rendering support."""
    env_map = env or os.environ
    info = platform_info or detect_platform_info(env=env_map)
    size = shutil.get_terminal_size(fallback=(80, 24))
    term_width = width if width is not None else size.columns
    term_height = height if height is not None else size.lines

    color_system = _detect_color_system(env_map, info)
    supports_unicode = _supports_unicode(env_map, info)
    supports_emoji = supports_unicode and _supports_emoji(env_map, info)
    supports_box = supports_unicode and _supports_box_drawing(env_map, info)
    supports_live = (
        info.is_tty
        and not info.is_ci
        and _env_flag(env_map, "TERM") != "dumb"
        and term_width >= 40
    )

    return TerminalCapabilities(
        color_system=color_system,
        supports_unicode=supports_unicode,
        supports_emoji=supports_emoji,
        supports_box_drawing=supports_box,
        supports_live_render=supports_live,
        width=term_width,
        height=term_height,
    )


def has_command(command: str) -> bool:
    """Return whether an executable is available on PATH."""
    return shutil.which(command) is not None


def legacy_tmux_hint(
    platform_info: PlatformInfo | None = None,
    *,
    tmux_available: bool | None = None,
) -> str:
    """Return a short platform-specific hint for legacy tmux usage."""
    info = platform_info or detect_platform_info()
    available = has_command("tmux") if tmux_available is None else tmux_available
    if available:
        return "tmux is available for legacy/debug transport."
    if info.is_windows:
        return (
            "Legacy tmux transport is not available in a normal Windows shell. "
            "Use the default one-shot transport, or run tmux from WSL/MSYS if "
            "you explicitly need legacy debugging."
        )
    if info.is_macos:
        return (
            "Legacy tmux transport requires tmux. Install it separately only if "
            "you explicitly need legacy/debug transport."
        )
    if info.is_linux:
        return (
            "Legacy tmux transport requires tmux. Install it separately only if "
            "you explicitly need legacy/debug transport."
        )
    return "Legacy tmux transport requires tmux; use one-shot transport by default."


def _detect_shell_name(env: Mapping[str, str], os_name: OSName) -> str:
    if shell := env.get("SHELL"):
        return Path(shell).name or shell
    if comspec := env.get("COMSPEC"):
        comspec_path = PureWindowsPath(comspec) if os_name == "windows" else Path(comspec)
        return comspec_path.stem or comspec_path.name or comspec
    if os_name == "windows" and env.get("PSModulePath"):
        return "powershell"
    return "unknown"


def _detect_terminal_name(env: Mapping[str, str]) -> str:
    for key in ("TERM_PROGRAM", "WT_SESSION", "TERMINAL_EMULATOR", "TERM"):
        value = env.get(key)
        if value:
            if key == "WT_SESSION":
                return "Windows Terminal"
            return value
    return "unknown"


def _detect_ci(env: Mapping[str, str]) -> bool:
    ci_markers = (
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "BUILDKITE",
        "TF_BUILD",
        "TEAMCITY_VERSION",
    )
    return any(_env_truthy(env, key) for key in ci_markers)


def _detect_color_system(env: Mapping[str, str], info: PlatformInfo) -> ColorSystem:
    if _env_truthy(env, "NO_COLOR") or _env_flag(env, "TERM") == "dumb":
        return "none"
    if not info.is_tty:
        return "none"
    colorterm = _env_flag(env, "COLORTERM")
    term = _env_flag(env, "TERM")
    if colorterm in {"truecolor", "24bit"}:
        return "truecolor"
    if "256color" in term:
        return "256color"
    if term and term != "dumb":
        return "standard"
    if info.is_windows and env.get("WT_SESSION"):
        return "truecolor"
    return "standard" if info.is_tty else "none"


def _supports_unicode(env: Mapping[str, str], info: PlatformInfo) -> bool:
    if _env_truthy(env, "TRINITY_ASCII"):
        return False
    encoding = (
        env.get("PYTHONIOENCODING")
        or env.get("LC_ALL")
        or env.get("LC_CTYPE")
        or env.get("LANG")
        or ""
    ).lower()
    if "utf" in encoding:
        return True
    if info.is_windows:
        return bool(env.get("WT_SESSION") or env.get("ConEmuANSI") == "ON")
    return True


def _supports_emoji(env: Mapping[str, str], info: PlatformInfo) -> bool:
    if _env_truthy(env, "TRINITY_NO_EMOJI"):
        return False
    if _env_truthy(env, "TRINITY_EMOJI"):
        return True
    if info.is_ci or _env_flag(env, "TERM") == "dumb":
        return False
    if info.is_windows:
        return bool(env.get("WT_SESSION"))
    return True


def _supports_box_drawing(env: Mapping[str, str], info: PlatformInfo) -> bool:
    if _env_truthy(env, "TRINITY_ASCII"):
        return False
    if info.is_ci or _env_flag(env, "TERM") == "dumb":
        return False
    return True


def _env_truthy(env: Mapping[str, str], key: str) -> bool:
    value = env.get(key)
    return value is not None and value.strip().lower() not in {"", "0", "false", "no"}


def _env_flag(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip().lower()
