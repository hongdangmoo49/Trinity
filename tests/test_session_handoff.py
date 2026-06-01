"""Tests for session handoff — keep_sections preservation during rotation."""

import pytest
from pathlib import Path

from trinity.context.shared import SharedContextEngine


@pytest.fixture
def engine(tmp_path):
    return SharedContextEngine(
        path=tmp_path / "shared.md",
        keep_sections=["## Current Goal", "## Agreed Conclusion"],
    )


class TestKeepSectionsPreservation:
    def test_pinned_sections_in_rotation_context(self, engine):
        engine.initialize("Build auth system", ["claude", "codex"])
        engine.append_opinion("claude", 1, "Use JWT.")
        engine.append_opinion("codex", 1, "Use sessions.")
        engine.update_consensus("Use JWT + refresh tokens")

        context = engine.get_context_for_rotation(recent_rounds=1)

        # Pinned sections must be present
        assert "Build auth system" in context
        assert "JWT + refresh tokens" in context

    def test_recent_rounds_in_rotation_context(self, engine):
        engine.initialize("Test goal", ["claude"])
        engine.append_opinion("claude", 1, "Round 1 opinion")
        engine.append_opinion("claude", 2, "Round 2 opinion")
        engine.append_opinion("claude", 3, "Round 3 opinion")

        # Only recent 2 rounds should be included
        context = engine.get_context_for_rotation(recent_rounds=2)
        assert "Round 3 opinion" in context
        assert "Round 2 opinion" in context
        # Round 1 should NOT be included (only recent 2)
        assert "Round 1 opinion" not in context

    def test_session_history_in_rotation_context(self, engine):
        engine.initialize("Test goal", ["claude"])
        engine.append_session_summary("claude", "Previous session summary here.")

        context = engine.get_context_for_rotation(recent_rounds=3)
        assert "Previous session summary" in context

    def test_empty_rotation_context(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        context = engine.get_context_for_rotation()
        # Should return empty or minimal content
        assert isinstance(context, str)

    def test_all_pinned_sections_preserved(self, engine):
        engine.initialize("Goal A", ["claude"])
        engine.write_section("New Section", "Some content")
        engine.update_consensus("Final decision")

        context = engine.get_context_for_rotation(recent_rounds=0)

        # Current Goal and Agreed Conclusion are pinned
        assert "Goal A" in context
        assert "Final decision" in context
        # Non-pinned section may or may not be included
