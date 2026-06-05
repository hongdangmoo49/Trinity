"""Compatibility hooks for terminals using the Kitty keyboard protocol."""

from __future__ import annotations


def install_prompt_toolkit_parser_patch() -> None:
    """Install prompt_toolkit compatibility hooks when needed.

    The default implementation is intentionally a no-op; terminal mode handling
    lives in the interactive session and this hook keeps imports stable.
    """


def install_textual_parser_patch() -> None:
    """Install Textual compatibility hooks when needed."""
