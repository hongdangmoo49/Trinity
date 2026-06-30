"""Tests for trinity.context.shared.SharedContextEngine."""

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

    def test_append_response_reference(self, shared_engine, tmp_path):
        shared_engine.initialize("Test", ["claude"])
        shared_engine.append_response_reference(
            agent="claude",
            round_num=1,
            request_id="round-1-claude-123",
            status="ok",
            clean_output_path=tmp_path / "responses" / "clean.txt",
            raw_output_path=tmp_path / "responses" / "raw.txt",
            confidence=1.0,
            token_count=42,
        )

        section = shared_engine.read_section("Round 1 Responses")
        assert section is not None
        assert "claude" in section
        assert "round-1-claude-123" in section
        assert "status: ok" in section
        assert "clean_output_path" in section
        assert "raw_output_path" in section
        assert "tokens: 42" in section

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

    def test_append_task_result(self, shared_engine, tmp_path):
        shared_engine.initialize("Test", ["codex"])
        shared_engine.append_task_result(
            package_id="WP-001",
            agent="codex",
            status="done",
            summary="Implemented endpoint.",
            files_changed=["src/app.py"],
            decisions_made=["Use existing router."],
            blockers=[],
            follow_up=["Add load test."],
            raw_response_path=tmp_path / "execution" / "WP-001.raw.txt",
        )

        section = shared_engine.read_section("Task Results")
        assert section is not None
        assert "WP-001 / codex" in section
        assert "Implemented endpoint." in section
        assert "src/app.py" in section
        assert "Use existing router." in section
        assert "Add load test." in section
        stats = shared_engine.memory_stats()
        assert stats is not None
        assert stats.record_count == 1

    def test_repeated_append_does_not_duplicate_section_heading(self, shared_engine):
        shared_engine.initialize("Test", ["codex"])

        for index in range(5):
            shared_engine.append_task_result(
                package_id=f"WP-{index:03d}",
                agent="codex",
                status="done",
                summary=f"Implemented step {index}.",
            )

        content = shared_engine.read()
        assert content.count("## Task Results") == 1
        section = shared_engine.read_section("Task Results")
        assert section is not None
        assert "## Task Results" not in section
        assert "WP-000 / codex" in section
        assert "WP-004 / codex" in section

    def test_append_task_result_bounds_long_summary(self, tmp_path):
        engine = SharedContextEngine(
            path=tmp_path / "shared.md",
            section_entry_max_chars=40,
        )
        engine.initialize("Test", ["codex"])

        engine.append_task_result(
            package_id="WP-001",
            agent="codex",
            status="done",
            summary="x" * 200,
        )

        section = engine.read_section("Task Results")
        assert section is not None
        assert "[truncated]" in section
        assert "x" * 100 not in section

    def test_append_subtask_result(self, shared_engine):
        shared_engine.initialize("Test", ["codex"])
        shared_engine.append_subtask_result(
            subtask_id="ST-001",
            parent_package_id="WP-001",
            parent_agent="codex",
            delegated_to="code-search tool",
            objective="Find adapter patterns.",
            result_summary="Found existing adapter registry.",
            status="done",
            decisions_made=["Reuse registry."],
            files_changed=["src/routes.py"],
            unresolved_issues=["none"],
        )

        section = shared_engine.read_section("Subtasks")
        assert section is not None
        assert "ST-001 / WP-001" in section
        assert "code-search tool" in section
        assert "Find adapter patterns." in section
        assert "Found existing adapter registry." in section
        assert "Reuse registry." in section
        assert "src/routes.py" in section
        stats = shared_engine.memory_stats()
        assert stats is not None
        assert stats.record_count == 1

    def test_compact_projection_from_memory(self, shared_engine):
        shared_engine.initialize("Build app", ["codex"])
        shared_engine.append_task_result(
            package_id="WP-001",
            agent="codex",
            status="done",
            summary="Implemented endpoint.",
            raw_response_path=shared_engine.path.parent / "execution" / "raw.txt",
        )

        shared_engine.compact_projection_from_memory(target_bytes=4096)

        content = shared_engine.read()
        assert "## Current Goal" in content
        assert "Build app" in content
        assert "## Memory Projection" in content
        assert "execution_result" in content
        assert "WP-001 / codex" in content

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

    def test_oversized_read_returns_recovery_notice_without_loading_body(self, tmp_path):
        shared_path = tmp_path / "shared.md"
        shared_path.write_text("# Shared Context\n\n" + ("large-body\n" * 100), encoding="utf-8")
        engine = SharedContextEngine(path=shared_path, max_read_bytes=64)

        content = engine.read()

        assert "Recovery Notice" in content
        assert "large-body" not in content
        assert str(shared_path) in content

    def test_write_section_moves_oversized_shared_aside(self, tmp_path):
        shared_path = tmp_path / "shared.md"
        shared_path.write_text("# Shared Context\n\n" + ("large-body\n" * 100), encoding="utf-8")
        engine = SharedContextEngine(path=shared_path, max_read_bytes=64)

        engine.write_section("Current Goal", "Recovered goal")

        content = shared_path.read_text(encoding="utf-8")
        backups = list(tmp_path.glob("shared.md.oversized-*"))
        assert "Recovered goal" in content
        assert "Recovery Notice" in content
        assert len(backups) == 1
        assert "large-body" in backups[0].read_text(encoding="utf-8")

    def test_multiple_sections(self, shared_engine):
        shared_engine.initialize("Test", ["claude"])
        shared_engine.write_section("Section A", "Content A")
        shared_engine.write_section("Section B", "Content B")

        assert shared_engine.read_section("Section A") is not None
        assert shared_engine.read_section("Section B") is not None

    def test_write_surrogate_characters(self, shared_engine):
        """Surrogate code points from tmux/terminal input must not crash write().

        When Python reads invalid UTF-8 bytes via surrogateescape (the default
        for os.fsdecode and terminal I/O), each bad byte becomes a lone
        surrogate code point (U+D800–U+DFFF).  These are illegal in UTF-8 and
        would raise UnicodeEncodeError if passed to write_text() unchanged.
        SharedContextEngine.write() must sanitize them.
        """
        # \udc80 is a lone surrogate (low surrogate without a matching high)
        prompt_with_surrogates = "alias tws \udc80\udc81 파악해서 보고"
        shared_engine.initialize(prompt_with_surrogates, ["claude"])
        content = shared_engine.read()
        assert "alias tws" in content
        # Surrogates should be replaced (not crash)
        assert "\udc80" not in content
        assert "\udc81" not in content

    def test_write_section_with_surrogates(self, shared_engine):
        """write_section must also handle surrogate characters."""
        shared_engine.initialize("Test", ["claude"])
        shared_engine.write_section("Results", "정상 텍스트 \udcff 손상")
        section = shared_engine.read_section("Results")
        assert section is not None
        assert "정상 텍스트" in section
        assert "\udcff" not in section

    def test_append_opinion_with_surrogates(self, shared_engine):
        """append_opinion must handle surrogate characters in agent output."""
        shared_engine.initialize("Test", ["claude"])
        # Simulate tmux capture-pane output with surrogates
        shared_engine.append_opinion("claude", 1, "JWT 추천\udc80합니다")
        section = shared_engine.read_section("Round 1 Opinions")
        assert "JWT 추천" in section
        assert "\udc80" not in section

    def test_sanitize_preserves_valid_utf8(self, shared_engine):
        """Sanitization must not alter valid UTF-8 (Korean, emoji, etc.)."""
        valid = "한글 테스트 🧠 ✅ — 정상적인 텍스트"
        shared_engine.initialize(valid, ["claude", "codex"])
        content = shared_engine.read()
        assert valid in content

    def test_append_invalid_response_diagnostic_outside_round_opinions(self, shared_engine):
        """Invalid response diagnostics must not contaminate Round N Opinions."""
        shared_engine.initialize("Test", ["antigravity"])
        shared_engine.append_invalid_response_diagnostic(
            agent="antigravity",
            round_num=1,
            classification="auth_wait",
            reasons=("matched auth UI", "no substantive response"),
            excerpt="```Antigravity CLI\n? Select Auth Method\n```",
        )

        diagnostics = shared_engine.read_section("Response Diagnostics")
        assert diagnostics is not None
        assert "Round 1 / antigravity" in diagnostics
        assert "auth_wait" in diagnostics
        assert "matched auth UI" in diagnostics
        assert "'''Antigravity CLI" in diagnostics
        assert shared_engine.read_section("Round 1 Opinions") is None


