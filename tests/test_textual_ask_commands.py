from types import SimpleNamespace

from trinity.textual_app.ask_commands import (
    ask_command_action,
    ask_command_run_effect,
    ask_error_presentation,
    nexus_follow_up_target_workspace,
    run_ask_command,
    start_submission_effect,
)


def test_ask_error_presentation_marks_warning_and_empty_state() -> None:
    presentation = ask_error_presentation(
        "Use: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )

    assert presentation.title == "Ask"
    assert presentation.body == (
        "Use: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )


def test_ask_error_presentation_uses_korean_labels() -> None:
    presentation = ask_error_presentation(
        "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>",
        lang="ko",
    )

    assert presentation.title == "질문"
    assert presentation.body == (
        "사용법: /ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )
    assert presentation.severity == "warning"
    assert presentation.empty is True
    assert presentation.action_hint == (
        "/ask <all|agent[,agent...]> [--model MODEL] <prompt>"
    )


def test_ask_command_action_returns_start_action_on_start_route() -> None:
    action = ask_command_action(
        ["claude", "--model", "sonnet", "분석해라"],
        ["claude", "codex"],
        current_route="start",
        lang="ko",
    )

    assert action.kind == "start"
    assert action.prompt == "분석해라"
    assert action.target_agents == ("claude",)
    assert action.agent_model_overrides == {"claude": "sonnet"}
    assert action.presentation is None


def test_ask_command_action_returns_follow_up_action_off_start_route() -> None:
    action = ask_command_action(
        ["all", "continue", "work"],
        ["claude", "codex"],
        current_route="nexus",
    )

    assert action.kind == "follow_up"
    assert action.prompt == "continue work"
    assert action.target_agents == ("claude", "codex")
    assert action.agent_model_overrides == {}
    assert action.presentation is None


def test_ask_command_action_returns_error_presentation() -> None:
    action = ask_command_action(
        ["missing", "hello"],
        ["claude"],
        current_route="nexus",
    )

    assert action.kind == "error"
    assert action.presentation is not None
    assert action.presentation.severity == "warning"
    assert "Unknown or disabled agent" in action.presentation.body


def test_run_ask_command_starts_workflow_with_safe_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    control_repo = tmp_path / "control"
    action = ask_command_action(
        ["claude", "--model", "sonnet", "분석해라"],
        ["claude"],
        current_route="start",
    )
    nexus = _FakeAskNexus()
    controller = _FakeAskController()

    run = run_ask_command(
        action,
        nexus=nexus,
        workflow_controller=controller,
        workspace_candidate=workspace,
        project_dir=control_repo,
    )

    assert nexus.initial_prompt == "분석해라"
    assert nexus.agent_selections == [(("claude",), {"claude": "sonnet"})]
    assert controller.started == [
        {
            "prompt": "분석해라",
            "target_workspace": workspace,
            "target_agents": ("claude",),
            "agent_model_overrides": {"claude": "sonnet"},
        }
    ]
    assert run.initial_prompt == "분석해라"
    assert run.target_workspace == workspace
    assert run.switch_to_nexus is True
    assert run.outcome is controller.start_outcome


def test_run_ask_command_skips_control_repo_start_workspace(tmp_path) -> None:
    control_repo = tmp_path / "control"
    action = ask_command_action(
        ["claude", "분석해라"],
        ["claude"],
        current_route="start",
    )
    controller = _FakeAskController()

    run = run_ask_command(
        action,
        nexus=_FakeAskNexus(),
        workflow_controller=controller,
        workspace_candidate=control_repo,
        project_dir=control_repo,
    )

    assert controller.started[0]["target_workspace"] is None
    assert run.target_workspace is None


def test_run_ask_command_submits_follow_up(tmp_path) -> None:
    action = ask_command_action(
        ["all", "continue"],
        ["claude", "codex"],
        current_route="nexus",
    )
    nexus = _FakeAskNexus()
    controller = _FakeAskController()

    run = run_ask_command(
        action,
        nexus=nexus,
        workflow_controller=controller,
        workspace_candidate=None,
        project_dir=tmp_path,
    )

    assert nexus.initial_prompt == ""
    assert nexus.agent_selections == [(("claude", "codex"), {})]
    assert controller.follow_ups == [
        {
            "text": "continue",
            "target_agents": ("claude", "codex"),
            "agent_model_overrides": {},
        }
    ]
    assert run.switch_to_nexus is False
    assert run.outcome is controller.follow_up_outcome


def test_ask_command_run_effect_marks_start_route_effects(tmp_path) -> None:
    snapshot = SimpleNamespace(session_id="wf-1")
    run = SimpleNamespace(
        outcome=SimpleNamespace(snapshot=snapshot, target_workspace_required=False),
        initial_prompt="분석해라",
        target_workspace=tmp_path,
        switch_to_nexus=True,
    )

    effect = ask_command_run_effect(run)

    assert effect.initial_prompt == "분석해라"
    assert effect.remember_target_preflight is True
    assert effect.target_workspace == tmp_path
    assert effect.target_snapshot is snapshot
    assert effect.switch_to_nexus is True
    assert effect.workspace_picker_snapshot is None


def test_ask_command_run_effect_marks_follow_up_workspace_picker() -> None:
    snapshot = SimpleNamespace(session_id="wf-1")
    run = SimpleNamespace(
        outcome=SimpleNamespace(snapshot=snapshot, target_workspace_required=True),
        initial_prompt="",
        target_workspace=None,
        switch_to_nexus=False,
    )

    effect = ask_command_run_effect(run)

    assert effect.initial_prompt == ""
    assert effect.remember_target_preflight is False
    assert effect.target_workspace is None
    assert effect.target_snapshot is None
    assert effect.switch_to_nexus is False
    assert effect.workspace_picker_snapshot is snapshot


def test_ask_command_run_effect_ignores_follow_up_without_workspace_picker() -> None:
    run = SimpleNamespace(
        outcome=SimpleNamespace(snapshot=SimpleNamespace(), target_workspace_required=False),
        initial_prompt="",
        target_workspace=None,
        switch_to_nexus=False,
    )

    effect = ask_command_run_effect(run)

    assert effect.remember_target_preflight is False
    assert effect.switch_to_nexus is False
    assert effect.workspace_picker_snapshot is None


def test_start_submission_effect_uses_event_workspace_when_current_is_empty(tmp_path) -> None:
    workspace = tmp_path / "workspace"

    effect = start_submission_effect(
        prompt="Build",
        event_workspace_candidate=workspace,
        current_workspace_candidate=None,
        target_agents=("claude",),
        agent_model_overrides={"claude": "sonnet"},
        project_dir=tmp_path / "control",
    )

    assert effect.prompt == "Build"
    assert effect.workspace_candidate_to_set == workspace
    assert effect.target_workspace == workspace
    assert effect.target_agents == ("claude",)
    assert effect.agent_model_overrides == {"claude": "sonnet"}


def test_start_submission_effect_keeps_existing_workspace_candidate(tmp_path) -> None:
    current = tmp_path / "current"
    event_workspace = tmp_path / "event"

    effect = start_submission_effect(
        prompt="Build",
        event_workspace_candidate=event_workspace,
        current_workspace_candidate=current,
        target_agents=("claude", "codex"),
        agent_model_overrides={},
        project_dir=tmp_path / "control",
    )

    assert effect.workspace_candidate_to_set is None
    assert effect.target_workspace == current
    assert effect.target_agents == ("claude", "codex")


def test_start_submission_effect_skips_control_repo_workspace(tmp_path) -> None:
    control_repo = tmp_path / "control"

    effect = start_submission_effect(
        prompt="Build",
        event_workspace_candidate=control_repo,
        current_workspace_candidate=None,
        target_agents=(),
        agent_model_overrides={},
        project_dir=control_repo,
    )

    assert effect.workspace_candidate_to_set == control_repo
    assert effect.target_workspace is None


def test_nexus_follow_up_target_workspace_prefers_snapshot_target(tmp_path) -> None:
    control_repo = tmp_path / "control"
    snapshot_target = tmp_path / "snapshot-app"
    candidate = tmp_path / "candidate-app"

    target = nexus_follow_up_target_workspace(
        SimpleNamespace(target_workspace=str(snapshot_target)),
        candidate,
        control_repo,
    )

    assert target == snapshot_target


def test_nexus_follow_up_target_workspace_uses_candidate_without_snapshot(tmp_path) -> None:
    control_repo = tmp_path / "control"
    candidate = tmp_path / "candidate-app"

    target = nexus_follow_up_target_workspace(
        SimpleNamespace(target_workspace=""),
        candidate,
        control_repo,
    )

    assert target == candidate


def test_nexus_follow_up_target_workspace_skips_control_repo_candidate(tmp_path) -> None:
    control_repo = tmp_path / "control"

    target = nexus_follow_up_target_workspace(
        SimpleNamespace(target_workspace=""),
        control_repo,
        control_repo,
    )

    assert target is None


class _FakeAskNexus:
    def __init__(self) -> None:
        self.initial_prompt = ""
        self.agent_selections: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def set_initial_prompt(self, prompt: str) -> None:
        self.initial_prompt = prompt

    def set_agent_selection(
        self,
        target_agents: tuple[str, ...],
        agent_model_overrides: dict[str, str],
    ) -> None:
        self.agent_selections.append((target_agents, dict(agent_model_overrides)))


class _FakeAskController:
    def __init__(self) -> None:
        self.start_outcome = SimpleNamespace(snapshot=SimpleNamespace())
        self.follow_up_outcome = SimpleNamespace(target_workspace_required=False)
        self.started: list[dict[str, object]] = []
        self.follow_ups: list[dict[str, object]] = []

    def start_prompt(
        self,
        prompt: str,
        *,
        target_workspace=None,
        target_agents=(),
        agent_model_overrides=None,
    ):
        self.started.append(
            {
                "prompt": prompt,
                "target_workspace": target_workspace,
                "target_agents": tuple(target_agents),
                "agent_model_overrides": dict(agent_model_overrides or {}),
            }
        )
        return self.start_outcome

    def submit_follow_up(
        self,
        text: str,
        *,
        target_agents=(),
        agent_model_overrides=None,
    ):
        self.follow_ups.append(
            {
                "text": text,
                "target_agents": tuple(target_agents),
                "agent_model_overrides": dict(agent_model_overrides or {}),
            }
        )
        return self.follow_up_outcome
