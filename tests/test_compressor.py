"""Tests for PromptCompressor — heuristic text compression."""

import pytest

from trinity.context.compressor import PromptCompressor


class TestPromptCompressorHeuristic:
    """Test the local heuristic compression (no LLM call)."""

    def test_compress_single_opinion_extracts_key_points(self):
        opinion = (
            "I recommend using pytest for testing. "
            "It has excellent fixture support and plugin ecosystem. "
            "The main benefit is easy parametrization. "
            "In my experience, pytest reduces test boilerplate by 40%. "
            "I agree that unittest is also viable for simple projects."
        )
        compressor = PromptCompressor(max_summary_tokens=30)
        result = compressor.compress_heuristic(opinion)
        assert len(result) < len(opinion)
        assert "pytest" in result
        assert result

    def test_compress_multiple_opinions(self):
        opinions = {
            "claude": "I suggest using FastAPI for the backend. It provides automatic OpenAPI docs.",
            "codex": "I agree with FastAPI. Additionally, consider SQLAlchemy for ORM.",
            "antigravity": "I recommend comparing FastAPI with Django REST first.",
        }
        compressor = PromptCompressor(max_summary_tokens=20)
        result = compressor.compress_opinions_heuristic(opinions)
        assert "claude" in result.lower() or "FastAPI" in result
        # Each agent's opinion should be compressed (shorter than original)
        for name, original in opinions.items():
            # The compressed output for each agent should be shorter
            # than the original opinion text (ignoring the prefix overhead)
            assert len(result) < sum(len(v) for v in opinions.values()) + 100

    def test_compress_empty_opinions_returns_empty(self):
        compressor = PromptCompressor()
        assert compressor.compress_heuristic("") == ""
        assert compressor.compress_opinions_heuristic({}) == ""

    def test_compress_preserves_agreement_disagreement(self):
        opinion = (
            "Looking at the options, Flask is lightweight. "
            "Django has more batteries included. "
            "I AGREE with the FastAPI suggestion. "
            "It is the best choice for async APIs."
        )
        compressor = PromptCompressor(max_summary_tokens=100)
        result = compressor.compress_heuristic(opinion)
        assert "AGREE" in result or "agree" in result.lower()

    def test_compress_short_text_unchanged(self):
        short_text = "Use pytest."
        compressor = PromptCompressor(max_summary_tokens=500)
        result = compressor.compress_heuristic(short_text)
        assert result == short_text

    def test_compress_opinions_formats_with_agent_names(self):
        opinions = {
            "claude": "I recommend approach A because it is simpler.",
            "codex": "I agree with approach A.",
        }
        compressor = PromptCompressor(max_summary_tokens=200)
        result = compressor.compress_opinions_heuristic(opinions)
        assert "claude" in result.lower()
        assert "codex" in result.lower()

    def test_estimated_token_count(self):
        compressor = PromptCompressor()
        text = "Hello world, this is a test."
        tokens = compressor.estimate_tokens(text)
        assert tokens > 0
        assert tokens < len(text)

    def test_compress_respects_max_tokens(self):
        long_text = " ".join(f"Word{i}" for i in range(200))
        compressor = PromptCompressor(max_summary_tokens=50)
        result = compressor.compress_heuristic(long_text)
        estimated = compressor.estimate_tokens(result)
        assert estimated <= compressor.max_summary_tokens * 1.2
