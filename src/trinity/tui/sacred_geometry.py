"""Rotating Trinity geometry for terminal headers.

The scene is a triadic 3D wireframe: three orbital rings set 120 degrees apart
around a central triangular core. It keeps the product name visible in the
structure itself: three independent paths, one shared convergence point.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rich.text import Text


@dataclass(frozen=True)
class _GlyphSet:
    """Character palette for a render mode."""

    near: str
    mid: str
    far: str
    node: str
    center: str


_GLYPH_MODES: dict[str, _GlyphSet] = {
    "modern": _GlyphSet(near="━", mid="─", far="·", node="◆", center="✦"),
    "unicode": _GlyphSet(near="═", mid="─", far="·", node="◇", center="◆"),
    "ascii": _GlyphSet(near="#", mid="+", far=".", node="o", center="*"),
}

_Point3 = tuple[float, float, float]
_Projected = tuple[float, float, float]

_TRIAD_ANGLES = (math.radians(90), math.radians(210), math.radians(330))


class SacredGeometryAnimator:
    """Generates rotating Trinity-themed 3D wireframe frames."""

    def __init__(self, width: int = 40, height: int = 13, mode: str = "modern") -> None:
        if width < 1 or height < 1:
            raise ValueError(f"Dimensions must be >= 1, got width={width}, height={height}")
        if mode not in _GLYPH_MODES:
            raise ValueError(f"Unsupported render mode: {mode!r}. Valid modes: {sorted(_GLYPH_MODES)}")
        self._width = width
        self._height = height
        self._glyphs = _GLYPH_MODES[mode]

    def render(self, angle: float = 0.0) -> str:
        """Return a multi-line string representing one animation frame."""
        cells = self._render_cells(angle=angle)
        return "\n".join("".join(ch for ch, _style in row) for row in cells)

    def render_rich(self, angle: float = 0.0, colors: list[str] | None = None) -> Text:
        """Return a Rich Text frame with one accent color per Trinity orbit."""
        if colors is None:
            colors = ["cyan", "green", "magenta"]

        result = Text()
        cells = self._render_cells(angle=angle, colors=colors)
        for y, row in enumerate(cells):
            for ch, style in row:
                result.append(ch, style=style) if style else result.append(ch)
            if y < len(cells) - 1:
                result.append("\n")
        return result

    def update_mode(self, mode: str) -> None:
        """Switch the glyph set used for rendering."""
        if mode not in _GLYPH_MODES:
            raise ValueError(f"Unsupported render mode: {mode!r}. Valid modes: {sorted(_GLYPH_MODES)}")
        self._glyphs = _GLYPH_MODES[mode]

    def _render_cells(
        self,
        *,
        angle: float,
        colors: list[str] | None = None,
    ) -> list[list[tuple[str, str | None]]]:
        canvas: list[list[tuple[str, str | None]]] = [
            [(" ", None) for _ in range(self._width)]
            for _ in range(self._height)
        ]
        depth: list[list[float]] = [
            [-999.0 for _ in range(self._width)]
            for _ in range(self._height)
        ]

        for orbit_index in range(3):
            style = colors[orbit_index % len(colors)] if colors else self._depth_style(0.15)
            self._draw_orbit(canvas, depth, angle, orbit_index, style)

        core_nodes = [self._rotate(self._core_node(index), angle) for index in range(3)]
        center = self._rotate((0.0, 0.0, 0.0), angle)
        crown = self._rotate((0.0, 0.88, 0.0), angle)
        base = self._rotate((0.0, -0.88, 0.0), angle)

        for index in range(3):
            next_index = (index + 1) % 3
            style = colors[index % len(colors)] if colors else "bright_cyan"
            self._draw_segment(canvas, depth, core_nodes[index], core_nodes[next_index], style)
            self._draw_segment(canvas, depth, center, core_nodes[index], style)
            self._draw_segment(canvas, depth, crown, core_nodes[index], style)
            self._draw_segment(canvas, depth, base, core_nodes[index], "dim cyan")

        for index, node in enumerate(core_nodes):
            style = colors[index % len(colors)] if colors else "bright_white"
            projected = self._project(node)
            self._put(canvas, depth, projected, node[2] + 0.12, self._glyphs.node, style)

        self._put(canvas, depth, self._project(crown), crown[2] + 0.12, self._glyphs.node, "bright_white")
        self._put(canvas, depth, self._project(base), base[2] + 0.04, self._depth_glyph(base[2]), "dim cyan")
        self._put(canvas, depth, self._project(center), 999.0, self._glyphs.center, "bright_white")
        return canvas

    def _draw_orbit(
        self,
        canvas: list[list[tuple[str, str | None]]],
        depth: list[list[float]],
        angle: float,
        orbit_index: int,
        style: str | None,
    ) -> None:
        phi = math.radians(orbit_index * 120)
        u = (math.cos(phi), 0.0, math.sin(phi))
        v = (0.0, 1.0, 0.0)
        radius = 1.42
        samples = 108
        previous: _Point3 | None = None
        for sample in range(samples + 1):
            t = math.tau * sample / samples
            pulse = 1.0 + 0.045 * math.sin(t * 3.0 + math.radians(angle) * 1.7)
            point = (
                radius * pulse * (math.cos(t) * u[0] + math.sin(t) * v[0]),
                radius * pulse * (math.cos(t) * u[1] + math.sin(t) * v[1]),
                radius * pulse * (math.cos(t) * u[2] + math.sin(t) * v[2]),
            )
            rotated = self._rotate(point, angle)
            if previous is not None:
                self._draw_segment(canvas, depth, previous, rotated, style)
            previous = rotated

    def _core_node(self, index: int) -> _Point3:
        angle = _TRIAD_ANGLES[index]
        radius = 0.72
        return (radius * math.cos(angle), 0.0, radius * math.sin(angle))

    def _rotate(self, point: _Point3, angle: float) -> _Point3:
        x, y, z = point
        yaw = math.radians(angle)
        pitch = math.radians(angle * 0.42 + 18.0)
        roll = math.radians(angle * 0.18)

        x, z = (
            x * math.cos(yaw) - z * math.sin(yaw),
            x * math.sin(yaw) + z * math.cos(yaw),
        )
        y, z = (
            y * math.cos(pitch) - z * math.sin(pitch),
            y * math.sin(pitch) + z * math.cos(pitch),
        )
        x, y = (
            x * math.cos(roll) - y * math.sin(roll),
            x * math.sin(roll) + y * math.cos(roll),
        )
        return (x, y, z)

    def _project(self, point: _Point3) -> _Projected:
        x, y, z = point
        distance = 4.6
        perspective = distance / (distance - z)
        scale = min(self._width / 4.6, self._height / 2.65)
        sx = self._width / 2.0 + x * scale * perspective
        sy = self._height / 2.0 - y * scale * perspective * 0.82
        return (sx, sy, z)

    def _draw_segment(
        self,
        canvas: list[list[tuple[str, str | None]]],
        depth: list[list[float]],
        start: _Point3,
        end: _Point3,
        style: str | None,
    ) -> None:
        p0 = self._project(start)
        p1 = self._project(end)
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        steps = max(int(length * 3.2), 2)
        for step in range(steps + 1):
            t = step / steps
            x = p0[0] + (p1[0] - p0[0]) * t
            y = p0[1] + (p1[1] - p0[1]) * t
            z = p0[2] + (p1[2] - p0[2]) * t
            self._put(canvas, depth, (x, y, z), z, self._depth_glyph(z), style or self._depth_style(z))

    def _put(
        self,
        canvas: list[list[tuple[str, str | None]]],
        depth: list[list[float]],
        projected: _Projected,
        z: float,
        ch: str,
        style: str | None,
    ) -> None:
        x, y, _ = projected
        ix = int(round(x))
        iy = int(round(y))
        if 0 <= ix < self._width and 0 <= iy < self._height and z >= depth[iy][ix]:
            depth[iy][ix] = z
            canvas[iy][ix] = (ch, style)

    def _depth_glyph(self, z: float) -> str:
        if z > 0.55:
            return self._glyphs.near
        if z > -0.35:
            return self._glyphs.mid
        return self._glyphs.far

    @staticmethod
    def _depth_style(z: float) -> str:
        if z > 0.55:
            return "bright_cyan"
        if z > -0.35:
            return "cyan"
        return "dim cyan"
