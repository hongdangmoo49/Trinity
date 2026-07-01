"""User UI settings for the Textual workbench."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 in packaging smoke
    import tomli as tomllib


@dataclass(frozen=True)
class UISettings:
    """User-level Textual UI preferences."""

    theme_mode: str = "dark"
    color_profile: str = "default"
    density: str = "comfortable"
    motion: str = "normal"
    unicode_rendering: str = "ascii"

    def to_dict(self) -> dict[str, Any]:
        return {
            "theme_mode": self.theme_mode,
            "color_profile": self.color_profile,
            "density": self.density,
            "motion": self.motion,
            "unicode_rendering": self.unicode_rendering,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UISettings":
        return cls(
            theme_mode=_choice(data.get("theme_mode"), {"system", "dark", "light"}, "dark"),
            color_profile=_choice(
                data.get("color_profile"),
                {"auto", "default", "truecolor", "256color", "ascii-safe"},
                "default",
            ),
            density=_choice(data.get("density"), {"comfortable", "compact"}, "comfortable"),
            motion=_choice(data.get("motion"), {"normal", "reduced"}, "normal"),
            unicode_rendering=_choice(
                data.get("unicode_rendering"),
                {"auto", "unicode", "ascii"},
                "ascii",
            ),
        )


class UISettingsStore:
    """Load and save user UI preferences under Trinity state."""

    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "ui" / "settings.toml"

    def load(self) -> UISettings:
        if not self.path.exists():
            return UISettings()
        try:
            data = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return UISettings()
        if not isinstance(data, dict):
            return UISettings()
        theme = data.get("theme", data)
        if not isinstance(theme, dict):
            return UISettings()
        return UISettings.from_dict(theme)

    def save(self, settings: UISettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            tomli_w.dumps({"theme": settings.to_dict()}),
            encoding="utf-8",
        )


def _choice(value: object, choices: set[str], default: str) -> str:
    text = str(value) if value is not None else default
    return text if text in choices else default


def textual_theme_for_mode(theme_mode: str) -> str:
    """Return the Textual theme name for a saved Trinity theme mode."""
    return "textual-light" if theme_mode == "light" else "textual-dark"
