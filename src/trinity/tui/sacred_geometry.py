"""Sacred geometry ASCII mandala animator for the Trinity TUI header.

Generates rotating frames of three overlapping circles and a hexagram,
symbolising the three-agent deliberation architecture ("Three minds, one context").
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class _GlyphSet:
    """Character palette for a given render mode."""

    circle: str
    vline: str
    bslash: str
    fslash: str
    hline: str
    dot: str
    ring: str
    center: str
    bullet: str


_GLYPH_MODES: dict[str, _GlyphSet] = {
    "modern": _GlyphSet(
        circle="○",
        vline="│",
        bslash="╲",
        fslash="╱",
        hline="─",
        dot="·",
        ring="○",
        center="✦",
        bullet="•",
    ),
    "unicode": _GlyphSet(
        circle="○",
        vline="│",
        bslash="╲",
        fslash="╱",
        hline="─",
        dot="·",
        ring="○",
        center="◆",
        bullet="·",
    ),
    "ascii": _GlyphSet(
        circle="o",
        vline="|",
        bslash="\\",
        fslash="/",
        hline="-",
        dot=".",
        ring="o",
        center="*",
        bullet=".",
    ),
}

# Aspect-ratio correction factor — terminal characters are roughly 2:1 (tall : wide).
_ASPECT = 0.5


class SacredGeometryAnimator:
    """Generates rotating sacred-geometry mandala frames for terminal display.

    The geometry comprises:
    * Three overlapping circles centred at 120-degree intervals around the
      midpoint (representing the three deliberation agents).
    * Two overlapping equilateral triangles forming a hexagram (Star of David).
    * Six cardinal dots placed at 60-degree intervals.
    * A centre convergence mark.

    Args:
        width:  Canvas width in terminal columns.
        height: Canvas height in terminal rows.
        mode:   Glyph mode — ``"modern"``, ``"unicode"``, or ``"ascii"``.
    """

    def __init__(self, width: int = 40, height: int = 13, mode: str = "modern") -> None:
        if width < 1 or height < 1:
            raise ValueError(f"Dimensions must be >= 1, got width={width}, height={height}")
        if mode not in _GLYPH_MODES:
            raise ValueError(f"Unsupported render mode: {mode!r}. Valid modes: {sorted(_GLYPH_MODES)}")
        self._width = width
        self._height = height
        self._mode = mode
        self._glyphs = _GLYPH_MODES[mode]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, angle: float = 0.0) -> str:
        """Return a multi-line string representing one animation frame.

        Args:
            angle: Rotation angle in degrees.
        """
        cx = self._width / 2.0
        cy = self._height / 2.0

        canvas: list[list[str]] = [
            [" "] * self._width for _ in range(self._height)
        ]

        radius = min(cx, cy) * 0.65
        angle_rad = math.radians(angle)

        # 1. Three overlapping circles at 120-degree intervals
        for k in range(3):
            offset = math.radians(120 * k) + angle_rad
            ocx = cx + radius * 0.38 * math.cos(offset)
            ocy = cy + radius * 0.38 * math.sin(offset) * _ASPECT
            self._trace_circle(canvas, ocx, ocy, radius * 0.72)

        # 2. Two overlapping equilateral triangles → hexagram
        for sign in (1, -1):
            verts = []
            for k in range(3):
                a = math.radians(120 * k + sign * 30) + angle_rad
                vx = cx + radius * 0.95 * math.cos(a)
                vy = cy + radius * 0.95 * math.sin(a) * _ASPECT
                verts.append((vx, vy))
            for i in range(3):
                self._trace_line(
                    canvas,
                    verts[i][0], verts[i][1],
                    verts[(i + 1) % 3][0], verts[(i + 1) % 3][1],
                )

        # 3. Six cardinal dots
        for k in range(6):
            a = math.radians(60 * k) + angle_rad
            dx = cx + radius * 0.85 * math.cos(a)
            dy = cy + radius * 0.85 * math.sin(a) * _ASPECT
            self._put(canvas, dx, dy, self._glyphs.bullet)

        # 4. Centre convergence mark
        self._put(canvas, cx, cy, self._glyphs.center)

        lines = ["".join(row) for row in canvas]
        return "\n".join(lines)

    def update_mode(self, mode: str) -> None:
        """Switch the glyph set used for rendering.

        Args:
            mode: One of ``"modern"``, ``"unicode"``, or ``"ascii"``.

        Raises:
            ValueError: If *mode* is not a recognised glyph mode.
        """
        if mode not in _GLYPH_MODES:
            raise ValueError(f"Unsupported render mode: {mode!r}. Valid modes: {sorted(_GLYPH_MODES)}")
        self._mode = mode
        self._glyphs = _GLYPH_MODES[mode]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _put(self, canvas: list[list[str]], x: float, y: float, ch: str) -> None:
        """Place a character on the canvas at fractional coordinates."""
        ix = int(round(x))
        iy = int(round(y))
        if 0 <= ix < self._width and 0 <= iy < self._height:
            canvas[iy][ix] = ch

    def _trace_circle(self, canvas: list[list[str]], cx: float, cy: float, r: float) -> None:
        """Draw a circle using the ring glyph."""
        steps = max(60, int(2 * math.pi * r * 4))
        for i in range(steps):
            a = 2 * math.pi * i / steps
            px = cx + r * math.cos(a)
            py = cy + r * math.sin(a) * _ASPECT
            self._put(canvas, px, py, self._glyphs.ring)

    def _trace_line(
        self,
        canvas: list[list[str]],
        x0: float, y0: float,
        x1: float, y1: float,
    ) -> None:
        """Draw a line segment using the appropriate directional glyph."""
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy)
        if length < 0.5:
            return

        steps = max(int(length * 2.5), 2)
        for i in range(steps + 1):
            t = i / steps
            px = x0 + dx * t
            py = y0 + dy * t
            # Choose directional character based on slope
            if abs(dx) < 0.01:
                ch = self._glyphs.vline
            elif abs(dy) < 0.01:
                ch = self._glyphs.hline
            else:
                slope = dy / dx
                if slope > 0.4:
                    ch = self._glyphs.bslash
                elif slope < -0.4:
                    ch = self._glyphs.fslash
                else:
                    ch = self._glyphs.hline
            self._put(canvas, px, py, ch)
