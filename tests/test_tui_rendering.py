"""Tests for adaptive TUI rendering policy selection."""

from enum import Enum

import pytest

from trinity.platform.capabilities import TerminalCapabilities
from trinity.tui.rendering import policy_for_render_mode, select_rendering_policy
from trinity.tui.theme import get_agent_glyph, get_theme


class ExampleState(str, Enum):
    RESPONDED = "responded"


def _capabilities(
    *,
    color_system: str = "truecolor",
    supports_unicode: bool = True,
    supports_emoji: bool = True,
    supports_box_drawing: bool = True,
    supports_live_render: bool = True,
) -> TerminalCapabilities:
    return TerminalCapabilities(
        color_system=color_system,  # type: ignore[arg-type]
        supports_unicode=supports_unicode,
        supports_emoji=supports_emoji,
        supports_box_drawing=supports_box_drawing,
        supports_live_render=supports_live_render,
        width=120,
        height=40,
    )


def test_modern_policy_uses_emoji_rounded_borders_and_live_rendering():
    policy = select_rendering_policy(_capabilities())

    assert policy.render_mode == "modern"
    assert policy.icons.style == "emoji"
    assert policy.icons.agent("claude") == get_theme("claude").icon
    assert policy.icons.state("responding") == "🔄"
    assert policy.border.style == "rounded"
    assert policy.border.rich_box_name == "ROUNDED"
    assert policy.border.panel_enabled is True
    assert policy.live.enabled is True


def test_unicode_policy_avoids_emoji_but_keeps_unicode_borders_and_live_rendering():
    policy = select_rendering_policy(
        _capabilities(supports_emoji=False, supports_box_drawing=True)
    )

    assert policy.render_mode == "unicode"
    assert policy.icons.style == "unicode"
    assert policy.icons.agent("claude") == "◇"
    assert policy.icons.state(ExampleState.RESPONDED) == "✓"
    assert policy.border.style == "unicode"
    assert policy.border.rich_box_name == "SQUARE"
    assert policy.border.rule_character == "─"
    assert policy.live.enabled is True


def test_ascii_policy_uses_ascii_icons_and_ascii_border():
    policy = select_rendering_policy(
        _capabilities(
            color_system="standard",
            supports_unicode=False,
            supports_emoji=False,
            supports_box_drawing=False,
        )
    )

    assert policy.render_mode == "ascii"
    assert policy.icons.style == "ascii"
    assert policy.icons.agent("codex") == "X"
    assert policy.icons.agent("new-agent") == "N"
    assert policy.icons.state("not_ready") == "!!"
    assert policy.border.style == "ascii"
    assert policy.border.rich_box_name == "ASCII"
    assert policy.border.rule_character == "-"
    assert policy.live.enabled is True


def test_plain_policy_disables_icons_borders_and_live_rendering():
    policy = select_rendering_policy(
        _capabilities(color_system="none", supports_live_render=False)
    )

    assert policy.render_mode == "plain"
    assert policy.icons.style == "plain"
    assert policy.icons.agent("claude") == ""
    assert policy.icons.state("responded") == ""
    assert policy.icons.concept("result") == ""
    assert policy.border.style == "none"
    assert policy.border.rich_box_name is None
    assert policy.border.panel_enabled is False
    assert policy.live.enabled is False
    assert policy.live.refresh_per_second == 0.0


def test_policy_for_render_mode_can_defensively_disable_live_rendering():
    policy = policy_for_render_mode("modern", supports_live_render=False)

    assert policy.render_mode == "modern"
    assert policy.live.enabled is False
    assert policy.icons.style == "emoji"


def test_policy_for_render_mode_rejects_unknown_modes():
    with pytest.raises(ValueError, match="Unsupported TUI render mode"):
        policy_for_render_mode("fancy")  # type: ignore[arg-type]


def test_theme_agent_glyphs_have_ascii_fallbacks():
    assert get_agent_glyph("claude", emoji=False) == "C"
    assert get_agent_glyph("codex", emoji=False) == "X"
    assert get_agent_glyph("unknown", emoji=False) == "U"
    assert get_agent_glyph("", emoji=False) == "?"


def test_unknown_agent_theme_uses_deterministic_palette():
    first = get_theme("new-agent")
    second = get_theme("new-agent")

    assert first.color == second.color
    assert first.border_style == second.border_style
