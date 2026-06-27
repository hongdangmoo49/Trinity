"""Pure helpers for Textual agent command presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, MutableMapping, Protocol

from trinity.textual_app.command_parsers import parse_agent_args
from trinity.textual_app import presenters as textual_presenters


class AgentCommandSpec(Protocol):
    """Small presenter-facing subset of an agent config."""

    enabled: bool
    provider: object


@dataclass(frozen=True)
class AgentCommandPresentation:
    """Prepared local command result for `/agent`."""

    title: str
    body: str
    severity: str = "info"
    action_hint: str = ""
    table_columns: tuple[str, ...] = ()
    table_rows: tuple[tuple[str, ...], ...] = ()


def agent_current_presentation(
    agents: Mapping[str, AgentCommandSpec],
    *,
    lang: str = "en",
) -> AgentCommandPresentation:
    """Return the presentation payload for current `/agent` settings."""
    return AgentCommandPresentation(
        title=textual_presenters.agent_title(lang=lang),
        body=textual_presenters.session_setting_body(
            textual_presenters.agent_current_settings_markdown(lang=lang)
        ),
        table_columns=textual_presenters.agent_table_columns(lang=lang),
        table_rows=textual_presenters.agent_rows(agents, lang=lang),
        action_hint=textual_presenters.agent_change_action_hint(lang=lang),
    )


def agent_command_presentation(
    agents: MutableMapping[str, AgentCommandSpec],
    args: list[str],
    *,
    lang: str = "en",
) -> AgentCommandPresentation:
    """Apply `/agent` args and return the resulting presentation."""
    parsed = parse_agent_args(
        args,
        agents.keys(),
        lang=lang,
    )
    if not args:
        return agent_current_presentation(agents, lang=lang)
    if parsed.error:
        return agent_error_presentation(parsed.error, agents, lang=lang)

    name = parsed.agent_name
    spec = agents[name]
    spec.enabled = bool(parsed.enabled)
    return agent_update_presentation(
        name,
        spec.enabled,
        agents,
        lang=lang,
    )


def agent_error_presentation(
    error: str,
    agents: Mapping[str, AgentCommandSpec],
    *,
    lang: str = "en",
) -> AgentCommandPresentation:
    """Return the warning presentation payload for invalid `/agent` input."""
    return AgentCommandPresentation(
        title=textual_presenters.agent_title(lang=lang),
        body=error,
        severity="warning",
        table_columns=textual_presenters.agent_table_columns(lang=lang),
        table_rows=textual_presenters.agent_rows(agents, lang=lang),
    )


def agent_update_presentation(
    agent_name: str,
    enabled: bool,
    agents: Mapping[str, AgentCommandSpec],
    *,
    lang: str = "en",
) -> AgentCommandPresentation:
    """Return the presentation payload for a changed `/agent` setting."""
    return AgentCommandPresentation(
        title=textual_presenters.agent_title(lang=lang),
        body=textual_presenters.session_setting_body(
            textual_presenters.agent_status_markdown(
                agent_name,
                enabled,
                lang=lang,
            )
        ),
        table_columns=textual_presenters.agent_table_columns(lang=lang),
        table_rows=textual_presenters.agent_rows(agents, lang=lang),
    )
