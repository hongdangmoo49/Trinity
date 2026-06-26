"""Pure parsers for Textual-owned slash commands."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class AskCommandParseResult:
    """Parsed `/ask` command arguments."""

    target_agents: tuple[str, ...] = ()
    agent_model_overrides: dict[str, str] = field(default_factory=dict)
    prompt: str = ""
    error: str = ""


def parse_ask_args(
    args: list[str],
    active_agent_names: Iterable[str],
    *,
    lang: str = "en",
) -> AskCommandParseResult:
    """Parse `/ask` arguments into target agents, model overrides, and prompt."""
    if not args:
        return AskCommandParseResult(
            error=textual_presenters.ask_usage_markdown(lang=lang)
        )

    active_agents = tuple(
        str(agent).strip()
        for agent in active_agent_names
        if str(agent).strip()
    )
    active_agent_set = set(active_agents)
    selector = args[0].strip().lower()
    if selector == "all":
        target_agents = active_agents
    else:
        requested = tuple(
            item.strip().lower()
            for item in selector.split(",")
            if item.strip()
        )
        unknown = [name for name in requested if name not in active_agent_set]
        if unknown:
            return AskCommandParseResult(
                error=textual_presenters.ask_unknown_agent_markdown(
                    unknown,
                    lang=lang,
                )
            )
        target_agents = requested

    if not target_agents:
        return AskCommandParseResult(
            error=textual_presenters.ask_no_active_agents_markdown(lang=lang)
        )

    model = ""
    prompt_parts: list[str] = []
    index = 1
    while index < len(args):
        value = args[index]
        if value in {"--model", "-m"}:
            if index + 1 >= len(args):
                return AskCommandParseResult(
                    error=textual_presenters.ask_missing_model_markdown(lang=lang)
                )
            model = args[index + 1].strip()
            index += 2
            continue
        prompt_parts.append(value)
        index += 1

    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        return AskCommandParseResult(
            error=textual_presenters.ask_prompt_empty_markdown(lang=lang)
        )

    model_overrides = {agent: model for agent in target_agents} if model else {}
    return AskCommandParseResult(
        target_agents=target_agents,
        agent_model_overrides=model_overrides,
        prompt=prompt,
    )
