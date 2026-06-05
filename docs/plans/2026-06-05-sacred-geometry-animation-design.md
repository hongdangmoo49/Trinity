# Sacred Geometry ASCII Animation — Design

**Date**: 2026-06-05
**Status**: Approved
**Target**: Rich TUI header area

## Goal

Add a rotating sacred geometry mandala animation to the Trinity Rich TUI header,
reinforcing the "Three minds, one context" brand with a visually striking ASCII
art animation.

## Architecture

### New Module: `src/trinity/tui/sacred_geometry.py`

- `SacredGeometryAnimator` class
  - Generates frames dynamically using trigonometric math
  - Renders overlapping circles, triangles, hexagons rotating
  - Center mark (✦) symbolizing consensus
  - Adapts to render policy (modern/unicode/ascii)
- Frame generation is math-based (no pre-rendered frames)
- Integrates with existing `TUIRenderingPolicy` for character adaptation

### Integration Point: `src/trinity/tui/app.py`

- `build_header()` method updated to include mandala above branding
- Animation tick tied to Rich Live refresh cycle (4-8 FPS)
- `TrinityTUI._tick` advances the animation angle

### Character Sets per Render Mode

| Mode | Geometry chars | Center |
|------|---------------|--------|
| Modern | ✦ ◆ │ ╲ ╱ ─ · | ✦ |
| Unicode | ◆ │ ╲ ╱ ─ · | ◆ |
| ASCII | + \| / \ - . | * |

### Visual Layout

```
            .  ·  ✦  ·  .
         ·  ╱╲    ╱╲    ╱╲  ·
        ╱  ╲  ╲╱  ╲╱  ╱  ╲
      ╱ ── ╲   ✦   ╱ ── ╲
     ╱______╲  │  ╱______╲
      \    /   │   \    /
       \  / ── ✦ ── \  /
        \/       \/

   🧠 Trinity v0.10.1 — Three minds, one context
```

- Three overlapping circles (3 agents)
- Rotating equilateral triangles
- Central convergence point (consensus)
- Colors: agent theme colors (Claude=red, Codex=green, Antigravity=blue)

## Constraints

- Must degrade gracefully in ASCII/plain modes
- Terminal height < 20 rows → auto-hide animation
- `--no-animation` flag to disable
- No external dependencies beyond Rich
- Frame generation must be fast (<1ms per frame)

## Testing

- Unit tests for frame generation math
- Render mode adaptation tests
- Terminal height threshold tests
