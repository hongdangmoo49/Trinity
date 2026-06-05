"""Tests for platform and terminal capability detection."""

from trinity.platform.capabilities import (
    PlatformInfo,
    detect_platform_info,
    detect_terminal_capabilities,
    legacy_tmux_hint,
    normalize_os_name,
)


def test_normalize_os_name_known_values():
    assert normalize_os_name("Windows") == "windows"
    assert normalize_os_name("Darwin") == "macos"
    assert normalize_os_name("Linux") == "linux"
    assert normalize_os_name("Solaris") == "unknown"


def test_detect_platform_info_windows_terminal():
    info = detect_platform_info(
        env={"COMSPEC": r"C:\Windows\System32\cmd.exe", "WT_SESSION": "abc"},
        stdin_is_tty=True,
        stdout_is_tty=True,
        system="Windows",
    )

    assert info.os_name == "windows"
    assert info.shell_name == "cmd"
    assert info.terminal_name == "Windows Terminal"
    assert info.is_tty is True
    assert info.is_ci is False


def test_detect_platform_info_ci_not_tty():
    info = detect_platform_info(
        env={"SHELL": "/bin/bash", "TERM": "xterm-256color", "CI": "true"},
        stdin_is_tty=True,
        stdout_is_tty=False,
        system="Linux",
    )

    assert info.os_name == "linux"
    assert info.shell_name == "bash"
    assert info.terminal_name == "xterm-256color"
    assert info.is_tty is False
    assert info.is_ci is True


def test_terminal_capabilities_modern_profile():
    info = PlatformInfo(
        os_name="macos",
        shell_name="zsh",
        terminal_name="Apple_Terminal",
        is_tty=True,
        is_ci=False,
    )

    caps = detect_terminal_capabilities(
        info,
        env={"TERM": "xterm-256color", "COLORTERM": "truecolor", "LANG": "en_US.UTF-8"},
        width=120,
        height=40,
    )

    assert caps.color_system == "truecolor"
    assert caps.supports_unicode is True
    assert caps.supports_emoji is True
    assert caps.supports_box_drawing is True
    assert caps.supports_live_render is True
    assert caps.render_mode == "modern"
    assert caps.is_narrow is False


def test_terminal_capabilities_plain_for_ci_dumb_terminal():
    info = PlatformInfo(
        os_name="linux",
        shell_name="bash",
        terminal_name="dumb",
        is_tty=True,
        is_ci=True,
    )

    caps = detect_terminal_capabilities(
        info,
        env={"TERM": "dumb", "CI": "true", "LANG": "en_US.UTF-8"},
        width=100,
        height=24,
    )

    assert caps.color_system == "none"
    assert caps.supports_unicode is True
    assert caps.supports_emoji is False
    assert caps.supports_box_drawing is False
    assert caps.supports_live_render is False
    assert caps.render_mode == "plain"


def test_terminal_capabilities_ascii_override():
    info = PlatformInfo(
        os_name="windows",
        shell_name="powershell",
        terminal_name="Windows Terminal",
        is_tty=True,
        is_ci=False,
    )

    caps = detect_terminal_capabilities(
        info,
        env={"WT_SESSION": "abc", "TERM": "xterm-256color", "TRINITY_ASCII": "1"},
        width=72,
        height=24,
    )

    assert caps.supports_unicode is False
    assert caps.supports_emoji is False
    assert caps.supports_box_drawing is False
    assert caps.render_mode == "ascii"
    assert caps.is_narrow is True


def test_legacy_tmux_hint_windows_without_tmux():
    info = PlatformInfo(
        os_name="windows",
        shell_name="powershell",
        terminal_name="Windows Terminal",
        is_tty=True,
        is_ci=False,
    )

    hint = legacy_tmux_hint(info, tmux_available=False)

    assert "Windows" in hint
    assert "one-shot" in hint


def test_legacy_tmux_hint_available():
    info = PlatformInfo(
        os_name="linux",
        shell_name="bash",
        terminal_name="xterm-256color",
        is_tty=True,
        is_ci=False,
    )

    assert legacy_tmux_hint(info, tmux_available=True) == (
        "tmux is available for legacy/debug transport."
    )
