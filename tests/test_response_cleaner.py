"""Tests for ResponseCleaner — CLI splash/banner stripping from agent output."""

from trinity.agents.response_cleaner import ResponseCleaner, ResponseValidator


class TestSplashRemoval:
    """CLI splash screens and banners are removed."""

    def test_claude_splash_art(self):
        raw = (
            "Welcome back!\n"
            "  ▐▛███▜▌\n"
            "  ▝▜█████▛▘\n"
            "GLM-5.1[1m] with high effort\n"
            "API Usage   Billing\n"
            "Read the shared context below for background.\n"
            "User's request: hello\n"
            "This is the actual response from Claude."
        )
        cleaned = ResponseCleaner.clean(raw)
        assert "actual response from Claude" in cleaned
        assert "Welcome back!" not in cleaned
        assert "▐▛███▜▌" not in cleaned
        assert "GLM-5.1" not in cleaned
        assert "API Usage" not in cleaned
        assert "Read the shared context" not in cleaned

    def test_codex_banner(self):
        raw = (
            ">_ OpenAI Codex (v0.136.0)\n"
            "model:     gpt-5.5 xhigh   /model to change\n"
            "directory: /home/user/workspace/Trinity\n"
            "Tip: GPT-5.5 is now available. It's our strongest agentic coding model yet, "
            "built to reason through large codebases, check assumptions with tools, "
            "and keep going until the work is done.\n"
            "\n"
            "The actual Codex response goes here."
        )
        cleaned = ResponseCleaner.clean(raw)
        assert "actual Codex response" in cleaned
        assert "OpenAI Codex" not in cleaned
        assert "gpt-5.5" not in cleaned
        assert "/model to change" not in cleaned
        assert "Tip:" not in cleaned

    def test_gemini_migration_notice(self):
        raw = (
            "Gemini CLI now available.\n"
            "Gemini CLI will stop serving requests for Google One and unpaid tiers starting June 18th.\n"
            "Please migrate to Antigravity CLI before this date to avoid disruption to your workflow.\n"
            "https://goo.gle/gemini-cli-migration\n"
            "\n"
            "Tips for getting started:\n"
            " 1 Create GEMINI.md files to customize your interactions\n"
            " 2 /help for more information\n"
            " 3 Ask coding questions, edit code or run commands\n"
            " 4 Be specific for the best results\n"
            "shell mode enabled (esc to disable)\n"
            "\n"
            "Here is the actual Gemini response with useful information."
        )
        cleaned = ResponseCleaner.clean(raw)
        assert "actual Gemini response" in cleaned
        assert "Gemini CLI now" not in cleaned
        assert "migrate to Antigravity" not in cleaned
        assert "gemini-cli-migration" not in cleaned
        assert "Tips for" not in cleaned
        assert "shell mode enabled" not in cleaned

    def test_empty_input(self):
        assert ResponseCleaner.clean("") == ""
        assert ResponseCleaner.clean("   ") == "   "

    def test_pure_content_unchanged(self):
        """Clean content with no splash patterns passes through unchanged."""
        raw = (
            "## Architecture Design\n"
            "\n"
            "The system consists of three components:\n"
            "1. API Gateway\n"
            "2. Message Queue\n"
            "3. Database\n"
            "\n"
            "Each component handles a specific concern."
        )
        cleaned = ResponseCleaner.clean(raw)
        assert cleaned == raw.strip()


class TestBorderRemoval:
    """Decorative border lines are removed."""

    def test_rich_panel_borders(self):
        raw = (
            "╭──────────────────────╮\n"
            "│ Some content here    │\n"
            "╰──────────────────────╯\n"
            "Actual response text"
        )
        cleaned = ResponseCleaner.clean(raw)
        # Borders should be removed, content kept
        assert "Actual response text" in cleaned
        # The box-drawing chars lines should be gone
        lines = cleaned.splitlines()
        border_lines = [
            line for line in lines if "╭" in line or "╰" in line or "╯" in line
        ]
        assert len(border_lines) == 0

    def test_unicode_box_drawing(self):
        raw = "┏━━━━━━━━┓\nActual\n┗━━━━━━━━┛"
        cleaned = ResponseCleaner.clean(raw)
        assert "Actual" in cleaned


class TestBlankCollapse:
    """Consecutive blank lines are collapsed."""

    def test_multiple_blanks(self):
        raw = "Line 1\n\n\n\n\nLine 2\n\n\n\n\nLine 3"
        cleaned = ResponseCleaner.clean(raw)
        # Should have at most one blank line between content
        assert "\n\n\n" not in cleaned
        assert "Line 1" in cleaned
        assert "Line 3" in cleaned

    def test_trailing_blanks(self):
        raw = "Content\n\n\n\n"
        cleaned = ResponseCleaner.clean(raw)
        assert cleaned == "Content"


