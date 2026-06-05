"""Cross-platform runtime capability helpers."""

from trinity.platform.capabilities import (
    ColorSystem,
    OSName,
    PlatformInfo,
    RenderMode,
    TerminalCapabilities,
    detect_platform_info,
    detect_terminal_capabilities,
    has_command,
    legacy_tmux_hint,
    normalize_os_name,
)
from trinity.platform.log_tail import LogTailEvent, follow_log
from trinity.platform.process import CommandSpec, ProcessRunner, render_command

__all__ = [
    "ColorSystem",
    "OSName",
    "PlatformInfo",
    "RenderMode",
    "TerminalCapabilities",
    "detect_platform_info",
    "detect_terminal_capabilities",
    "has_command",
    "legacy_tmux_hint",
    "normalize_os_name",
    "LogTailEvent",
    "follow_log",
    "CommandSpec",
    "ProcessRunner",
    "render_command",
]
