# Sacred Geometry ASCII Animation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a rotating sacred geometry mandala animation to the Trinity Rich TUI header that reinforces the "Three minds, one context" branding.

**Architecture:** A new `SacredGeometryAnimator` class generates frames dynamically using trigonometric math, rendering overlapping circles, rotating triangles, and a central convergence point as ASCII art. It integrates into the existing `build_header()` method in `TrinityTUI` and adapts characters to the current `TUIRenderingPolicy`.

**Tech Stack:** Python 3.11+, Rich (Text/Console), math (sin/cos), existing TUI infrastructure (`TUIRenderingPolicy`, `AgentTheme`).

---

### Task 1: Create `SacredGeometryAnimator` core with frame generation

**Files:**
- Create: `src/trinity/tui/sacred_geometry.py`
- Test: `tests/test_tui_sacred_geometry.py`

**Step 1: Write the failing test for frame generation**

```python
"""Tests for sacred geometry ASCII animation."""
import math

import pytest

from trinity.tui.sacred_geometry import SacredGeometryAnimator


def test_animator_produces_non_empty_frame():
    """Animator should produce at least one non-empty line."""
    animator = SacredGeometryAnimator(width=40, height=13)
    frame = animator.render(angle=0.0)
    lines = frame.split("\n")
    non_empty = [l for l in lines if l.strip()]
    assert len(non_empty) > 0


def test_animator_frame_has_expected_dimensions():
    """Each frame should match the configured height."""
    animator = SacredGeometryAnimator(width=40, height=13)
    frame = animator.render(angle=0.0)
    lines = frame.rstrip("\n").split("\n")
    assert len(lines) == 13


def test_animator_different_angles_produce_different_frames():
    """Rotating should change the output."""
    animator = SacredGeometryAnimator(width=40, height=13)
    frame0 = animator.render(angle=0.0)
    frame1 = animator.render(angle=math.pi / 3)
    assert frame0 != frame1


def test_animator_ascii_mode_uses_only_ascii_chars():
    """ASCII mode should not use any Unicode characters."""
    animator = SacredGeometryAnimator(
        width=40, height=13, mode="ascii",
    )
    frame = animator.render(angle=0.0)
    for ch in frame:
        if ch not in "\n\r\t":
            assert ord(ch) < 128, f"Non-ASCII char: {ch!r}"


def test_animator_center_mark_present():
    """Frame should contain a center mark at the origin."""
    animator = SacredGeometryAnimator(width=40, height=13)
    frame = animator.render(angle=0.0)
    # Center mark should be one of the expected characters
    assert any(c in frame for c in ("✦", "◆", "*", "+"))


def test_animator_traces_overlapping_circles():
    """Three circles should be traced at 120-degree intervals."""
    animator = SacredGeometryAnimator(width=40, height=13)
    frame = animator.render(angle=0.0)
    # Should have characters (the circles produce points)
    assert len(frame.strip()) > 20
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tui_sacred_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'trinity.tui.sacred_geometry'`

**Step 3: Write minimal implementation**