class TestMixedContent:
    """Real-world mixed output: splash + response + splash."""

    def test_splash_before_and_after_response(self):
        raw = (
            "Welcome back!\n"
            "▐▛███▜▌\n"
            "\n"
            "## Ethereum Whale Tracking Bot\n"
            "\n"
            "The architecture should use:\n"
            "1. Etherscan WebSocket API\n"
            "2. Redis for caching\n"
            "3. PostgreSQL for storage\n"
            "\n"
            "shell mode enabled (esc to disable)\n"
            "Tips for getting started:\n"
            " 1 Create GEMINI.md files"
        )
        cleaned = ResponseCleaner.clean(raw)
        assert "Ethereum Whale Tracking Bot" in cleaned
        assert "Etherscan WebSocket API" in cleaned
        assert "Welcome back!" not in cleaned
        assert "shell mode enabled" not in cleaned
        assert "Tips for" not in cleaned

    def test_codex_response_with_banner_leading(self):
        """Full codex-style output: banner -> prompt echo -> response."""
        raw = (
            ">_ OpenAI Codex (v0.136.0)\n"
            "model: gpt-5.5 xhigh /model to change\n"
            "\n"
            "Tip: GPT-5.5 is now available in Codex. It's our strongest agentic coding model yet.\n"
            "\n"
            "User's request: 이더 스캔에서 비용이 거의 없이 실시간으로 고래 추적하는 방법\n"
            "\n"
            "# Whale Tracking Architecture\n"
            "\n"
            "Use Etherscan API + WebSocket for real-time monitoring.\n"
            "Filter transactions > $100K.\n"
            "Store in Redis for deduplication."
        )
        cleaned = ResponseCleaner.clean(raw)
        assert "Whale Tracking Architecture" in cleaned
        assert "Etherscan API" in cleaned
        assert "OpenAI Codex" not in cleaned
        assert "gpt-5.5" not in cleaned


class TestCompletionMarkerAndInteractiveUiRemoval:
    """Completion markers and interactive approval UI are stripped."""

    def test_request_boundaries_removed(self):
        raw = (
            "TRINITY_REQUEST_START round-1-claude-abc123\n"
            "User's request: design the contract\n"
            "TRINITY_REQUEST_END round-1-claude-abc123\n"
            "\n"
            "Use request ids and persist raw/clean response files."
        )

        cleaned = ResponseCleaner.clean(raw)

        assert "TRINITY_REQUEST_START" not in cleaned
        assert "TRINITY_REQUEST_END" not in cleaned
        assert "Use request ids" in cleaned

    def test_marker_tail_removes_following_ui(self):
        raw = (
            "Use the existing response cleaner and keep the change scoped.\n"
            "[TRINITY_DONE]#7\n"
            "Action Required\n"
            "Enter Plan Mode\n"
            "Allow once\n"
            "Shift+Tab to accept edits"
        )

        cleaned = ResponseCleaner.clean(raw)

        assert cleaned == "Use the existing response cleaner and keep the change scoped."
        assert "[TRINITY_DONE]" not in cleaned
        assert "Action Required" not in cleaned
        assert "Allow once" not in cleaned

    def test_action_required_block_removed_without_marker(self):
        raw = (
            "Keep the final answer concise and include the executed tests.\n"
            "\n"
            "╭────────────────────────╮\n"
            "│ Action Required        │\n"
            "│ Enter Plan Mode        │\n"
            "│ ❯ Allow once           │\n"
            "│ Shift+Tab to accept edits │\n"
            "╰────────────────────────╯"
        )

        cleaned = ResponseCleaner.clean(raw)

        assert cleaned == "Keep the final answer concise and include the executed tests."
        assert "Action Required" not in cleaned
        assert "Enter Plan Mode" not in cleaned
        assert "Shift+Tab" not in cleaned

    def test_existing_normal_response_preserved(self):
        raw = (
            "I recommend preserving the current public API.\n"
            "\n"
            "Action Required: keep this sentence because it is normal content.\n"
            "The hotfix should only add defensive cleanup around terminal UI."
        )

        cleaned = ResponseCleaner.clean(raw)

        assert cleaned == raw

    def test_validation_preserves_answer_tail_after_prompt_echo(self):
        raw = (
            "Read the shared context below for background.\n"
            "User's request: fix the Gemini response cleaner\n"
            "Share your initial opinion. Be specific and concise.\n"
            "State your recommendation and key reasoning.\n"
            "Keep your response under 500 words.\n"
            "\n"
            "I recommend stripping marker tails before validation. "
            "That keeps approval UI out of shared context writes."
        )

        result = ResponseValidator.validate_opinion(raw)

        assert result.usable is True
        assert result.classification == ResponseValidator.USABLE_OPINION
        assert result.cleaned_text.startswith("I recommend stripping marker tails")
        assert "Read the shared context" not in result.cleaned_text


