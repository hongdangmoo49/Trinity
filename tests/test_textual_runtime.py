from __future__ import annotations

import pytest

from trinity.textual_app.runtime import normalize_tui_mode, resolve_tui_runtime


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "auto"),
        ("auto", "auto"),
        ("textual", "textual"),
        ("app", "textual"),
        ("workbench", "textual"),
        ("plain", "plain"),
        ("rich", "plain"),
        ("legacy", "plain"),
    ],
)
def test_normalize_tui_mode(value: str | None, expected: str) -> None:
    assert normalize_tui_mode(value) == expected


def test_normalize_tui_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="Unsupported TUI mode"):
        normalize_tui_mode("unknown")


def test_resolve_tui_runtime_prefers_textual_when_available() -> None:
    runtime = resolve_tui_runtime(env={}, textual_available=True)

    assert runtime.use_textual is True
    assert runtime.selected == "textual"
    assert runtime.reason == "textual-available"


def test_resolve_tui_runtime_falls_back_when_textual_is_missing() -> None:
    runtime = resolve_tui_runtime(env={}, textual_available=False)

    assert runtime.use_textual is False
    assert runtime.selected == "plain"
    assert runtime.reason == "textual-unavailable"


def test_resolve_tui_runtime_honors_plain_environment_override() -> None:
    runtime = resolve_tui_runtime(
        env={"TRINITY_TUI": "plain"},
        textual_available=True,
    )

    assert runtime.use_textual is False
    assert runtime.selected == "plain"
    assert runtime.reason == "plain-forced"


def test_resolve_tui_runtime_honors_explicit_request_over_environment() -> None:
    runtime = resolve_tui_runtime(
        requested="textual",
        env={"TRINITY_TUI": "plain"},
        textual_available=True,
    )

    assert runtime.use_textual is True
    assert runtime.selected == "textual"