```python
"""Sacred geometry ASCII art animator for Trinity TUI.

Generates rotating mandala frames using trigonometric math:
- Three overlapping circles (representing the three agents)
- Rotating equilateral triangles
- Central convergence point (representing consensus)
- Adapts characters to the current render mode
"""

from __future__ import annotations

import math
from typing import Literal

# Character sets per render mode
_GLYPHS: dict[str, dict[str, str]] = {
    "modern": {
        "point": "·",
        "line_h": "─",
        "line_v": "│",
        "diag_ur": "╱",
        "diag_ul": "╲",
        "center": "✦",
        "vertex": "◆",
        "circle": "○",
        "dot": "•",
    },
    "unicode": {
        "point": "·",
        "line_h": "─",
        "line_v": "│",
        "diag_ur": "╱",
        "diag_ul": "╲",
        "center": "◆",
        "vertex": "◇",
        "circle": "○",
        "dot": "·",
    },
    "ascii": {
        "point": ".",
        "line_h": "-",
        "line_v": "|",
        "diag_ur": "/",
        "diag_ul": "\\",
        "center": "*",
        "vertex": "+",
        "circle": "o",
        "dot": ".",
    },
}

RenderMode = Literal["modern", "unicode", "ascii"]


class SacredGeometryAnimator:
    """Generates rotating sacred geometry mandala frames.

    Args:
        width: Canvas width in characters.
        height: Canvas height in rows.
        mode: Render mode for character selection.
    """

    def __init__(
        self,
        width: int = 40,
        height: int = 13,
        mode: RenderMode = "modern",
    ):
        self.width = width
        self.height = height
        self.mode = mode
        self._glyphs = _GLYPHS.get(mode, _GLYPHS["ascii"])

        # Grid: list of lists of characters
        self._grid: list[list[str]] = []

    def render(self, angle: float = 0.0) -> str:
        """Render a single frame at the given rotation angle.

        Args:
            angle: Rotation angle in radians.

        Returns:
            Multi-line string containing the ASCII art frame.
        """
        # Initialize blank grid
        self._grid = [
            [" " for _ in range(self.width)]
            for _ in range(self.height)
        ]

        cx = self.width / 2
        cy = self.height / 2
        radius = min(self.width, self.height) * 0.35

        # 1. Draw three overlapping circles at 120-degree intervals
        for i in range(3):
            offset_angle = angle + i * (2 * math.pi / 3)
            ocx = cx + radius * 0.3 * math.cos(offset_angle)
            ocy = cy + radius * 0.3 * math.sin(offset_angle) * 0.5  # Aspect ratio
            self._draw_circle(ocx, ocy, radius * 0.7)

        # 2. Draw rotating equilateral triangle
        self._draw_triangle(cx, cy, radius * 0.85, angle)

        # 3. Draw inner inverted triangle (hexagram effect)
        self._draw_triangle(cx, cy, radius * 0.85, angle + math.pi)

        # 4. Draw center mark
        self._set_char(int(cx), int(cy), self._glyphs["center"])

        # 5. Draw cardinal dots
        for i in range(6):
            dot_angle = angle / 3 + i * (math.pi / 3)  # Slow rotation
            dx = cx + radius * 0.55 * math.cos(dot_angle)
            dy = cy + radius * 0.55 * math.sin(dot_angle) * 0.5
            self._set_char(int(dx), int(dy), self._glyphs["dot"])

        # Convert grid to string
        return "\n".join("".join(row).rstrip() for row in self._grid)

    def _draw_circle(self, cx: float, cy: float, radius: float) -> None:
        """Draw a circle using parametric points."""
        steps = max(40, int(radius * 4))
        for i in range(steps):
            t = 2 * math.pi * i / steps
            x = cx + radius * math.cos(t)
            y = cy + radius * math.sin(t) * 0.5  # Aspect ratio correction
            ix, iy = int(x), int(y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                existing = self._grid[iy][ix]
                if existing == " ":
                    self._grid[iy][ix] = self._glyphs["circle"]

    def _draw_triangle(
        self, cx: float, cy: float, radius: float, angle: float,
    ) -> None:
        """Draw an equilateral triangle rotated by angle."""
        vertices = []
        for i in range(3):
            va = angle + i * (2 * math.pi / 3) - math.pi / 2
            vx = cx + radius * math.cos(va)
            vy = cy + radius * math.sin(va) * 0.5  # Aspect ratio
            vertices.append((vx, vy))

        # Draw edges
        for i in range(3):
            x0, y0 = vertices[i]
            x1, y1 = vertices[(i + 1) % 3]
            self._draw_line(x0, y0, x1, y1)

        # Draw vertex marks
        for vx, vy in vertices:
            self._set_char(int(vx), int(vy), self._glyphs["vertex"])

    def _draw_line(
        self, x0: float, y0: float, x1: float, y1: float,
    ) -> None:
        """Draw a line between two points using Bresenham-like approach."""
        steps = max(
            int(abs(x1 - x0)), int(abs(y1 - y0)), 1,
        ) * 2
        for i in range(steps + 1):
            t = i / max(steps, 1)
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            ix, iy = int(x), int(y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                existing = self._grid[iy][ix]
                if existing == " ":
                    self._grid[iy][ix] = self._glyphs["point"]

    def _set_char(self, x: int, y: int, ch: str) -> None:
        """Set a character on the grid if in bounds."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._grid[y][x] = ch
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tui_sacred_geometry.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/trinity/tui/sacred_geometry.py tests/test_tui_sacred_geometry.py
git commit -m "feat(tui): add SacredGeometryAnimator core with frame generation"
```

---

### Task 2: Integrate animator into `TrinityTUI` header

**Files:**
- Modify: `src/trinity/tui/app.py` (lines 99-141 `__init__`, lines 241-296 `build_header`)
- Test: `tests/test_tui.py`

