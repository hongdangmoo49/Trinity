"""Tests for SessionRotator — format string injection prevention."""

from unittest.mock import AsyncMock, MagicMock

from trinity.context.rotator import SessionRotator


class TestRotatorSecurity:
    def test_continuation_prompt_handles_curly_braces(self):
        """Verify curly braces in context don't cause KeyError via string.Template."""
        rotator = SessionRotator(agents={}, shared=MagicMock())

        # string.Template.substitute should handle curly braces safely
        result = rotator.CONTINUATION_PROMPT.substitute(
            shared_context="some {curly} content",
            session_summary="summary with {braces}",
            agent_role="role",
        )
        assert "curly" in result
        assert "braces" in result

    def test_continuation_prompt_dollar_sign_safe(self):
        """Verify that $ signs in content don't get interpreted as template vars
        (they won't, since ${} syntax is used, not $var)."""
        rotator = SessionRotator(agents={}, shared=MagicMock())
        result = rotator.CONTINUATION_PROMPT.substitute(
            shared_context="cost is $100",
            session_summary="earned $200 total",
            agent_role="role",
        )
        assert "$100" in result
        assert "$200" in result
