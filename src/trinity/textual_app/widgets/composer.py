"""Prompt composer widgets."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import TextArea


class PromptComposer(Vertical):
    """Multi-line prompt composer."""

    class Submitted(Message):
        """Posted when the composer should be sent."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    BINDINGS = [
        Binding("ctrl+enter", "submit", "Send", priority=True),
    ]

    def __init__(
        self,
        *,
        placeholder: str = "",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield TextArea(
            "",
            placeholder=self.placeholder,
            soft_wrap=True,
            show_line_numbers=False,
            id="prompt-textarea",
        )

    @property
    def text(self) -> str:
        return self.query_one(TextArea).text

    def set_text(self, text: str) -> None:
        self.query_one(TextArea).load_text(text)

    def clear(self) -> None:
        self.set_text("")

    def focus_text_area(self) -> None:
        self.query_one(TextArea).focus()

    def action_submit(self) -> None:
        self.post_message(self.Submitted(self.text))
