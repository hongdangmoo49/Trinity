"""Pure helpers for Textual save command presentation."""

from __future__ import annotations

from dataclasses import dataclass

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class SaveCommandPresentation:
    """Prepared local command result for `/save`."""

    title: str
    body: str


def save_command_presentation(*, lang: str = "en") -> SaveCommandPresentation:
    """Return the presentation payload for a Textual `/save` command."""
    return SaveCommandPresentation(
        title=textual_presenters.save_title(lang=lang),
        body=textual_presenters.save_auto_persist_markdown(lang=lang),
    )
