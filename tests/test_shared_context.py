"""Tests for trinity.context.shared.SharedContextEngine."""

import pytest
from pathlib import Path

from trinity.context.shared import SharedContextEngine


class TestSharedContextEngine:
    def test_initialize(self, shared_engine):
        shared_engine.initialize("Build an auth system", ["claude", "codex"])
        content = shared_engine.read()
        assert "Build an auth system" in content
        assert "claude" in content
        assert "codex" in content

    def test_read_section(self, shared_engine):
        shared_engine.initialize("Test goal", ["claude"])
        section = shared_engine.read_section("Current Goal")
        assert section is not None
        assert "Test goal" in section

    def test_read_section_not_found(self, shared_engine):
        shared_engine.initialize("Test", ["claude"])
        section = shared_engine.read_section("Nonexistent Section")
        assert section is None

    def test_write_section_new(self, shared_engine):
        shared_engine.initialize("Test", ["claude"])
        shared_engine.write_section("Architecture", "Use microservices")
        section = shared_engine.read_section("Architecture")
        assert "Use microservices" in section

    def test_write_section_replace(self, shared_engine):
        shared_engine.initialize("Original goal", ["claude"])
        shared_engine.write_section("Current Goal", "Updated goal")
        section = shared_engine.read_section("Current Goal")
        assert "Updated goal" in section
        assert "Original goal" not in section

    def test_append_opinion(self, shared_engine):
        shared_engine.initialize("Test", ["claude", "codex"])
        shared_engine.append_opinion("claude", 1, "JWT is best")
        shared_engine.append_opinion("codex", 1, "Sessions are better")

        section = shared_engine.read_section("Round 1 Opinions")
        assert "claude" in section
        assert "JWT is best" in section
        assert "codex" in section
        assert "Sessions are better" in section

    def test_update_consensus(self, shared_engine):
        shared_engine.initialize("Test", ["claude"])
        shared_engine.update_consensus("Use JWT + refresh tokens")
        section = shared_engine.read_section("Agreed Conclusion")
        assert "JWT + refresh tokens" in section

    def test_update_tasks(self, shared_engine):
        shared_engine.initialize("Test", ["claude", "codex"])
        shared_engine.update_tasks({
            "claude": "Design middleware",
            "codex": "Implement endpoints",
        })
        section = shared_engine.read_section("Task Assignment")
        assert "claude" in section
        assert "Design middleware" in section
        assert "codex" in section

    def test_append_session_summary(self, shared_engine):
        shared_engine.initialize("Test", ["claude"])
        shared_engine.append_session_summary("claude", "Completed auth middleware")

        section = shared_engine.read_section("Session History")
        assert "claude" in section
        assert "Completed auth middleware" in section

    def test_get_context_for_rotation(self, shared_engine):
        shared_engine.initialize("Original goal", ["claude"])
        shared_engine.append_opinion("claude", 1, "Opinion 1")
        shared_engine.append_opinion("claude", 2, "Opinion 2")
        shared_engine.update_consensus("Final decision")

        context = shared_engine.get_context_for_rotation(recent_rounds=1)
        # Should contain pinned sections
        assert "Original goal" in context
        assert "Final decision" in context
        # Should contain only the most recent round
        assert "Opinion 2" in context

    def test_empty_file(self, tmp_path):
        engine = SharedContextEngine(path=tmp_path / "shared.md")
        assert engine.read() == ""
        assert engine.read_section("anything") is None

    def test_multiple_sections(self, shared_engine):
        shared_engine.initialize("Test", ["claude"])
        shared_engine.write_section("Section A", "Content A")
        shared_engine.write_section("Section B", "Content B")

        assert shared_engine.read_section("Section A") is not None
        assert shared_engine.read_section("Section B") is not None
