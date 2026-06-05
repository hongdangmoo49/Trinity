"""Trinity TUI theme — per-agent visual configuration.

Assigns distinct colors, icons, and role labels to each agent
for visual differentiation in the TUI.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTheme:
    """Visual theme for a single agent.

    Attributes:
        name: Agent identifier (e.g. "claude").
        color: Rich color name for text and borders.
        icon: Unicode emoji for the agent.
        role_label: Short role description (e.g. "Architect").
        border_style: Rich color name for panel borders.
    """

    name: str
    color: str
    icon: str
    role_label: str
    border_style: str


# Default themes for known agents
AGENT_THEMES: dict[str, AgentTheme] = {
    "claude": AgentTheme(
        name="claude",
        color="cyan",
        icon="🏗️",
        role_label="Architect",
        border_style="cyan",
    ),
    "codex": AgentTheme(
        name="codex",
        color="green",
        icon="⚙️",
        role_label="Implementer",
        border_style="green",
    ),
    "antigravity": AgentTheme(
        name="antigravity",
        color="bright_magenta",
        icon="🔍",
        role_label="Reviewer",
        border_style="bright_magenta",
    ),
}

AGENT_ASCII_GLYPHS: dict[str, str] = {
    "claude": "C",
    "codex": "X",
    "antigravity": "A",
}

# Fallback palette for unknown agents
_FALLBACK_PALETTE = [
    "bright_blue",
    "bright_green",
    "bright_magenta",
    "bright_yellow",
    "bright_red",
    "bright_cyan",
]


def get_theme(agent_name: str) -> AgentTheme:
    """Get the visual theme for an agent.

    Args:
        agent_name: The agent's name.

    Returns:
        AgentTheme with either a known or fallback color assignment.
    """
    if agent_name in AGENT_THEMES:
        return AGENT_THEMES[agent_name]

    # Deterministic fallback independent from Python's per-process hash seed.
    idx = sum(agent_name.encode("utf-8")) % len(_FALLBACK_PALETTE)
    color = _FALLBACK_PALETTE[idx]
    return AgentTheme(
        name=agent_name,
        color=color,
        icon="🤖",
        role_label=agent_name.title(),
        border_style=color,
    )


def get_agent_glyph(agent_name: str, *, emoji: bool = True) -> str:
    """Return an agent glyph that can be downgraded for ASCII render modes."""
    if emoji:
        return get_theme(agent_name).icon

    normalized = agent_name.strip().lower()
    if normalized in AGENT_ASCII_GLYPHS:
        return AGENT_ASCII_GLYPHS[normalized]
    if normalized:
        return normalized[0].upper()
    return "?"
