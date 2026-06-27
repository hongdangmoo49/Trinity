"""Pure helpers for Textual ask command presentation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from trinity.textual_app.command_parsers import parse_ask_args
from trinity.textual_app import presenters as textual_presenters
from trinity.textual_app.target_workspace import safe_start_target_workspace

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


class AskCommandNexus(Protocol):
    """Nexus surface methods used by `/ask` execution."""

    def set_initial_prompt(self, prompt: str) -> None: ...

    def set_agent_selection(
        self,
        target_agents: tuple[str, ...],
        agent_model_overrides: dict[str, str],
    ) -> None: ...


class AskWorkflowController(Protocol):
    """Workflow controller methods used by `/ask` execution."""

    def start_prompt(
        self,
        prompt: str,
        *,
        target_workspace: Path | None = None,
        target_agents: tuple[str, ...] = (),
        agent_model_overrides: dict[str, str] | None = None,
    ) -> Any: ...

    def submit_follow_up(
        self,
        text: str,
        *,
        target_agents: tuple[str, ...] = (),
        agent_model_overrides: dict[str, str] | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class AskCommandRun:
    """Result of executing a valid `/ask` action."""

    outcome: Any
    initial_prompt: str = ""
    target_workspace: Path | None = None
    switch_to_nexus: bool = False


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


def run_ask_command(
    action: AskCommandAction,
    *,
    nexus: AskCommandNexus,
    workflow_controller: AskWorkflowController,
    workspace_candidate: Path | None,
    project_dir: Path,
) -> AskCommandRun:
    """Apply UI selection and execute a valid `/ask` action."""
    nexus.set_agent_selection(action.target_agents, action.agent_model_overrides)
    if action.kind == "start":
        nexus.set_initial_prompt(action.prompt)
        target_workspace = safe_start_target_workspace(workspace_candidate, project_dir)
        outcome = workflow_controller.start_prompt(
            action.prompt,
            target_workspace=target_workspace,
            target_agents=action.target_agents,
            agent_model_overrides=action.agent_model_overrides,
        )
        return AskCommandRun(
            outcome=outcome,
            initial_prompt=action.prompt,
            target_workspace=target_workspace,
            switch_to_nexus=True,
        )

    outcome = workflow_controller.submit_follow_up(
        action.prompt,
        target_agents=action.target_agents,
        agent_model_overrides=action.agent_model_overrides,
    )
    return AskCommandRun(outcome=outcome)


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
