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
from trinity.textual_app.workspace_labels import (
    ProjectAnalyzeActionPresentation,
    project_analyze_action_presentation,
    project_brief_action_variant,
    project_create_action_variant,
    project_generation_preview_label,
    project_intake_state_label,
    project_mode_rail_label,
    project_plan_preview_label,
    project_validation_plan_label,
    target_workspace_state_label,
)
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.textual_app.widgets.central_agent import CentralAgentView
from trinity.textual_app.widgets.inspector import WorkflowInspector
from trinity.textual_app.widgets.provider_panel import ProviderPanel, ProviderPanelState
from trinity.textual_app.widgets.question_panel import QuestionAnswer, QuestionPanel
from trinity.workflow.provider_error_gate import (
    PROVIDER_ERROR_CONTINUE_OPTION,
    PROVIDER_ERROR_GATE_QUESTION_ID,
    PROVIDER_ERROR_RETRY_OPTION,
    PROVIDER_ERROR_STOP_OPTION,
)


NEXUS_LABELS = {
    "en": {
        "analyze_workspace": "Analyze Existing",
        "composer_placeholder": "Reply, refine direction, or type / for commands",
        "create_project": "Create New",
        "edit_brief": "Edit Brief",
        "execute": "Execute",
        "open_provider_inspector": "Open Provider Inspector",
        "refresh_analysis": "Refresh Analysis",
        "select_agent_warning": "Select at least one agent.",
        "select_workspace": "Select Workspace",
    },
    "ko": {
        "analyze_workspace": "기존 프로젝트 분석",
        "composer_placeholder": "답변, 방향 조정 또는 /로 명령 입력",
        "create_project": "새 프로젝트 생성",
        "edit_brief": "브리프 편집",
        "execute": "실행",
        "open_provider_inspector": "프로바이더 인스펙터 열기",
        "refresh_analysis": "분석 갱신",
        "select_agent_warning": "에이전트를 하나 이상 선택하세요.",
        "select_workspace": "작업 폴더 선택",
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

    class ProjectIntakeRequested(Message):
        """Posted when the user wants to analyze the current Nexus workspace."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    class NewProjectRequested(Message):
        """Posted when the user wants to create a new project workspace."""

        def __init__(self, snapshot: WorkflowNexusSnapshot | None) -> None:
            super().__init__()
            self.snapshot = snapshot

    class ProjectBriefRequested(Message):
        """Posted when the user wants to edit the project brief."""

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
        self._applied_snapshot_identity: int | None = None
        self._provider_panels: dict[str, ProviderPanel] = {}
        self._workspace_label_widget: Static | None = None
        self._central_view: CentralAgentView | None = None
        self._question_panel: QuestionPanel | None = None
        self._inspector: WorkflowInspector | None = None
        self._recipient_selector: AgentRecipientModelSelector | None = None
        self._composer: PromptComposer | None = None
        self._project_mode_rail_widget: Static | None = None
        self._project_plan_preview_widget: Static | None = None
        self._project_generation_preview_widget: Static | None = None
        self._project_validation_plan_widget: Static | None = None

    def compose(self) -> ComposeResult:
        self._reset_widget_cache()
        self._reset_render_cache()
        yield Header(show_clock=False)
        with Vertical(id="nexus-screen"):
            with Horizontal(id="provider-strip"):
                for state in self._initial_provider_states():
                    panel = ProviderPanel(
                        state,
                        id=f"provider-{state.name}",
                        lang=self.config.lang,
                    )
                    self._provider_panels[state.name] = panel
                    yield panel
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
                workspace_label_text = self._workspace_label()
                workspace_label = Static(
                    workspace_label_text,
                    id="nexus-target-workspace",
                )
                self._workspace_label_widget = workspace_label
                self._workspace_label_key = workspace_label_text
                yield workspace_label
                yield Button(
                    self._label("execute"),
                    id="request-execute",
                    variant="primary",
                )
            yield Static(
                self._project_intake_label(),
                id="nexus-project-intake-summary",
            )
            analyze_action = self._project_analyze_action_presentation()
            with Horizontal(id="nexus-project-intake-actions"):
                yield Button(
                    self._label(analyze_action.label_key),
                    id="nexus-analyze-workspace",
                    variant=analyze_action.variant,
                )
                yield Button(
                    self._label("create_project"),
                    id="nexus-create-project",
                    variant=self._project_create_action_variant(),
                )
                yield Button(
                    self._label("edit_brief"),
                    id="nexus-edit-project-brief",
                    variant=self._project_brief_action_variant(),
                )
            mode_rail = Static(
                self._project_mode_rail_label(),
                id="nexus-project-mode-rail",
            )
            self._project_mode_rail_widget = mode_rail
            yield mode_rail
            plan_preview = Static(
                self._project_plan_preview_label(),
                id="nexus-project-plan-preview",
            )
            self._project_plan_preview_widget = plan_preview
            yield plan_preview
            generation_preview = Static(
                self._project_generation_preview_label(),
                id="nexus-project-generation-preview",
            )
            self._project_generation_preview_widget = generation_preview
            yield generation_preview
            validation_plan = Static(
                self._project_validation_plan_label(),
                id="nexus-project-validation-plan",
            )
            self._project_validation_plan_widget = validation_plan
            yield validation_plan
            with Horizontal(id="nexus-main"):
                with Vertical(id="nexus-center-stack"):
                    central = CentralAgentView(id="central-agent", lang=self.config.lang)
                    self._central_view = central
                    yield central
                    question_panel = QuestionPanel(
                        id="nexus-question-panel",
                        lang=self.config.lang,
                    )
                    self._question_panel = question_panel
                    yield question_panel
                inspector = WorkflowInspector(id="workflow-inspector", lang=self.config.lang)
                self._inspector = inspector
                yield inspector
            selector = AgentRecipientModelSelector(
                self.config.agents,
                id="nexus-recipient-selector",
                lang=self.config.lang,
            )
            self._recipient_selector = selector
            yield selector
            composer = PromptComposer(
                placeholder=self._label("composer_placeholder"),
                id="nexus-composer",
                lang=self.config.lang,
            )
            self._composer = composer
            yield composer
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
        self._prompt_composer().focus_text_area()

    def set_initial_prompt(self, prompt: str) -> None:
        next_prompt = prompt.strip()
        if next_prompt == self.initial_prompt:
            return
        self.initial_prompt = next_prompt
        if self.is_mounted:
            self._refresh_central()

    def set_agent_selection(
        self,
        target_agents: tuple[str, ...] | list[str],
        agent_model_overrides: dict[str, str],
    ) -> None:
        """Apply selection state restored from the Start screen or resume."""
        next_agents = tuple(target_agents)
        next_overrides = dict(agent_model_overrides)
        if (
            next_agents == self._selected_agents
            and next_overrides == self._agent_model_overrides
        ):
            return
        self._selected_agents = next_agents
        self._agent_model_overrides = next_overrides
        if not self.is_mounted:
            return
        self._apply_agent_selection()

    def _apply_agent_selection(self) -> None:
        selector = self._agent_selector()
        if self._selected_agents:
            selector.set_selected_agents(self._selected_agents)
        if self._agent_model_overrides:
            selector.set_model_overrides(self._agent_model_overrides)

    def set_workspace_candidate(self, path: object | None) -> None:
        """Update the visible workspace fallback when no workflow target exists."""
        next_candidate = str(path or "")
        if next_candidate == self._workspace_candidate:
            return
        self._workspace_candidate = next_candidate
        if self.is_mounted:
            self._refresh_workspace_label()

    def set_agent_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]],
    ) -> None:
        """Apply live model choices discovered from provider CLIs."""
        changed_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        for name, choices in choices_by_agent.items():
            next_choices = tuple(choices)
            if tuple(self._agent_model_choices.get(name, ())) == next_choices:
                continue
            self._agent_model_choices[name] = next_choices
            changed_choices[name] = next_choices
        if changed_choices and self.is_mounted:
            self._apply_model_choices(changed_choices)

    def _apply_model_choices(
        self,
        choices_by_agent: dict[str, tuple[ProviderModelChoice, ...]] | None = None,
    ) -> None:
        if not self._agent_model_choices:
            return
        selector = self._agent_selector()
        for name, choices in (choices_by_agent or self._agent_model_choices).items():
            selector.set_model_choices(name, choices)

    def _reset_widget_cache(self) -> None:
        self._provider_panels = {}
        self._workspace_label_widget = None
        self._central_view = None
        self._question_panel = None
        self._inspector = None
        self._recipient_selector = None
        self._composer = None
        self._project_mode_rail_widget = None
        self._project_plan_preview_widget = None

    def _reset_render_cache(self) -> None:
        self._provider_state_cache = {}
        self._applied_snapshot_identity = None
        self._workspace_label_key = ""

    def _provider_panel(self, name: str) -> ProviderPanel | None:
        panel = self._provider_panels.get(name)
        if panel is not None:
            return panel
        matches = self.query(f"#provider-{name}")
        if not matches:
            return None
        panel = matches.first(ProviderPanel)
        self._provider_panels[name] = panel
        return panel

    def _workspace_label_static(self) -> Static:
        if self._workspace_label_widget is None:
            self._workspace_label_widget = self.query_one(
                "#nexus-target-workspace",
                Static,
            )
        return self._workspace_label_widget

    def _central_agent(self) -> CentralAgentView:
        if self._central_view is None:
            self._central_view = self.query_one(CentralAgentView)
        return self._central_view

    def _questions(self) -> QuestionPanel:
        if self._question_panel is None:
            self._question_panel = self.query_one(QuestionPanel)
        return self._question_panel

    def _workflow_inspector(self) -> WorkflowInspector:
        if self._inspector is None:
            self._inspector = self.query_one(WorkflowInspector)
        return self._inspector

    def _agent_selector(self) -> AgentRecipientModelSelector:
        if self._recipient_selector is None:
            self._recipient_selector = self.query_one(AgentRecipientModelSelector)
        return self._recipient_selector

    def _prompt_composer(self) -> PromptComposer:
        if self._composer is None:
            self._composer = self.query_one("#nexus-composer", PromptComposer)
        return self._composer

    def _project_plan_preview_static(self) -> Static:
        if self._project_plan_preview_widget is None:
            self._project_plan_preview_widget = self.query_one(
                "#nexus-project-plan-preview",
                Static,
            )
        return self._project_plan_preview_widget

    def _project_generation_preview_static(self) -> Static:
        if self._project_generation_preview_widget is None:
            self._project_generation_preview_widget = self.query_one(
                "#nexus-project-generation-preview",
                Static,
            )
        return self._project_generation_preview_widget

    def _project_validation_plan_static(self) -> Static:
        if self._project_validation_plan_widget is None:
            self._project_validation_plan_widget = self.query_one(
                "#nexus-project-validation-plan",
                Static,
            )
        return self._project_validation_plan_widget

    def _project_mode_rail_static(self) -> Static:
        if self._project_mode_rail_widget is None:
            self._project_mode_rail_widget = self.query_one(
                "#nexus-project-mode-rail",
                Static,
            )
        return self._project_mode_rail_widget

    def apply_snapshot(self, snapshot: WorkflowNexusSnapshot) -> None:
        snapshot_identity = id(snapshot)
        if (
            self.is_mounted
            and self._applied_snapshot_identity == snapshot_identity
        ):
            self.snapshot = snapshot
            return
        self.snapshot = snapshot
        if not self.is_mounted:
            return
        self._applied_snapshot_identity = snapshot_identity
        for provider in snapshot.providers:
            state = self._provider_panel_state(provider)
            if self._provider_state_cache.get(provider.name) == state:
                continue
            panel = self._provider_panel(provider.name)
            if panel is None:
                continue
            panel.update_state(state)
            self._provider_state_cache[provider.name] = state
        self._refresh_central()
        self._refresh_questions()
        self._refresh_inspector()
        self._refresh_workspace_label()
        if self._snapshot_has_activity_frame_targets(snapshot):
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
        state = self._state_from_spec(name, spec, status=status, summary=summary)
        if self._provider_state_cache.get(name) == state:
            return
        panel = self._provider_panel(name)
        if panel is None:
            return
        panel.update_state(state)
        self._provider_state_cache[name] = state
        self._applied_snapshot_identity = None
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
        elif event.button.id == "nexus-analyze-workspace":
            event.stop()
            self.action_request_project_intake()
        elif event.button.id == "nexus-create-project":
            event.stop()
            self.action_request_new_project()
        elif event.button.id == "nexus-edit-project-brief":
            event.stop()
            self.action_request_project_brief()

    def action_submit_follow_up(self) -> None:
        composer = self._prompt_composer()
        self._submit_follow_up(composer.submission_text)

    def action_open_inspector(self) -> None:
        self.post_message(self.InspectorRequested(self.snapshot))

    def action_request_execute(self) -> None:
        self.post_message(self.ExecuteRequested(self.snapshot))

    def action_request_workspace(self) -> None:
        self.post_message(self.WorkspaceRequested(self.snapshot))

    def action_request_project_intake(self) -> None:
        self.post_message(self.ProjectIntakeRequested(self.snapshot))

    def action_request_new_project(self) -> None:
        self.post_message(self.NewProjectRequested(self.snapshot))

    def action_request_project_brief(self) -> None:
        self.post_message(self.ProjectBriefRequested(self.snapshot))

    def _refresh_workspace_label(self) -> None:
        label = self._workspace_label()
        if label == self._workspace_label_key:
            return
        self._workspace_label_static().update(label)
        self._workspace_label_key = label

    def _workspace_label(self) -> str:
        return target_workspace_state_label(
            self._current_workspace_text(),
            control_repo=self.config.project_dir,
            lang=self.config.lang,
        )

    def _project_intake_label(self) -> str:
        return project_intake_state_label(
            self.config.effective_state_dir,
            lang=self.config.lang,
            target_workspace=self._current_workspace_text(),
        )

    def _project_plan_preview_label(self) -> str:
        return project_plan_preview_label(
            self.config.effective_state_dir,
            lang=self.config.lang,
            target_workspace=self._current_workspace_text(),
        )

    def _project_generation_preview_label(self) -> str:
        return project_generation_preview_label(
            self.config.effective_state_dir,
            lang=self.config.lang,
            target_workspace=self._current_workspace_text(),
        )

    def _project_validation_plan_label(self) -> str:
        return project_validation_plan_label(
            self.config.effective_state_dir,
            lang=self.config.lang,
            target_workspace=self._current_workspace_text(),
        )

    def _project_mode_rail_label(self) -> str:
        return project_mode_rail_label(
            self.config.effective_state_dir,
            lang=self.config.lang,
            target_workspace=self._current_workspace_text(),
        )

    def _project_brief_action_variant(self) -> str:
        return project_brief_action_variant(
            self.config.effective_state_dir,
            target_workspace=self._current_workspace_text(),
        )

    def _project_analyze_action_presentation(
        self,
    ) -> ProjectAnalyzeActionPresentation:
        return project_analyze_action_presentation(
            self.config.effective_state_dir,
            target_workspace=self._current_workspace_text(),
        )

    def _project_create_action_variant(self) -> str:
        return project_create_action_variant(
            self.config.effective_state_dir,
            target_workspace=self._current_workspace_text(),
        )

    def refresh_project_intake_summary(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#nexus-project-intake-summary", Static).update(
            self._project_intake_label()
        )
        self._project_plan_preview_static().update(
            self._project_plan_preview_label()
        )
        self._project_generation_preview_static().update(
            self._project_generation_preview_label()
        )
        self._project_validation_plan_static().update(
            self._project_validation_plan_label()
        )
        self._project_mode_rail_static().update(
            self._project_mode_rail_label()
        )
        analyze_action = self._project_analyze_action_presentation()
        analyze_button = self.query_one("#nexus-analyze-workspace", Button)
        analyze_button.label = self._label(analyze_action.label_key)
        analyze_button.variant = analyze_action.variant
        self.query_one("#nexus-create-project", Button).variant = (
            self._project_create_action_variant()
        )
        self.query_one("#nexus-edit-project-brief", Button).variant = (
            self._project_brief_action_variant()
        )

    def _current_workspace_text(self) -> str:
        if self.snapshot and self.snapshot.target_workspace.strip():
            return self.snapshot.target_workspace.strip()
        return self._workspace_candidate.strip()

    def _submit_follow_up(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        if is_slash_command_text(cleaned):
            self._prompt_composer().clear()
            self.post_message(self.SlashCommandSubmitted(cleaned))
            return
        selector = self._agent_selector()
        target_agents = selector.selected_agents()
        if not target_agents:
            self.app.notify(self._label("select_agent_warning"), severity="warning")
            return
        self.follow_ups.append(cleaned)
        self._prompt_composer().clear()
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
        if self.snapshot is not None and self._central_snapshot_is_running(
            self.snapshot
        ):
            return True
        return any(
            ProviderPanel._state_group(state) == "running"
            for state in self._provider_state_cache.values()
        )

    def _snapshot_has_activity_frame_targets(
        self,
        snapshot: WorkflowNexusSnapshot,
    ) -> bool:
        if self._central_snapshot_is_running(snapshot):
            return True
        return any(
            ProviderPanel._state_group(
                self._provider_panel_state(provider)
            ) == "running"
            for provider in snapshot.providers
        )

    @staticmethod
    def _central_snapshot_is_running(snapshot: WorkflowNexusSnapshot) -> bool:
        if snapshot.synthesis.status in {"running", "waiting"}:
            return True
        if snapshot.state in {"preflight", "deliberating", "executing", "reviewing"}:
            return True
        return False

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
        central = self._central_agent()
        if self.snapshot is not None:
            central.apply_snapshot(self.snapshot)
            return
        central.apply_snapshot(self._fallback_snapshot())

    def _refresh_questions(self) -> None:
        question_panel = self._questions()
        snapshot = self.snapshot or self._fallback_snapshot()
        question_panel.apply_questions(snapshot.questions)

    def _refresh_inspector(self) -> None:
        inspector = self._workflow_inspector()
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
        for panel in self._provider_panels.values():
            panel.set_activity_frame(self._activity_frame)
        self._central_agent().set_activity_frame(self._activity_frame)
