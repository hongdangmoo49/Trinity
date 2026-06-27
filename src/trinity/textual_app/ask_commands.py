"""Pure helpers for Textual ask command presentation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from trinity.textual_app.command_parsers import parse_ask_args
from trinity.textual_app import presenters as textual_presenters

AskCommandActionKind = Literal["error", "start", "follow_up"]


@dataclass(frozen=True)
class AskCommandPresentation:
    """Prepared local command result for `/ask` errors."""

    title: str
    body: str
    severity: str = "info"
    empty: bool = False
    action_hint: str = ""


@dataclass(frozen=True)
class AskCommandAction:
    """Parsed `/ask` command action for the Textual app to execute."""

    kind: AskCommandActionKind
    prompt: str = ""
    target_agents: tuple[str, ...] = ()
    agent_model_overrides: dict[str, str] = field(default_factory=dict)
    presentation: AskCommandPresentation | None = None


def ask_command_action(
    args: list[str],
    active_agent_names: Iterable[str],
    *,
    current_route: str,
    lang: str = "en",
) -> AskCommandAction:
    """Return the `/ask` action to execute from parsed command arguments."""
    parsed = parse_ask_args(
        args,
        active_agent_names,
        lang=lang,
    )
    if parsed.error:
        return AskCommandAction(
            kind="error",
            presentation=ask_error_presentation(parsed.error, lang=lang),
        )

    return AskCommandAction(
        kind="start" if current_route == "start" else "follow_up",
        prompt=parsed.prompt,
        target_agents=parsed.target_agents,
        agent_model_overrides=parsed.agent_model_overrides,
    )


def ask_error_presentation(
    error: str,
    *,
    lang: str = "en",
) -> AskCommandPresentation:
    """Return the warning presentation payload for invalid `/ask` input."""
    return AskCommandPresentation(
        title=textual_presenters.ask_title(lang=lang),
        body=error,
        severity="warning",
        empty=True,
        action_hint=textual_presenters.ask_action_hint(lang=lang),
    )
