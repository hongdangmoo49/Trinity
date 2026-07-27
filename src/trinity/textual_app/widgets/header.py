"""Trinity-safe Textual header."""

from textual.widgets import Static


class TrinityHeader(Static):
    """A stable one-line header without deferred title watchers."""

    DEFAULT_CSS = """
    TrinityHeader {
        dock: top;
        width: 100%;
        height: 1;
        background: $panel;
        color: $foreground;
        content-align: center middle;
    }
    """

    def __init__(self, *, show_clock: bool = False) -> None:
        super().__init__("")
        self.show_clock = show_clock

    def on_mount(self) -> None:
        title = self.screen.title or self.app.title or ""
        sub_title = self.screen.sub_title or self.app.sub_title or ""
        self.update(self.app.format_title(title, sub_title))
