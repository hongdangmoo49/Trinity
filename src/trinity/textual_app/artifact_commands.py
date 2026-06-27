"""Pure helpers for Textual artifact command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from trinity.context.commands import artifact_markdown
from trinity.context.shared import SharedContextEngine
from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.command_parsers import parse_artifact_args


ArtifactSeverity = Literal["info", "warning"]


@dataclass(frozen=True)
class ArtifactCommandPresentation:
    """Prepared local command result for `/artifact`."""

    title: str
    body: str
    severity: ArtifactSeverity = "info"


def artifact_command_presentation(
    engine: SharedContextEngine,
    args: list[str],
    *,
    lang: str = "en",
) -> ArtifactCommandPresentation:
    """Return the presentation payload for a Textual `/artifact` command."""
    parsed = parse_artifact_args(args, lang=lang)
    title = textual_presenters.artifact_title(lang=lang)
    if parsed.error:
        return ArtifactCommandPresentation(
            title=title,
            body=parsed.error,
            severity="warning",
        )
    return ArtifactCommandPresentation(
        title=title,
        body=artifact_markdown(engine, parsed.record_id, lang=lang),
    )
