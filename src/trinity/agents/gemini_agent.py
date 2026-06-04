"""Compatibility shim for the legacy Gemini CLI provider."""

from trinity.legacy.gemini.agent import COMPLETION_MARKER, GeminiAgent

__all__ = ["COMPLETION_MARKER", "GeminiAgent"]
