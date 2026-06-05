"""Runtime selection for the Textual workbench."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from os import environ
from typing import Mapping

TRINITY_TUI_ENV = "TRINITY_TUI"
_TEXTUAL_ALIASES = {"auto", "textual", "app", "workbench"}
_PLAIN_ALIASES = {"plain", "rich", "legacy", "prompt"}


@dataclass(frozen=True)
class TuiRuntimeMode:
    """Resolved interactive UI mode."""

    requested: str
    selected: str
    textual_available: bool
    reason: str = ""

    @property
    def use_textual(self) -> bool:
        return self.selected == "textual"


def textual_is_available() -> bool:
    """Return True when Textual can be imported."""
    return find_spec("textual") is not None


def normalize_tui_mode(value: str | None) -> str:
    """Normalize a requested TUI mode."""
    mode = (value or "auto").strip().lower()
    if mode in _TEXTUAL_ALIASES:
        return "auto" if mode == "auto" else "textual"
    if mode in _PLAIN_ALIASES:
        return "plain"
    raise ValueError(
        f"Unsupported TUI mode: {value!r}. "
        "Expected auto, textual, or plain."
    )


def resolve_tui_runtime(
    requested: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    textual_available: bool | None = None,
) -> TuiRuntimeMode:
    """Resolve whether Trinity should launch Textual or plain TUI."""
    source_env = environ if env is None else env
    requested_mode = normalize_tui_mode(requested or source_env.get(TRINITY_TUI_ENV))
    available = textual_is_available() if textual_available is None else textual_available

    if requested_mode == "plain":
        return TuiRuntimeMode(
            requested=requested_mode,
            selected="plain",
            textual_available=available,
            reason="plain-forced",
        )

    if available:
        return TuiRuntimeMode(
            requested=requested_mode,
            selected="textual",
            textual_available=True,
            reason="textual-available",
        )

    return TuiRuntimeMode(
        requested=requested_mode,
        selected="plain",
        textual_available=False,
        reason="textual-unavailable",
    )