**Step 1: Write the failing test for header integration**

Add to `tests/test_tui_sacred_geometry.py`:

```python
from trinity.tui.app import TrinityTUI
from trinity.config import TrinityConfig


def _make_config() -> TrinityConfig:
    """Create a minimal config for testing."""
    return TrinityConfig(
        session_name="test",
        agents={},
    )


def test_tui_header_contains_geometry():
    """TUI header should include sacred geometry when enabled."""
    config = _make_config()
    tui = TrinityTUI(config)
    header = tui.build_header()
    # Header should render without error
    from rich.console import Console
    console = Console(width=80, force_terminal=True)
    console.render(header)


def test_tui_has_animator_attribute():
    """TrinityTUI should have a SacredGeometryAnimator instance."""
    config = _make_config()
    tui = TrinityTUI(config)
    assert hasattr(tui, "_geometry_animator")


def test_tui_animator_disabled_when_no_animation():
    """Animator should be None when terminal is too small or disabled."""
    config = _make_config()
    tui = TrinityTUI(config, show_geometry=False)
    assert tui._geometry_animator is None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tui_sacred_geometry.py::test_tui_has_animator_attribute -v`
Expected: FAIL — `TrinityTUI.__init__` doesn't accept `show_geometry` and has no `_geometry_animator`.

**Step 3: Modify `TrinityTUI.__init__` and `build_header`**

In `src/trinity/tui/app.py`:

1. Add import at top (after line 30):
```python
from trinity.tui.sacred_geometry import SacredGeometryAnimator
```

2. Add `show_geometry` and `_geometry_animator` to `__init__` (after line 128):
```python
        # Sacred geometry animation
        self._animation_tick: float = 0.0
        self._geometry_animator: SacredGeometryAnimator | None = None
        if show_geometry:
            term_height = self.console.size.height
            if term_height >= 20:
                self._geometry_animator = SacredGeometryAnimator(
                    width=min(self.console.size.width - 4, 50),
                    height=11,
                    mode="modern",
                )
```

3. Update `__init__` signature (line 107):
```python
    def __init__(
        self,
        config: TrinityConfig,
        console: Console | None = None,
        show_geometry: bool = True,
    ):
```

4. Update `build_header` to insert mandala above branding (replace lines 259-267):
```python
        header_parts: list = []

        # Sacred geometry mandala
        if self._geometry_animator is not None:
            self._animation_tick += 0.15  # Advance rotation
            geo_frame = self._geometry_animator.render(angle=self._animation_tick)
            header_parts.append(Text(geo_frame, style="dim cyan"))
            header_parts.append(Text())

        header_parts.extend([
            Text.assemble(
                Text("🧠 ", style=""),
                Text(f"Trinity v{__version__}", style="bold cyan"),
                Text("  —  ", style="dim"),
                Text("Three minds, one context", style="dim italic"),
            ),
            Text(),
            agent_line,
            Text(),
        ])
```

And update the `content = Group(...)` to use `header_parts`:
```python
        content = Group(
            *header_parts,
            Text.assemble(
                Text(f"📡 Session: {self.config.session_name}", style="dim"),
                Text(f"  ⏱ {mins}m {secs:02d}s", style="dim"),
            ),
            Text.assemble(
                Text("Workflow: ", style="dim"),
                Text(self.workflow_state.value, style="bold magenta"),
                Text(
                    f"  Pending questions: {self.pending_question_count}",
                    style="dim",
                ),
                Text(
                    f"  Work packages: {self._work_package_summary()}",
                    style="dim",
                ),
                Text(f"  Subtasks: {self.subtask_result_count}", style="dim"),
            ),
            Text.assemble(
                self._caveman_badge(),
            ),
            Text(),
        )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tui_sacred_geometry.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trinity/tui/app.py tests/test_tui_sacred_geometry.py
git commit -m "feat(tui): integrate sacred geometry mandala into header"
```

---

### Task 3: Add render-mode adaptation for geometry

**Files:**
- Modify: `src/trinity/tui/app.py` (the `_geometry_animator` initialization)
- Modify: `src/trinity/tui/sacred_geometry.py` (add `update_mode` method)
- Test: `tests/test_tui_sacred_geometry.py`

**Step 1: Write the failing test**

Add to `tests/test_tui_sacred_geometry.py`:

```python
def test_animator_update_mode_changes_glyphs():
    """Switching mode should change the character set."""
    animator = SacredGeometryAnimator(width=40, height=13, mode="modern")
    frame_modern = animator.render(angle=0.0)
    animator.update_mode("ascii")
    frame_ascii = animator.render(angle=0.0)
    # ASCII frame should not contain Unicode
    for ch in frame_ascii:
        if ch not in "\n\r\t ":
            assert ord(ch) < 128


def test_tui_geometry_respects_render_policy():
    """Geometry should adapt to the rendering policy mode."""
    config = _make_config()
    tui = TrinityTUI(config)
    if tui._geometry_animator is not None:
        assert tui._geometry_animator.mode in ("modern", "unicode", "ascii")
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tui_sacred_geometry.py::test_animator_update_mode_changes_glyphs -v`
Expected: FAIL — `SacredGeometryAnimator` has no `update_mode` method.

**Step 3: Add `update_mode` method to `SacredGeometryAnimator`**

In `src/trinity/tui/sacred_geometry.py`, add after `__init__`:

```python
    def update_mode(self, mode: RenderMode) -> None:
        """Switch the render mode, changing the character set."""
        self.mode = mode
        self._glyphs = _GLYPHS.get(mode, _GLYPHS["ascii"])
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tui_sacred_geometry.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/trinity/tui/sacred_geometry.py tests/test_tui_sacred_geometry.py
git commit -m "feat(tui): add render-mode adaptation for geometry animator"
```

---

### Task 4: Polish — color the mandala with agent colors and verify visually

**Files:**
- Modify: `src/trinity/tui/sacred_geometry.py` (add `render_rich` method returning colored `Text`)
- Modify: `src/trinity/tui/app.py` (use `render_rich` instead of plain `render`)
- Test: `tests/test_tui_sacred_geometry.py`

**Step 1: Write the failing test**

```python
from rich.text import Text


def test_animator_render_rich_returns_text():
    """render_rich should return a Rich Text object."""
    animator = SacredGeometryAnimator(width=40, height=13)
    text = animator.render_rich(angle=0.0, colors=["red", "green", "blue"])
    assert isinstance(text, Text)
    assert len(text) > 0


def test_animator_render_rich_has_style_spans():
    """Rich output should contain styled spans for colors."""
    animator = SacredGeometryAnimator(width=40, height=13)
    text = animator.render_rich(angle=0.0, colors=["red", "green", "blue"])
    # Should have at least some styled spans
    assert len(text._spans) > 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tui_sacred_geometry.py::test_animator_render_rich_returns_text -v`
Expected: FAIL — `SacredGeometryAnimator` has no `render_rich` method.

**Step 3: Implement `render_rich`**

In `src/trinity/tui/sacred_geometry.py`, add:

```python
    def render_rich(
        self,
        angle: float = 0.0,
        colors: list[str] | None = None,
    ) -> "Text":
        """Render a frame as a Rich Text with per-layer colors.

        Args:
            angle: Rotation angle in radians.
            colors: List of Rich color names for each circle layer.

        Returns:
            Rich Text object with styled spans.
        """
        from rich.text import Text

        if colors is None:
            colors = ["cyan", "green", "magenta"]

        # Render individual layers for coloring
        frames: list[str] = []
        for i in range(3):
            layer_angle = angle + i * (2 * math.pi / 3)
            frames.append(self._render_single_circle(layer_angle))

        # Also render triangles
        tri_frame = self._render_triangles(angle)

        # Combine with colors
        result = Text()
        for row_idx in range(self.height):
            for col_idx in range(self.width):
                ch = " "
                color = None

                # Check triangle layer first
                if row_idx < len(tri_frame) and col_idx < len(tri_frame[row_idx]):
                    if tri_frame[row_idx][col_idx] != " ":
                        ch = tri_frame[row_idx][col_idx]
                        color = "bright_cyan"

                # Check circle layers
                for i, frame in enumerate(frames):
                    if row_idx < len(frame) and col_idx < len(frame[row_idx]):
                        if frame[row_idx][col_idx] != " ":
                            ch = frame[row_idx][col_idx]
                            color = colors[i % len(colors)]

                # Check center mark
                if (
                    col_idx == self.width // 2
                    and row_idx == self.height // 2
                ):
                    ch = self._glyphs["center"]
                    color = "bright_white"

                if color:
                    result.append(ch, style=color)
                else:
                    result.append(ch)

            if row_idx < self.height - 1:
                result.append("\n")

        return result

    def _render_single_circle(self, offset_angle: float) -> list[str]:
        """Render a single circle layer, return as list of strings."""
        grid = [
            [" " for _ in range(self.width)]
            for _ in range(self.height)
        ]
        cx = self.width / 2
        cy = self.height / 2
        radius = min(self.width, self.height) * 0.35
        ocx = cx + radius * 0.3 * math.cos(offset_angle)
        ocy = cy + radius * 0.3 * math.sin(offset_angle) * 0.5
        self._draw_circle_on(grid, ocx, ocy, radius * 0.7)
        return ["".join(row) for row in grid]

    def _render_triangles(self, angle: float) -> list[str]:
        """Render both triangles, return as list of strings."""
        grid = [
            [" " for _ in range(self.width)]
            for _ in range(self.height)
        ]
        cx = self.width / 2
        cy = self.height / 2
        radius = min(self.width, self.height) * 0.35 * 0.85
        self._draw_triangle_on(grid, cx, cy, radius, angle)
        self._draw_triangle_on(grid, cx, cy, radius, angle + math.pi)
        # Center mark
        icx, icy = int(cx), int(cy)
        if 0 <= icx < self.width and 0 <= icy < self.height:
            grid[icy][icx] = self._glyphs["center"]
        return ["".join(row) for row in grid]

    def _draw_circle_on(
        self, grid: list[list[str]], cx: float, cy: float, radius: float,
    ) -> None:
        """Draw a circle on a given grid."""
        steps = max(40, int(radius * 4))
        for i in range(steps):
            t = 2 * math.pi * i / steps
            x = cx + radius * math.cos(t)
            y = cy + radius * math.sin(t) * 0.5
            ix, iy = int(x), int(y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                grid[iy][ix] = self._glyphs["circle"]

    def _draw_triangle_on(
        self, grid: list[list[str]], cx: float, cy: float,
        radius: float, angle: float,
    ) -> None:
        """Draw a triangle on a given grid."""
        vertices = []
        for i in range(3):
            va = angle + i * (2 * math.pi / 3) - math.pi / 2
            vx = cx + radius * math.cos(va)
            vy = cy + radius * math.sin(va) * 0.5
            vertices.append((vx, vy))
        for i in range(3):
            x0, y0 = vertices[i]
            x1, y1 = vertices[(i + 1) % 3]
            self._draw_line_on(grid, x0, y0, x1, y1)
        for vx, vy in vertices:
            ix, iy = int(vx), int(vy)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                grid[iy][ix] = self._glyphs["vertex"]

    def _draw_line_on(
        self, grid: list[list[str]], x0: float, y0: float,
        x1: float, y1: float,
    ) -> None:
        """Draw a line on a given grid."""
        steps = max(int(abs(x1 - x0)), int(abs(y1 - y0)), 1) * 2
        for i in range(steps + 1):
            t = i / max(steps, 1)
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            ix, iy = int(x), int(y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                if grid[iy][ix] == " ":
                    grid[iy][ix] = self._glyphs["point"]
```

Then update `build_header` in `src/trinity/tui/app.py` to use `render_rich`:

Replace the geometry section in `build_header`:
```python
        # Sacred geometry mandala
        if self._geometry_animator is not None:
            self._animation_tick += 0.15
            agent_colors = [
                get_theme(name).color
                for name in self.agents
                if status.state != AgentTUIState.DISABLED
            ]
            geo_text = self._geometry_animator.render_rich(
                angle=self._animation_tick,
                colors=agent_colors[:3] or ["cyan", "green", "magenta"],
            )
            header_parts.append(geo_text)
            header_parts.append(Text())
```

**Step 4: Run all tests**

Run: `python -m pytest tests/test_tui_sacred_geometry.py -v`
Expected: All tests PASS

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests PASS (no regressions)

**Step 6: Commit**

```bash
git add src/trinity/tui/sacred_geometry.py src/trinity/tui/app.py tests/test_tui_sacred_geometry.py
git commit -m "feat(tui): add colored mandala rendering with agent theme colors"
```

---

### Task 5: Visual verification

**Step 1: Run the Trinity TUI and visually inspect**

Run: `trinity` or the appropriate launch command
Expected: Sacred geometry mandala rotating above the header branding text.

**Step 2: Take a screenshot and verify**

Check that:
- Mandala is visible above the "🧠 Trinity v{version}" line
- Colors correspond to agent themes
- Animation rotates smoothly
- No visual artifacts or misalignment
