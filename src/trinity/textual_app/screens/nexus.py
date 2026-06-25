"""Nexus brainstorming screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from trinity.config import TrinityConfig
from trinity.models import AgentSpec
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import is_slash_command_text
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.snapshot import ProviderSnapshot, WorkflowNexusSnapshot
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel, ProviderPanelState
from trinity.textual_app.widgets.question_panel import QuestionAnswer, QuestionPanel
from trinity.workflow.engine import (
    PROVIDER_ERROR_CONTINUE_OPTION,
    PROVIDER_ERROR_GATE_QUESTION_ID,
    PROVIDER_ERROR_RETRY_OPTION,
    PROVIDER_ERROR_STOP_OPTION,
)


NEXUS_LABELS = {
    "en": {
        "composer_placeholder": "Reply, refine direction, or type / for commands",
        "execute": "Execute",
        "open_provider_inspector": "Open Provider Inspector",
        "select_agent_warning": "Select at least one agent.",
        "select_workspace": "Select Workspace",
        "workspace_not_selected": "Workspace: not selected",
        "workspace_selected": "Workspace: {target}",
    },
    "ko": {
        "composer_placeholder": "답변, 방향 조정 또는 /로 명령 입력",
        "execute": "실행",
        "open_provider_inspector": "프로바이더 인스펙터 열기",
        "select_agent_warning": "에이전트를 하나 이상 선택하세요.",
        "select_workspace": "작업 폴더 선택",
        "workspace_not_selected": "작업 폴더: 선택 안 됨",
        "workspace_selected": "작업 폴더: {target}",
    },
}


class NexusScreen(Screen[None]):
    """Provider dashboard and central synthesis conversation."""

    class FollowUpSubmitted(Message):
        """Posted when the user sends a follow-up in the active workflow."""

        def __init__(
            self,
            text: str,
            target_agents: tuple[str, ...],
            agent_model_overrides: dict[str, str],
        ) -> None:
            super().__init__()
            self.text = text
            self.target_agents = target_agents
            self.agent_model_overrides = agent_model_overrides

    class SlashCommandSubmitted(Message):
        """Posted when the Nexus composer submits a Trinity slash command."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class QuestionAnswered(Message):
        """Posted when the user selects a synthesized question answer."""

        def __init__(self, answer: QuestionAnswer) -> None:
            super().__init__()
            self.answer = answer

    class InspectorRequested(Message):
        """Posted when the user wants to inspect provider raw output."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    class ExecuteRequested(Message):
        """Posted when the user wants to move from planning to execution."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    class WorkspaceRequested(Message):
        """Posted when the user wants to choose a target workspace."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    class RepairActionRequested(Message):
        """Posted when the user chooses a review-repair blocked action."""

        def __init__(self, action: str, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.action = action
            self.snapshot = snapshot

    BINDINGS = [
        ("ctrl+enter", "submit_follow_up", "Send"),
        ("ctrl+e", "request_execute", "Execute"),
        ("i", "open_inspector", "Inspector"),
    ]

    LOCALIZED_BINDINGS = {
        ("ctrl+enter", "submit_follow_up"): ("binding_send", None),
        ("ctrl+e", "request_execute"): ("binding_execute", None),
        ("i", "open_inspector"): ("binding_inspector", None),
    }

    def __init__(self, config: TrinityConfig) -> None:
        super().__init__(name="nexus")
        self.config = config
        self.initial_prompt: str = ""
        localize_bindings(
            self._bindings, self.config.lang, self.LOCALIZED_BINDINGS
        )
        self.follow_ups: list[str] = []
        self.snapshot: WorkflowNexusSnapshot | None = None
        self._activity_frame = 0
        self._selected_agents: tuple[str, ...] = ()
        self._agent_model_overrides: dict[str, str] = {}
        self._agent_model_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        self._workspace_candidate: str = ""
        self._workspace_label_key = ""
        self._provider_state_cache: dict[str, ProviderPanelState] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="nexus-screen"):
            with Horizontal(id="provider-strip"):
                for state in self._initial_provider_states():
                    yield ProviderPanel(
                        state,
                        id=f"provider-{state.name}",
                        lang=self.config.lang,
                    )
            with Horizontal(id="nexus-action-bar"):
                yield Button(
                    self._label("open_provider_inspector"),
                    id="open-provider-inspector",
                )
                yield Button(
                    self._label("select_workspace"),
                    id="select-workspace",
                    variant="default",
                )
                yield Static(
                    self._workspace_label(),
                    id="nexus-target-workspace",
                )
                yield Button(
                    self._label("execute"),
                    id="request-execute",
                    variant="primary",
                )
            with Horizontal(id="nexus-main"):
                with Vertical(id="nexus-center-stack"):
                    yield CentralAgentView(id="central-agent", lang=self.config.lang)
                    yield QuestionPanel(id="nexus-question-panel", lang=self.config.lang)
                yield WorkflowInspector(id="workflow-inspector", lang=self.config.lang)
            yield AgentRecipientModelSelector(
                self.config.agents,
                id="nexus-recipient-selector",
                lang=self.config.lang,
            )
            yield PromptComposer(
                placeholder=self._label("composer_placeholder"),
                id="nexus-composer",
                lang=self.config.lang,
            )
        yield Footer()

    def on_mount(self) -> None:
        if self.snapshot is not None:
            self.apply_snapshot(self.snapshot)
        else:
            self._refresh_central()
            self._refresh_questions()
            self._refresh_inspector()
        if self._selected_agents or self._agent_model_overrides:
            self._apply_agent_selection()
        self._apply_model_choices()
        self.query_one("#nexus-composer", PromptComposer).focus_text_area()

    def set_initial_prompt(self, prompt: str) -> None:
        self.initial_prompt = prompt.strip()
        if self.is_mounted:
            self._refresh_central()

    def set_agent_selection(
        self,
        target_agents: tuple[str, ...] | list[str],
        agent_model_overrides: dict[str, str],
    ) -> None:
        """Apply selection state restored from the Start screen or resume."""
        self._selected_agents = tuple(target_agents)
        self._agent_model_overrides = dict(agent_model_overrides)
        if not self.is_mounted:
            return
        self._apply_agent_selection()

    def _apply_agent_selection(self) -> None:
        selector = self.query_one(AgentRecipientModelSelector)
        if self._selected_agents:
            selector.set_selected_agents(self._selected_agents)
        if self._agent_model_overrides:
            selector.set_model_overrides(self._agent_model_overrides)

    def set_workspace_candidate(self, path: object | None) -> None:
        """Update the visible workspace fallback when no workflow target exists."""
        self._workspace_candidate = str(path or "")
        if self.is_mounted:
            self._refresh_workspace_label()

    def set_agent_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        """Apply live model choices discovered from provider CLIs."""
        changed = False
        for name, choices in choices_by_agent.items():
            next_choices = tuple(choices)
            if tuple(self._agent_model_choices.get(name, ())) == next_choices:
                continue
            self._agent_model_choices[name] = next_choices
            changed = True
        if changed and self.is_mounted:
            self._apply_model_choices()

    def _apply_model_choices(self) -> None:
        if not self._agent_model_choices:
            return
        selector = self.query_one(AgentRecipientModelSelector)
        for name, choices in self._agent_model_choices.items():
            selector.set_model_choices(name, choices)

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        for provider in snapshot.providers:
            state = self._provider_panel_state(provider)
            if self._provider_state_cache.get(provider.name) == state:
                continue
            panel_id = f"#provider-{provider.name}"
            matches = self.query(panel_id)
            if not matches:
                continue
            panel = matches.first(ProviderPanel)
            panel.update_state(state)
            self._provider_state_cache[provider.name] = state
        self._refresh_central()
        self._refresh_questions()
        self._refresh_inspector()
        self._refresh_workspace_label()
        self._apply_activity_frame()

    def on_question_panel_question_answered(
        self,
        event: QuestionPanel.QuestionAnswered,
    ) -> None:
        event.stop()
        self.post_message(self.QuestionAnswered(event.answer))

    def on_central_agent_view_blueprint_action_requested(
        self,
        event: CentralAgentView.BlueprintActionRequested,
    ) -> None:
        event.stop()
        if event.action.startswith("repair-"):
            self.post_message(self.RepairActionRequested(event.action, self.snapshot))
            return
        if event.action.startswith("provider-error-"):
            answer = self._provider_error_action_answer(event.action)
            if answer:
                self.post_message(
                    self.QuestionAnswered(
                        QuestionAnswer(PROVIDER_ERROR_GATE_QUESTION_ID, answer)
                    )
                )
            return
        if event.action == "execution-retry":
            self.post_message(self.SlashCommandSubmitted("/execute-retry all"))
            return
        if event.action == "execute":
            self.post_message(self.ExecuteRequested(self.snapshot))
            return
        if event.action.startswith("refine-"):
            self._submit_follow_up(self._refine_prompt(event.action))

    def update_provider(
        self,
        name: str,
        *,
        status: str,
        summary: str = "",
    ) -> None:
        spec = self.config.agents.get(name)
        if spec is None:
            return
        panel = self.query_one(f"#provider-{name}", ProviderPanel)
        state = self._state_from_spec(name, spec, status=status, summary=summary)
        panel.update_state(state)
        self._provider_state_cache[name] = state
        panel.set_activity_frame(self._activity_frame)

    def on_prompt_composer_submitted(self, event: PromptComposer.Submitted) -> None:
        event.stop()
        self._submit_follow_up(event.text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-provider-inspector":
            event.stop()
            self.action_open_inspector()
        elif event.button.id == "request-execute":
            event.stop()
            self.action_request_execute()
        elif event.button.id == "select-workspace":
            event.stop()
            self.action_request_workspace()

    def action_submit_follow_up(self) -> None:
        composer = self.query_one("#nexus-composer", PromptComposer)
        self._submit_follow_up(composer.submission_text)

    def action_open_inspector(self) -> None:
        self.post_message(self.InspectorRequested(self.snapshot))

    def action_request_execute(self) -> None:
        self.post_message(self.ExecuteRequested(self.snapshot))

    def action_request_workspace(self) -> None:
        self.post_message(self.WorkspaceRequested(self.snapshot))

    def _refresh_workspace_label(self) -> None:
        matches = self.query("#nexus-target-workspace")
        if not matches:
            return
        label = self._workspace_label()
        if label == self._workspace_label_key:
            return
        matches.first(Static).update(label)
        self._workspace_label_key = label

    def _workspace_label(self) -> str:
        target = self._current_workspace_text()
        if target:
            return self._label("workspace_selected").format(target=target)
        return self._label("workspace_not_selected")

    def _current_workspace_text(self) -> str:
        if self.snapshot and self.snapshot.target_workspace.strip():
            return self.snapshot.target_workspace.strip()
        return self._workspace_candidate.strip()

    def _submit_follow_up(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        if is_slash_command_text(cleaned):
            self.query_one("#nexus-composer", PromptComposer).clear()
            self.post_message(self.SlashCommandSubmitted(cleaned))
            return
        selector = self.query_one(AgentRecipientModelSelector)
        target_agents = selector.selected_agents()
        if not target_agents:
            self.app.notify(self._label("select_agent_warning"), severity="warning")
            return
        self.follow_ups.append(cleaned)
        self.query_one("#nexus-composer", PromptComposer).clear()
        self._refresh_central()
        self.post_message(
            self.FollowUpSubmitted(
                cleaned,
                target_agents,
                selector.model_overrides(),
            )
        )

    def _refine_prompt(self, action: str) -> str:
        prompts_ko = {
            "refine-features": (
                "현재 설계에서 핵심 기능, 게임 루프, 사용자 경험을 더 구체화하고 "
                "빠진 결정 사항을 정리해라."
            ),
            "refine-risks": (
                "현재 설계의 실행 리스크, 안티패턴 가능성, 성능 우려, 검증 기준을 "
                "더 구체화해라."
            ),
            "refine-work-packages": (
                "현재 작업 패키지의 범위, 담당 에이전트, 의존성, 병렬 실행 가능성을 다시 "
                "검토하고 필요한 재분배안을 제안해라."
            ),
        }
        prompts_en = {
            "refine-features": (
                "Refine the current blueprint around core features, gameplay loop, "
                "user experience, and missing decisions."
            ),
            "refine-risks": (
                "Refine the current blueprint around execution risks, possible "
                "anti-patterns, performance concerns, and validation criteria."
            ),
            "refine-work-packages": (
                "Review the current WP scope, owner agents, dependencies, and "
                "parallel execution plan, then propose any needed rebalance."
            ),
        }
        if self.config.lang == "ko":
            return prompts_ko.get(action, prompts_ko["refine-features"])
        return prompts_en.get(action, prompts_en["refine-features"])

    @staticmethod
    def _provider_error_action_answer(action: str) -> str:
        answers = {
            "provider-error-retry": PROVIDER_ERROR_RETRY_OPTION,
            "provider-error-continue": PROVIDER_ERROR_CONTINUE_OPTION,
            "provider-error-stop": PROVIDER_ERROR_STOP_OPTION,
        }
        return answers.get(action, "")

    def advance_activity_frame(self) -> None:
        """Advance running indicators for provider and central-agent surfaces."""
        if not self._has_activity_frame_targets():
            return
        self._activity_frame = (self._activity_frame + 1) % 4
        self._apply_activity_frame()

    def _has_activity_frame_targets(self) -> bool:
        if not self.is_mounted:
            return False
        central = self.query_one(CentralAgentView)
        if central.has_running_activity():
            return True
        return any(panel.has_running_activity() for panel in self.query(ProviderPanel))

    def _initial_provider_states(self) -> list[ProviderPanelState]:
        return [
            self._state_from_spec(name, spec)
            for name, spec in self.config.agents.items()
        ]

    @staticmethod
    def _provider_panel_state(provider: ProviderSnapshot) -> ProviderPanelState:
        return ProviderPanelState(
            name=provider.name,
            provider=provider.provider,
            enabled=provider.enabled,
            status=provider.status,
            summary=provider.summary,
            response_status=provider.response_status,
            configured_model=provider.configured_model,
            actual_model=provider.actual_model,
            model_label=provider.model_label,
            context_window=provider.context_window,
            budget_source=provider.budget_source,
            session_id=provider.session_id,
            output_contract=provider.output_contract,
            quality_signal_count=provider.quality_signal_count,
            quality_success_count=provider.quality_success_count,
            quality_score=provider.quality_score,
        )

    def _label(self, key: str) -> str:
        labels = NEXUS_LABELS.get(self.config.lang, NEXUS_LABELS["en"])
        return labels.get(key, NEXUS_LABELS["en"][key])

    def _state_from_spec(
        self,
        name: str,
        spec: AgentSpec,
        *,
        status: str | None = None,
        summary: str = "",
    ) -> ProviderPanelState:
        default_status = "Queued" if spec.enabled else "Disabled"
        return ProviderPanelState(
            name=name,
            provider=spec.provider.value,
            enabled=spec.enabled,
            status=status or default_status,
            summary=summary,
            configured_model=spec.model,
            context_window=spec.effective_context_budget,
            budget_source="trinity_config",
            output_contract=spec.profile.output_contracts.get("execute", ""),
        )

    def _refresh_central(self) -> None:
        central = self.query_one(CentralAgentView)
        if self.snapshot is not None:
            central.apply_snapshot(self.snapshot)
            return
        central.apply_snapshot(self._fallback_snapshot())

    def _refresh_questions(self) -> None:
        question_panel = self.query_one(QuestionPanel)
        snapshot = self.snapshot or self._fallback_snapshot()
        question_panel.apply_questions(snapshot.questions)

    def _refresh_inspector(self) -> None:
        inspector = self.query_one(WorkflowInspector)
        inspector.apply_snapshot(self.snapshot or self._fallback_snapshot())

    def _fallback_snapshot(self) -> WorkflowNexusSnapshot:
        return WorkflowNexusSnapshot(
            goal=self.initial_prompt,
            questions=[],
            work_packages=[
                f"follow-up: {item}" for item in self.follow_ups[-3:]
            ],
        )

    def _apply_activity_frame(self) -> None:
        if not self.is_mounted:
            return
        for panel in self.query(ProviderPanel):
            panel.set_activity_frame(self._activity_frame)
        self.query_one(CentralAgentView).set_activity_frame(self._activity_frame)
