"""Compatibility namespace for legacy tmux transport.

The implementation lives in `trinity.legacy.tmux`; this package remains so
existing imports keep working during the one-shot provider migration.
"""

from trinity.legacy.tmux import TMUX_CONFIG_FLAGS, TmuxPane, TmuxSessionManager

__all__ = ["TMUX_CONFIG_FLAGS", "TmuxPane", "TmuxSessionManager"]
