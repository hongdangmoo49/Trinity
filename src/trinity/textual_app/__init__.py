"""Textual workbench UI for Trinity."""

from __future__ import annotations

from trinity.textual_app.runtime import (
    TRINITY_TUI_ENV,
    TuiRuntimeMode,
    resolve_tui_runtime,
)

__all__ = [
    "TRINITY_TUI_ENV",
    "TrinityTextualApp",
    "TuiRuntimeMode",
    "resolve_tui_runtime",
]


def __getattr__(name: str):
    if name == "TrinityTextualApp":
        from trinity.textual_app.app import TrinityTextualApp

        return TrinityTextualApp
    raise AttributeError(name)