class TestQualityCheck:
    """The cleaner logs warnings for mostly-garbage output."""

    def test_mostly_splash_triggers_warning(self, caplog):
        """If >85% of lines are splash, a warning is logged."""
        raw = (
            "Welcome back!\n"
            "▐▛███▜▌\n"
            "GLM-5.1[1m]\n"
            "API Usage\n"
            "Billing\n"
            "Tip: stuff\n"
            "/model to change\n"
            "shell mode enabled\n"
            "Be specific\n"
            "Tips for getting started\n"
            "short"  # Only 1 meaningful line out of 12
        )
        import logging
        with caplog.at_level(logging.WARNING, logger="trinity.agents.response_cleaner"):
            cleaned = ResponseCleaner.clean(raw)
        assert "mostly boilerplate" in caplog.text or "short" in cleaned


class TestResponseValidation:
    """Opinion validation rejects CLI state and prompt echo before shared.md writes."""

    def test_usable_opinion(self):
        raw = (
            "I recommend using FastAPI with PostgreSQL for this service. "
            "It keeps the implementation small, supports async I/O, and leaves "
            "room for background workers if ingestion grows."
        )

        result = ResponseValidator.validate_opinion(raw)

        assert result.usable is True
        assert result.classification == ResponseValidator.USABLE_OPINION
        assert result.cleaned_text == raw

    def test_short_oauth_opinion_is_usable(self):
        result = ResponseValidator.validate_opinion("Use OAuth.")

        assert result.usable is True
        assert result.classification == ResponseValidator.USABLE_OPINION

    def test_gemini_auth_ui_is_invalid(self):
        raw = (
            "Gemini CLI\n"
            "? Select Auth Method\n"
            "❯ Login with Google\n"
            "Open the following URL to sign in:\n"
            "https://accounts.google.com/o/oauth2/auth\n"
            "Waiting for authentication..."
        )

        result = ResponseValidator.validate_opinion(raw)

        assert result.usable is False
        assert result.classification == ResponseValidator.AUTH_WAIT
        assert "Select Auth Method" in result.raw_excerpt

    def test_gemini_thinking_ui_is_invalid(self):
        raw = "✦ Thinking...\nProcessing request...\nPress Esc to interrupt"

        result = ResponseValidator.validate_opinion(raw)

        assert result.usable is False
        assert result.classification == ResponseValidator.THINKING_UI

    def test_codex_model_loading_ui_is_invalid(self):
        raw = (
            ">_ OpenAI Codex (v0.136.0)\n"
            "model: gpt-5.5 xhigh /model to change\n"
            "Loading model gpt-5.5...\n"
            "Preparing workspace..."
        )

        result = ResponseCleaner.validate_opinion(raw)

        assert result.usable is False
        assert result.classification == ResponseValidator.MODEL_LOADING

    def test_claude_prompt_echo_is_invalid(self):
        raw = (
            "Read the shared context below for background.\n"
            "User's request: Build an auth system\n"
            "Share your initial opinion. Be specific and concise.\n"
            "State your recommendation and key reasoning.\n"
            "Keep your response under 500 words."
        )

        result = ResponseValidator.validate_opinion(raw)

        assert result.usable is False
        assert result.classification == ResponseValidator.PROMPT_ECHO

    def test_shared_context_summary_echo_is_invalid(self):
        raw = (
            "Previous round opinions:\n\n"
            "## Round 1 Summary\n"
            "**claude**: Use FastAPI with PostgreSQL.\n"
            "**codex**: Same recommendation, add Redis later.\n"
            "---\n"
            "For each other agent's opinion above, state whether you AGREE or DISAGREE.\n"
            "End your response with either 'I AGREE with [name]' or 'I DISAGREE with all'."
        )

        result = ResponseValidator.validate_opinion(raw)

        assert result.usable is False
        assert result.classification == ResponseValidator.SHARED_CONTEXT_ECHO
