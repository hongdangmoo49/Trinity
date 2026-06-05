"""Tests for SacredGeometryAnimator — sacred geometry ASCII mandala frames."""

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


def test_animator_traces_overlapping_circles() -> None:
    """The three overlapping circles should produce substantial non-space content."""
    anim = SacredGeometryAnimator(width=60, height=20)
    frame = anim.render(angle=0.0)
    non_space = sum(1 for ch in frame if ch not in (" ", "\n"))
    # With three circles and a hexagram we expect significant content
    assert non_space > 20, f"expected substantial content, got {non_space} non-space chars"


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
