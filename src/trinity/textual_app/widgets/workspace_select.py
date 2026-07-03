"""Shared workspace selection surface."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import Static


class WorkspaceSelectSurface(Static):
    """Clickable workspace selector used by Start and Nexus."""

    can_focus = True

    class Pressed(Message):
        """Posted when the selector is clicked."""

    def __init__(self, label: str, *, id: str, tall: bool = False) -> None:
        classes = "workspace-select-surface"
        if tall:
            classes += " workspace-select-surface-tall"
        super().__init__(label, id=id, classes=classes)

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Pressed())

    def on_key(self, event: events.Key) -> None:
        if event.key not in {"space", "enter"}:
            return
        event.stop()
        self.post_message(self.Pressed())
