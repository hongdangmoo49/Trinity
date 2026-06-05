"""Tests for SacredGeometryAnimator — rotating 3D geometric wireframe frames."""

from __future__ import annotations

import pytest

from trinity.tui.sacred_geometry import SacredGeometryAnimator


def test_animator_produces_non_empty_frame() -> None:
    """A rendered frame should contain non-whitespace characters."""
    anim = SacredGeometryAnimator()
    frame = anim.render(angle=0.0)
    assert frame.strip(), "frame must contain visible content"


def test_animator_frame_has_expected_dimensions() -> None:
    """Frame should have the correct number of lines matching the configured height."""
    anim = SacredGeometryAnimator(width=40, height=13)
    frame = anim.render(angle=0.0)
    lines = frame.splitlines()
    assert len(lines) == 13, f"expected 13 lines, got {len(lines)}"
    for line in lines:
        assert len(line) == 40, f"Line length mismatch: {len(line)} != 40"


def test_animator_different_angles_produce_different_frames() -> None:
    """Rotation should cause visible changes in the output."""
    anim = SacredGeometryAnimator()
    frame_0 = anim.render(angle=0.0)
    frame_90 = anim.render(angle=90.0)
    assert frame_0 != frame_90, "different angles should produce different frames"


def test_animator_loop_endpoint_matches_start_frame() -> None:
    """A full 360-degree cycle should return to the exact starting frame."""
    anim = SacredGeometryAnimator(width=56, height=14, mode="ascii")
    assert anim.render(angle=0.0) == anim.render(angle=360.0)


def test_animator_ascii_mode_uses_only_ascii_chars() -> None:
    """In ascii mode every character in the frame should have ordinal < 128."""
    anim = SacredGeometryAnimator(mode="ascii")
    frame = anim.render(angle=0.0)
    for ch in frame:
        if ch not in ("\n",):
            assert ord(ch) < 128, f"non-ASCII character found: {ch!r} (ord={ord(ch)})"


def test_animator_center_mark_present() -> None:
    """The centre convergence glyph should appear somewhere in the frame."""
    anim = SacredGeometryAnimator()
    frame = anim.render(angle=0.0)
    # centre glyph in modern mode is "✦"
    assert "✦" in frame, "centre mark glyph should be present in modern mode"


def test_animator_traces_3d_wireframe() -> None:
    """The projected 3D form should produce substantial non-space content."""
    anim = SacredGeometryAnimator(width=60, height=20)
    frame = anim.render(angle=0.0)
    non_space = sum(1 for ch in frame if ch not in (" ", "\n"))
    assert non_space > 20, f"expected substantial content, got {non_space} non-space chars"


def test_animator_compact_textual_size_remains_visible() -> None:
    """The Textual start-screen size should still render a recognizable wireframe."""
    anim = SacredGeometryAnimator(width=56, height=14, mode="ascii")
    frame = anim.render(angle=30.0)
    non_space = sum(1 for ch in frame if ch not in (" ", "\n"))
    assert non_space > 16, f"expected compact wireframe content, got {non_space} non-space chars"


def test_animator_update_mode_changes_glyphs() -> None:
    """Switching mode should change the set of glyphs used in the frame."""
    anim = SacredGeometryAnimator(mode="modern")
    frame_modern = anim.render(angle=0.0)
    anim.update_mode("ascii")
    frame_ascii = anim.render(angle=0.0)
    assert frame_modern != frame_ascii, "mode switch should change rendered glyphs"


def test_animator_rejects_invalid_mode() -> None:
    """Constructing with an unsupported mode should raise ValueError."""
    with pytest.raises(ValueError, match="Unsupported render mode"):
        SacredGeometryAnimator(mode="nonexistent")


def test_animator_update_mode_rejects_invalid() -> None:
    """Switching to an unsupported mode should raise ValueError."""
    animator = SacredGeometryAnimator()
    with pytest.raises(ValueError, match="Unsupported render mode"):
        animator.update_mode("bad")


def test_animator_rejects_zero_dimensions() -> None:
    """Constructing with zero or negative dimensions should raise ValueError."""
    with pytest.raises(ValueError, match="Dimensions must be >= 1"):
        SacredGeometryAnimator(width=0, height=0)


from trinity.tui.app import TrinityTUI
from trinity.config import TrinityConfig


def _make_config() -> TrinityConfig:
    """Create a minimal config for testing."""
    return TrinityConfig(
        session_name="test",
        agents={},
    )


def test_tui_header_renders_with_geometry():
    """TUI header should render with geometry without errors."""
    config = _make_config()
    tui = TrinityTUI(config)
    header = tui.build_header()
    from rich.console import Console
    console = Console(width=80, force_terminal=True)
    console.render(header)  # Should not raise


def test_tui_has_animator_attribute():
    """TrinityTUI should have a SacredGeometryAnimator instance."""
    config = _make_config()
    tui = TrinityTUI(config)
    # May or may not have animator depending on terminal size in CI
    assert hasattr(tui, "_geometry_animator")


def test_tui_animator_disabled_when_show_geometry_false():
    """Animator should be None when show_geometry is False."""
    config = _make_config()
    tui = TrinityTUI(config, show_geometry=False)
    assert tui._geometry_animator is None


from rich.text import Text


def test_animator_render_rich_returns_text():
    """render_rich should return a Rich Text object."""
    animator = SacredGeometryAnimator(width=40, height=13)
    text = animator.render_rich(angle=0.0, colors=["red", "green", "blue"])
    assert isinstance(text, Text)
    assert len(text) > 0


def test_animator_rich_loop_endpoint_matches_start_frame():
    """Rich rendering should use the same seamless 360-degree cycle."""
    animator = SacredGeometryAnimator(width=40, height=13)
    colors = ["red", "green", "blue"]
    assert animator.render_rich(angle=0.0, colors=colors) == animator.render_rich(
        angle=360.0,
        colors=colors,
    )


def test_animator_render_rich_has_style_spans():
    """Rich output should contain styled spans for colors."""
    animator = SacredGeometryAnimator(width=40, height=13)
    text = animator.render_rich(angle=0.0, colors=["red", "green", "blue"])
    # Should have at least some styled spans
    assert len(text._spans) > 0


def test_animator_render_rich_uses_custom_colors():
    """Custom colors should appear in the style spans."""
    animator = SacredGeometryAnimator(width=40, height=13)
    text = animator.render_rich(angle=0.0, colors=["red1", "green1", "blue1"])
    # At least one span should use one of our colors
    span_styles = [str(s.style) for s in text._spans if s.style]
    assert any("red1" in s or "green1" in s or "blue1" in s for s in span_styles)