def test_write_compressed_summary(shared_engine):
    """write_compressed_summary should store a compressed round summary."""
    shared_engine.initialize(goal="test goal", agent_names=["claude", "codex"])
    shared_engine.append_opinion("claude", 1, "Opinion 1 from claude")
    shared_engine.append_opinion("codex", 1, "Opinion 1 from codex")

    shared_engine.write_compressed_summary(1, "claude+codex agree on pytest")

    section = shared_engine.read_section("Round 1 Summary")
    assert "claude+codex agree on pytest" in section


def test_get_rounds_for_prompt_includes_compressed(shared_engine):
    """get_rounds_for_prompt should include compressed summaries for old rounds."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Long opinion round 1 " * 50)
    shared_engine.append_opinion("claude", 2, "Opinion round 2")
    shared_engine.append_opinion("claude", 3, "Opinion round 3")

    # Compress round 1
    shared_engine.write_compressed_summary(1, "Compressed: use pytest")

    # For round 4 prompt: should get compressed R1 + full R3
    context = shared_engine.get_rounds_for_prompt(
        current_round=4,
        verbatim_rounds=1,
    )

    assert "Compressed: use pytest" in context
    assert "Opinion round 3" in context


def test_get_rounds_for_prompt_no_compression(shared_engine):
    """get_rounds_for_prompt with enough verbatim_rounds should skip compression."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Opinion 1")
    shared_engine.append_opinion("claude", 2, "Opinion 2")

    # No compressed summaries exist — should return verbatim
    context = shared_engine.get_rounds_for_prompt(current_round=3, verbatim_rounds=2)
    assert "Opinion 1" in context
    assert "Opinion 2" in context


