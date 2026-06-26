"""Pure parsers for Textual-owned slash commands."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from trinity.i18n import VALID_CAVEMAN_INTENSITIES
from trinity.textual_app import presenters as textual_presenters


@dataclass(frozen=True)
class AskCommandParseResult:
    """Parsed `/ask` command arguments."""

    target_agents: tuple[str, ...] = ()
    agent_model_overrides: dict[str, str] = field(default_factory=dict)
    prompt: str = ""
    error: str = ""


@dataclass(frozen=True)
class RoundsCommandParseResult:
    """Parsed `/rounds` command arguments."""

    rounds: int | None = None
    error: str = ""
    action_hint: str = ""


@dataclass(frozen=True)
class AgentCommandParseResult:
    """Parsed `/agent` command arguments."""

    agent_name: str = ""
    enabled: bool | None = None
    error: str = ""


@dataclass(frozen=True)
class CavemanCommandParseResult:
    """Parsed `/caveman` command arguments."""

    enabled: bool | None = None
    intensity: str = ""
    error: str = ""
    action_hint: str = ""


@dataclass(frozen=True)
class AnswerCommandParseResult:
    """Parsed `/answer` command arguments."""

    question_selector: str = ""
    answer: str = ""
    option_index: str = ""
    replace: bool = False
    error: str = ""
    action_hint: str = ""


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


def parse_rounds_args(
    args: list[str],
    *,
    lang: str = "en",
    minimum: int = 1,
    maximum: int = 20,
) -> RoundsCommandParseResult:
    """Parse `/rounds` arguments into a validated session round count."""
    if not args:
        return RoundsCommandParseResult()

    action_hint = textual_presenters.rounds_usage_action_hint(lang=lang)
    try:
        rounds = int(args[0])
    except ValueError:
        return RoundsCommandParseResult(
            error=textual_presenters.rounds_invalid_number_markdown(lang=lang),
            action_hint=action_hint,
        )

    if rounds < minimum or rounds > maximum:
        return RoundsCommandParseResult(
            error=textual_presenters.rounds_range_error_markdown(lang=lang),
            action_hint=action_hint,
        )
    return RoundsCommandParseResult(rounds=rounds)


def parse_agent_args(
    args: list[str],
    agent_names: Iterable[str],
    *,
    lang: str = "en",
) -> AgentCommandParseResult:
    """Parse `/agent` arguments into a target agent and enabled state."""
    if not args:
        return AgentCommandParseResult()
    if len(args) < 2:
        return AgentCommandParseResult(
            error=textual_presenters.agent_usage_markdown(lang=lang)
        )

    active_agent_names = {
        str(agent).strip().lower()
        for agent in agent_names
        if str(agent).strip()
    }
    name = args[0].strip().lower()
    if name not in active_agent_names:
        return AgentCommandParseResult(
            agent_name=name,
            error=textual_presenters.agent_unknown_markdown(name, lang=lang),
        )

    action = args[1].strip().lower()
    if action not in {"on", "off"}:
        return AgentCommandParseResult(
            agent_name=name,
            error=textual_presenters.agent_usage_markdown(lang=lang),
        )

    return AgentCommandParseResult(agent_name=name, enabled=action == "on")


def parse_caveman_args(
    args: list[str],
    *,
    lang: str = "en",
) -> CavemanCommandParseResult:
    """Parse `/caveman` arguments into mode and intensity updates."""
    if not args:
        return CavemanCommandParseResult()

    action = args[0].strip().lower()
    if action in {"off", "disable"}:
        return CavemanCommandParseResult(enabled=False)
    if action in {"on", "enable"}:
        return CavemanCommandParseResult(enabled=True)
    if action in VALID_CAVEMAN_INTENSITIES:
        return CavemanCommandParseResult(enabled=True, intensity=action)
    return CavemanCommandParseResult(
        error=textual_presenters.caveman_usage_markdown(lang=lang),
        action_hint=textual_presenters.caveman_allowed_action_hint(lang=lang),
    )


def parse_answer_args(
    args: list[str],
    *,
    lang: str = "en",
) -> AnswerCommandParseResult:
    """Parse `/answer` arguments into controller routing data."""
    replace_answer = False
    filtered: list[str] = []
    for arg in args:
        if arg in {"--replace", "-r"}:
            replace_answer = True
        else:
            filtered.append(arg)

    if not filtered:
        return AnswerCommandParseResult(
            replace=replace_answer,
            error=textual_presenters.answer_usage_markdown(lang=lang),
            action_hint=textual_presenters.answer_action_hint(lang=lang),
        )

    if len(filtered) == 1 and filtered[0].isdigit():
        return AnswerCommandParseResult(
            option_index=filtered[0],
            replace=replace_answer,
        )
    if len(filtered) == 1:
        return AnswerCommandParseResult(
            question_selector="next",
            answer=filtered[0],
            replace=replace_answer,
        )
    return AnswerCommandParseResult(
        question_selector=filtered[0],
        answer=" ".join(filtered[1:]),
        replace=replace_answer,
    )
