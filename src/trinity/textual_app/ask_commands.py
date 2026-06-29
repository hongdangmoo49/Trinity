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


@dataclass(frozen=True)
class AskCommandRunEffect:
    """UI effects derived from a completed `/ask` command run."""

    initial_prompt: str = ""
    remember_target_preflight: bool = False
    target_workspace: Path | None = None
    target_snapshot: Any | None = None
    switch_to_nexus: bool = False
    workspace_picker_snapshot: Any | None = None


@dataclass(frozen=True)
class StartSubmissionEffect:
    """Prepared app state for a Start screen prompt submission."""

    prompt: str
    workspace_candidate_to_set: Path | None
    target_workspace: Path | None
    target_agents: tuple[str, ...]
    agent_model_overrides: dict[str, str]


def nexus_follow_up_target_workspace(
    snapshot: Any | None,
    workspace_candidate: Path | None,
    project_dir: Path,
) -> Path | None:
    """Return the visible Nexus workspace that should scope a follow-up."""
    candidates: list[Path] = []
    snapshot_target = str(getattr(snapshot, "target_workspace", "") or "").strip()
    if snapshot_target:
        candidates.append(Path(snapshot_target))
    if workspace_candidate is not None:
        candidates.append(workspace_candidate)
    for candidate in candidates:
        target = safe_start_target_workspace(candidate, project_dir)
        if target is not None:
            return target
    return None


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


def ask_command_run_effect(run: AskCommandRun) -> AskCommandRunEffect:
    """Return the UI effects the app should apply after a valid `/ask` run."""
    outcome = run.outcome
    snapshot = getattr(outcome, "snapshot", None)
    workspace_picker_snapshot = None
    if not run.switch_to_nexus and getattr(outcome, "target_workspace_required", False):
        workspace_picker_snapshot = snapshot
    return AskCommandRunEffect(
        initial_prompt=run.initial_prompt,
        remember_target_preflight=run.switch_to_nexus,
        target_workspace=run.target_workspace,
        target_snapshot=snapshot if run.switch_to_nexus else None,
        switch_to_nexus=run.switch_to_nexus,
        workspace_picker_snapshot=workspace_picker_snapshot,
    )


def start_submission_effect(
    *,
    prompt: str,
    event_workspace_candidate: Path | None,
    current_workspace_candidate: Path | None,
    target_agents: tuple[str, ...],
    agent_model_overrides: dict[str, str],
    project_dir: Path,
) -> StartSubmissionEffect:
    """Return the state changes needed before starting a workflow from Start."""
    workspace_candidate_to_set = None
    effective_workspace_candidate = current_workspace_candidate
    if effective_workspace_candidate is None:
        workspace_candidate_to_set = event_workspace_candidate
        effective_workspace_candidate = event_workspace_candidate
    return StartSubmissionEffect(
        prompt=prompt,
        workspace_candidate_to_set=workspace_candidate_to_set,
        target_workspace=safe_start_target_workspace(
            effective_workspace_candidate,
            project_dir,
        ),
        target_agents=target_agents,
        agent_model_overrides=dict(agent_model_overrides),
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
