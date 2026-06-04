"""Compatibility shim for legacy tmux session imports."""

from trinity.legacy.tmux.session import TMUX_CONFIG_FLAGS, TmuxSessionManager

__all__ = ["TMUX_CONFIG_FLAGS", "TmuxSessionManager"]
