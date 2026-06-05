"""Adaptive TUI rendering policies.

This module keeps terminal capability decisions separate from the current Rich
TUI builders. P5 can consume this small policy surface without coupling itself
to capability detection internals or hard-coded emoji assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal, Mapping

from trinity.platform.capabilities import RenderMode, TerminalCapabilities
from trinity.tui.theme import get_agent_glyph

IconStyle = Literal["emoji", "unicode", "ascii", "plain"]
BorderStyle = Literal["rounded", "unicode", "ascii", "none"]


@dataclass(frozen=True)
class TUIIconPolicy:
    """Icon choices for an adaptive TUI render mode."""

    style: IconStyle
    agents: Mapping[str, str]
    states: Mapping[str, str]
    concepts: Mapping[str, str]
    show_icons: bool = True

    def agent(self, agent_name: str) -> str:
        """Return the display glyph for an agent name."""
        if not self.show_icons:
            return ""
        if self.style == "emoji":
            return get_agent_glyph(agent_name, emoji=True)

        normalized = _normalize_key(agent_name)
        if normalized in self.agents:
            return self.agents[normalized]
        if self.style == "ascii":
            return get_agent_glyph(agent_name, emoji=False)
        return self.agents.get("default", "")

    def state(self, state: object) -> str:
        """Return the display glyph for a TUI state value or enum."""
        if not self.show_icons:
            return ""
        key = _normalize_key(getattr(state, "value", state))
        return self.states.get(key, self.states.get("unknown", "?"))

    def concept(self, name: str) -> str:
        """Return a generic UI glyph such as app, session, or result."""
        if not self.show_icons:
            return ""
        key = _normalize_key(name)
        return self.concepts.get(key, self.concepts.get("default", ""))


@dataclass(frozen=True)
class TUIBorderPolicy:
    """Border choices that later Rich integration can apply directly."""

    style: BorderStyle
    rich_box_name: str | None
    rule_character: str
    panel_enabled: bool


@dataclass(frozen=True)
class TUILiveRenderingPolicy:
    """Live refresh behavior for the active render mode."""

    enabled: bool
    refresh_per_second: float


@dataclass(frozen=True)
class TUIRenderingPolicy:
    """Complete render policy selected from terminal capabilities."""

    render_mode: RenderMode
    icons: TUIIconPolicy
    border: TUIBorderPolicy
    live: TUILiveRenderingPolicy


def select_rendering_policy(capabilities: TerminalCapabilities) -> TUIRenderingPolicy:
    """Select a TUI rendering policy from detected terminal capabilities."""
    return policy_for_render_mode(
        capabilities.render_mode,
        supports_live_render=capabilities.supports_live_render,
    )


def policy_for_render_mode(
    render_mode: RenderMode,
    *,
    supports_live_render: bool | None = None,
) -> TUIRenderingPolicy:
    """Return the policy for a render mode.

    `TerminalCapabilities.render_mode` already folds in terminal liveness and
    color constraints. The optional live flag keeps this function defensive for
    tests and future callers that pass a mode directly.
    """
    if render_mode not in _POLICIES:
        raise ValueError(f"Unsupported TUI render mode: {render_mode}")

    policy = _POLICIES[render_mode]
    if supports_live_render is False and policy.live.enabled:
        return replace(policy, live=replace(policy.live, enabled=False))
    return policy


def _normalize_key(value: object) -> str:
    return str(value).strip().lower()


def _mapping(values: dict[str, str]) -> Mapping[str, str]:
    return MappingProxyType(values)


_MODERN_ICONS = TUIIconPolicy(
    style="emoji",
    agents=_mapping({}),
    states=_mapping(
        {
            "idle": "⬜",
            "ready": "✅",
            "responding": "🔄",
            "responded": "✅",
            "error": "❌",
            "not_ready": "⚠️",
            "disabled": "⏸️",
            "unknown": "❓",
        }
    ),
    concepts=_mapping(
        {
            "app": "🧠",
            "session": "📡",
            "time": "⏱",
            "agents": "📊",
            "deliberation": "💬",
            "result": "📋",
            "task": "🎯",
            "consensus": "✅",
            "default": "•",
        }
    ),
)

_UNICODE_ICONS = TUIIconPolicy(
    style="unicode",
    agents=_mapping(
        {
            "claude": "◇",
            "codex": "◆",
            "antigravity": "△",
            "default": "○",
        }
    ),
    states=_mapping(
        {
            "idle": "□",
            "ready": "✓",
            "responding": "↻",
            "responded": "✓",
            "error": "×",
            "not_ready": "!",
            "disabled": "‖",
            "unknown": "?",
        }
    ),
    concepts=_mapping(
        {
            "app": "◆",
            "session": "◇",
            "time": "◷",
            "agents": "▣",
            "deliberation": "≡",
            "result": "▤",
            "task": "◇",
            "consensus": "✓",
            "default": "•",
        }
    ),
)

_ASCII_ICONS = TUIIconPolicy(
    style="ascii",
    agents=_mapping(
        {
            "claude": "C",
            "codex": "X",
            "antigravity": "A",
            "default": "?",
        }
    ),
    states=_mapping(
        {
            "idle": "[ ]",
            "ready": "OK",
            "responding": "...",
            "responded": "OK",
            "error": "XX",
            "not_ready": "!!",
            "disabled": "--",
            "unknown": "?",
        }
    ),
    concepts=_mapping(
        {
            "app": "*",
            "session": "@",
            "time": "t",
            "agents": "#",
            "deliberation": ">",
            "result": "=",
            "task": "+",
            "consensus": "OK",
            "default": "*",
        }
    ),
)

_PLAIN_ICONS = TUIIconPolicy(
    style="plain",
    agents=_mapping({}),
    states=_mapping({}),
    concepts=_mapping({}),
    show_icons=False,
)

_POLICIES: Mapping[RenderMode, TUIRenderingPolicy] = MappingProxyType(
    {
        "modern": TUIRenderingPolicy(
            render_mode="modern",
            icons=_MODERN_ICONS,
            border=TUIBorderPolicy(
                style="rounded",
                rich_box_name="ROUNDED",
                rule_character="─",
                panel_enabled=True,
            ),
            live=TUILiveRenderingPolicy(enabled=True, refresh_per_second=8.0),
        ),
        "unicode": TUIRenderingPolicy(
            render_mode="unicode",
            icons=_UNICODE_ICONS,
            border=TUIBorderPolicy(
                style="unicode",
                rich_box_name="SQUARE",
                rule_character="─",
                panel_enabled=True,
            ),
            live=TUILiveRenderingPolicy(enabled=True, refresh_per_second=4.0),
        ),
        "ascii": TUIRenderingPolicy(
            render_mode="ascii",
            icons=_ASCII_ICONS,
            border=TUIBorderPolicy(
                style="ascii",
                rich_box_name="ASCII",
                rule_character="-",
                panel_enabled=True,
            ),
            live=TUILiveRenderingPolicy(enabled=True, refresh_per_second=4.0),
        ),
        "plain": TUIRenderingPolicy(
            render_mode="plain",
            icons=_PLAIN_ICONS,
            border=TUIBorderPolicy(
                style="none",
                rich_box_name=None,
                rule_character="-",
                panel_enabled=False,
            ),
            live=TUILiveRenderingPolicy(enabled=False, refresh_per_second=0.0),
        ),
    }
)
