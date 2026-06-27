from types import SimpleNamespace

from trinity.textual_app.ask_commands import (
    ask_command_action,
    ask_error_presentation,
    run_ask_command,
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