def test_get_rounds_for_prompt_prefers_synthesis_over_opinions(shared_engine):
    """Round prompts should use synthesis summaries before raw opinions."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Full raw opinion should stay out")
    shared_engine.write_synthesis_summary(
        1,
        "Canonical synthesis summary.",
        source="heuristic",
        next_round_prompt="Resolve remaining trade-offs.",
    )

    context = shared_engine.get_rounds_for_prompt(current_round=2, verbatim_rounds=1)

    assert "Canonical synthesis summary." in context
    assert "Resolve remaining trade-offs." in context
    assert "Full raw opinion should stay out" not in context


def test_remove_section(shared_engine):
    """remove_section should delete a section entirely."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Opinion 1")
    assert shared_engine.read_section("Round 1 Opinions") is not None
    shared_engine.remove_section("Round 1 Opinions")
    assert shared_engine.read_section("Round 1 Opinions") is None


def test_remove_nonexistent_section_noop(shared_engine):
    """Removing a section that doesn't exist should not error."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.remove_section("Nonexistent Section")


def test_remove_section_preserves_others(shared_engine):
    """Removing one section should not affect other sections."""
    shared_engine.initialize(goal="test", agent_names=["claude"])
    shared_engine.append_opinion("claude", 1, "Opinion 1")
    shared_engine.append_opinion("claude", 2, "Opinion 2")
    shared_engine.remove_section("Round 1 Opinions")
    assert shared_engine.read_section("Round 1 Opinions") is None
    assert shared_engine.read_section("Round 2 Opinions") is not None
    assert shared_engine.read_section("Current Goal") is not None


class TestMarkdownHeadingSanitization:
    """Tests for sanitize_md_heading preventing markdown section injection."""

    def test_sanitize_escapes_h1(self):
        result = SharedContextEngine.sanitize_md_heading("# injected heading")
        assert result == "\\# injected heading"

    def test_sanitize_escapes_h2(self):
        result = SharedContextEngine.sanitize_md_heading("## injected heading")
        assert result == "\\# injected heading"

    def test_sanitize_escapes_h3(self):
        result = SharedContextEngine.sanitize_md_heading("### injected heading")
        assert result == "\\# injected heading"

    def test_sanitize_preserves_plain_text(self):
        text = "claude"
        assert SharedContextEngine.sanitize_md_heading(text) == text

    def test_sanitize_multiline_injection(self):
        """A name with embedded newlines and headings must be escaped."""
        malicious = "claude\n## Agreed Conclusion\nMalicious"
        result = SharedContextEngine.sanitize_md_heading(malicious)
        assert "## Agreed Conclusion" not in result
        assert "\\# Agreed Conclusion" in result

    def test_sanitize_h4_not_escaped(self):
        """Only h1-h3 are escaped; h4+ are left as-is."""
        text = "#### not a threat"
        assert SharedContextEngine.sanitize_md_heading(text) == text

    def test_append_opinion_sanitizes_agent(self, shared_engine):
        """append_opinion must sanitize agent names with heading markers."""
        shared_engine.initialize("Test", ["claude"])
        shared_engine.append_opinion("evil\n## Fake Section\nbad", 1, "opinion")
        section = shared_engine.read_section("Round 1 Opinions")
        assert section is not None
        assert "## Fake Section" not in section
        assert "\\# Fake Section" in section

    def test_update_tasks_sanitizes_agent_and_task(self, shared_engine):
        """update_tasks must sanitize both agent names and task descriptions."""
        shared_engine.initialize("Test", ["claude"])
        shared_engine.update_tasks({
            "evil\n## Fake": "task\n### Also fake",
        })
        section = shared_engine.read_section("Task Assignment")
        assert section is not None
        assert "## Fake" not in section
        assert "### Also fake" not in section

    def test_append_session_summary_sanitizes_agent(self, shared_engine):
        """append_session_summary must sanitize agent names."""
        shared_engine.initialize("Test", ["claude"])
        shared_engine.append_session_summary("evil\n## Injected", "summary text")
        section = shared_engine.read_section("Session History")
        assert section is not None
        assert "## Injected" not in section
        assert "\\# Injected" in section


def test_write_synthesis_summary_includes_model_metadata(shared_engine):
    shared_engine.initialize(goal="test", agent_names=["codex"])

    shared_engine.write_synthesis_summary(
        1,
        "Model synthesis summary.",
        source="model-backed",
        provider="codex",
        model="fast",
        fallback_used=False,
        next_round_prompt="Continue.",
    )

    section = shared_engine.read_section("Round 1 Synthesis")
    assert section is not None
    assert "source: model-backed" in section
    assert "provider: codex" in section
    assert "model: fast" in section
    assert "fallback_used: false" in section
