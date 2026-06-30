"""Start screen for the Textual workbench."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from trinity.config import TrinityConfig
from trinity.textual_app.project_start_runtime import project_setup_next_action
from trinity.providers.model_discovery import ProviderModelChoice
from trinity.slash_commands import is_slash_command_text
from trinity.textual_app.i18n import localize_bindings
from trinity.textual_app.workspace_labels import (
    ProjectAnalyzeActionPresentation,
    provider_cli_setup_label,
    project_analyze_action_presentation,
    project_brief_action_label_key,
    project_brief_action_variant,
    project_create_action_variant,
    project_existing_diagnostic_label,
    project_generation_preview_label,
    project_intake_state_label,
    project_mode_rail_label,
    project_plan_preview_label,
    project_start_choice_guide_label,
    project_startup_readiness_label,
    provider_execution_review_policy_label,
    project_read_first_checklist_label,
    project_validation_plan_label,
    target_workspace_state_label,
)
from trinity.textual_app.widgets.agent_recipient_model_selector import (
    AgentRecipientModelSelector,
)
from trinity.textual_app.widgets.composer import PromptComposer
from trinity.tui.sacred_geometry import SacredGeometryAnimator


START_LABELS = {
    "en": {
        "analyze_workspace": "Analyze Existing",
        "analyze_selected_workspace": "Analyze Selected",
        "complete_brief": "Complete Brief",
        "continue_setup": "Continue Setup",
        "create_project": "Create New",
        "edit_brief": "Edit Brief",
        "focus_existing": "Existing",
        "focus_new": "New",
        "placeholder": "What should Trinity work on?",
        "refresh_analysis": "Refresh Analysis",
        "select_agent_warning": "Select at least one agent.",
        "select_workspace": "Select Workspace",
        "subtitle": "Three minds, one context",
    },
    "ko": {
        "analyze_workspace": "기존 프로젝트 분석",
        "analyze_selected_workspace": "선택 대상 분석",
        "complete_brief": "브리프 완성",
        "continue_setup": "설정 계속",
        "create_project": "새 프로젝트 생성",
        "edit_brief": "브리프 편집",
        "focus_existing": "기존",
        "focus_new": "신규",
        "placeholder": "Trinity가 무엇을 진행하면 될까요?",
        "refresh_analysis": "분석 갱신",
        "select_agent_warning": "에이전트를 하나 이상 선택하세요.",
        "select_workspace": "작업 폴더 선택",
        "subtitle": "세 개의 관점, 하나의 컨텍스트",
    },
}


class SacredGeometryAnimation(Static):
    """Textual wrapper for the Trinity ASCII geometry animation."""

    def __init__(self) -> None:
        super().__init__("", id="start-geometry")
        self._angle = 0.0
        self._animator = SacredGeometryAnimator(width=56, height=14, mode="ascii")

    def on_mount(self) -> None:
        self._render_frame()
        self.set_interval(0.12, self._tick)

    def _tick(self) -> None:
        self._angle = (self._angle + 8.0) % 360.0
        self._render_frame()

    def _render_frame(self) -> None:
        self.update(self._animator.render(angle=self._angle))


class StartScreen(Screen[None]):
    """Initial prompt and optional workspace candidate screen."""

    class Submitted(Message):
        """Posted when the user starts planning from the first prompt."""

        def __init__(
            self,
            prompt: str,
            workspace_candidate: Path | None,
            target_agents: tuple[str, ...],
            agent_model_overrides: dict[str, str],
        ) -> None:
            super().__init__()
            self.prompt = prompt
            self.workspace_candidate = workspace_candidate
            self.target_agents = target_agents
            self.agent_model_overrides = agent_model_overrides

    class SlashCommandSubmitted(Message):
        """Posted when the first prompt is a Trinity slash command."""

        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class WorkspaceRequested(Message):
        """Posted when the user wants to choose a workspace candidate early."""

    class ProjectIntakeRequested(Message):
        """Posted when the user wants to analyze the current workspace candidate."""

    class NewProjectRequested(Message):
        """Posted when the user wants to create a new project workspace."""

    class ProjectBriefRequested(Message):
        """Posted when the user wants to edit the project brief."""

    class ProjectScopeRequested(Message):
        """Posted when the user wants to choose an existing-project scope."""

    class ProjectReadFirstRequested(Message):
        """Posted when the user wants to confirm existing-project read-first anchors."""

    class ProjectValidationRequested(Message):
        """Posted when the user wants to record validation commands."""

    BINDINGS = [
        ("ctrl+enter", "submit", "Plan"),
    ]

    LOCALIZED_BINDINGS = {
        ("ctrl+enter", "submit"): ("binding_plan", None),
    }

    def __init__(
        self,
        config: TrinityConfig,
        workspace_candidate: Path | None = None,
        *,
        initial_prompt: str = "",
        lang: str = "en",
    ) -> None:
        super().__init__(name="start")
        self.config = config
        self.workspace_candidate = workspace_candidate
        self.initial_prompt = initial_prompt
        self.lang = lang
        self._agent_model_choices: dict[str, tuple[ProviderModelChoice, ...]] = {}
        self._workspace_label_key = self._workspace_label()
        self._composer: PromptComposer | None = None
        self._recipient_selector: AgentRecipientModelSelector | None = None
        self._workspace_label_widget: Static | None = None
        self._provider_policy_widget: Static | None = None
        self._provider_cli_setup_widget: Static | None = None
        self._project_startup_readiness_widget: Static | None = None
        self._project_start_choice_guide_widget: Static | None = None
        self._project_mode_rail_widget: Static | None = None
        self._project_plan_preview_widget: Static | None = None
        self._project_generation_preview_widget: Static | None = None
        self._project_validation_plan_widget: Static | None = None
        self._project_existing_diagnostic_widget: Static | None = None
        self._project_read_first_checklist_widget: Static | None = None
        self.project_mode_focus = "auto"
        localize_bindings(self._bindings, self.lang, self.LOCALIZED_BINDINGS)

    def compose(self) -> ComposeResult:
        self._reset_widget_cache()
        yield Header(show_clock=False)
        with Vertical(id="start-screen"):
            with Vertical(id="start-shell"):
                yield SacredGeometryAnimation()
                yield Static("TRINITY", id="start-title")
                yield Static(self._label("subtitle"), id="start-subtitle")
                composer = PromptComposer(
                    placeholder=self._label("placeholder"),
                    initial_text=self.initial_prompt,
                    id="start-composer",
                    lang=self.lang,
                )
                self._composer = composer
                yield composer
                selector = AgentRecipientModelSelector(
                    self.config.agents,
                    id="start-recipient-selector",
                    lang=self.lang,
                )
                self._recipient_selector = selector
                yield selector
                provider_policy = Static(
                    self._provider_policy_label(),
                    id="start-provider-policy",
                )
                self._provider_policy_widget = provider_policy
                yield provider_policy
                provider_cli_setup = Static(
                    self._provider_cli_setup_label(),
                    id="start-provider-cli-setup",
                )
                self._provider_cli_setup_widget = provider_cli_setup
                yield provider_cli_setup
                with Horizontal(id="start-actions"):
                    workspace_label = Static(
                        self._workspace_label(),
                        id="workspace-candidate",
                    )
                    self._workspace_label_widget = workspace_label
                    yield workspace_label
                    yield Button(
                        self._label("select_workspace"),
                        id="choose-workspace",
                        variant="default",
                    )
                startup_readiness = Static(
                    self._project_startup_readiness_label(),
                    id="project-startup-readiness",
                )
                self._project_startup_readiness_widget = startup_readiness
                yield startup_readiness
                yield Static(
                    self._project_intake_label(),
                    id="project-intake-summary",
                )
                existing_diagnostic = Static(
                    self._project_existing_diagnostic_label(),
                    id="project-existing-diagnostic",
                )
                self._project_existing_diagnostic_widget = existing_diagnostic
                yield existing_diagnostic
                start_choice_guide = Static(
                    self._project_start_choice_guide_label(),
                    id="project-start-choice-guide",
                )
                self._project_start_choice_guide_widget = start_choice_guide
                yield start_choice_guide
                with Horizontal(id="project-mode-focus-actions"):
                    yield Button(
                        self._label("focus_existing"),
                        id="focus-existing-project",
                        variant=self._project_mode_focus_variant("existing"),
                    )
                    yield Button(
                        self._label("focus_new"),
                        id="focus-new-project",
                        variant=self._project_mode_focus_variant("new"),
                    )
                analyze_action = self._project_analyze_action_presentation()
                with Horizontal(id="project-intake-actions"):
                    yield Button(
                        self._label("continue_setup"),
                        id="continue-project-setup",
                        variant="primary",
                    )
                    yield Button(
                        self._label(analyze_action.label_key),
                        id="analyze-workspace",
                        variant=analyze_action.variant,
                    )
                    yield Button(
                        self._label("create_project"),
                        id="create-project",
                        variant=self._project_create_action_variant(),
                    )
                    yield Button(
                        self._label(self._project_brief_action_label_key()),
                        id="edit-project-brief",
                        variant=self._project_brief_action_variant(),
                    )
                mode_rail = Static(
                    self._project_mode_rail_label(),
                    id="project-mode-rail",
                )
                self._project_mode_rail_widget = mode_rail
                yield mode_rail
                plan_preview = Static(
                    self._project_plan_preview_label(),
                    id="project-plan-preview",
                )
                self._project_plan_preview_widget = plan_preview
                yield plan_preview
                generation_preview = Static(
                    self._project_generation_preview_label(),
                    id="project-generation-preview",
                )
                self._project_generation_preview_widget = generation_preview
                yield generation_preview
                validation_plan = Static(
                    self._project_validation_plan_label(),
                    id="project-validation-plan",
                )
                self._project_validation_plan_widget = validation_plan
                yield validation_plan
                read_first_checklist = Static(
                    self._project_read_first_checklist_label(),
                    id="project-read-first-checklist",
                )
                self._project_read_first_checklist_widget = read_first_checklist
                yield read_first_checklist
        yield Footer()

    def on_mount(self) -> None:
        self._apply_model_choices()
        self._prompt_composer().focus_text_area()

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

    def on_prompt_composer_submitted(self, event: PromptComposer.Submitted) -> None:
        event.stop()
        self._submit(event.text)

    def on_agent_recipient_model_selector_selection_changed(
        self,
        event: AgentRecipientModelSelector.SelectionChanged,
    ) -> None:
        event.stop()
        self._refresh_provider_policy_label(event.selected_agents)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "continue-project-setup":
            event.stop()
            self._continue_project_setup()
        elif button_id == "focus-existing-project":
            event.stop()
            self._set_project_mode_focus("existing")
        elif button_id == "focus-new-project":
            event.stop()
            self._set_project_mode_focus("new")
        elif button_id == "choose-workspace":
            event.stop()
            self.post_message(self.WorkspaceRequested())
        elif button_id == "analyze-workspace":
            event.stop()
            self._set_project_mode_focus("existing")
            self.post_message(self.ProjectIntakeRequested())
        elif button_id == "create-project":
            event.stop()
            self._set_project_mode_focus("new")
            self.post_message(self.NewProjectRequested())
        elif button_id == "edit-project-brief":
            event.stop()
            self.post_message(self.ProjectBriefRequested())

    def action_submit(self) -> None:
        composer = self._prompt_composer()
        self._submit(composer.submission_text)

    def _continue_project_setup(self) -> None:
        action = self._project_setup_next_action()
        if action == "workspace":
            self.post_message(self.WorkspaceRequested())
        elif action == "analyze":
            self.post_message(self.ProjectIntakeRequested())
        elif action == "create":
            self.post_message(self.NewProjectRequested())
        elif action == "brief":
            self.post_message(self.ProjectBriefRequested())
        elif action == "scope":
            self.post_message(self.ProjectScopeRequested())
        elif action == "read_first":
            self.post_message(self.ProjectReadFirstRequested())
        elif action == "validation":
            self.post_message(self.ProjectValidationRequested())
        else:
            composer = self._prompt_composer()
            self._submit(composer.submission_text)

    def _project_setup_next_action(self) -> str:
        return project_setup_next_action(
            self.config.effective_state_dir,
            self.workspace_candidate,
            ready_action="plan",
            analyze_variant=self._project_analyze_action_presentation().variant,
            preferred_mode=self.project_mode_focus,
        )

    def set_workspace_candidate(self, path: Path | None) -> None:
        next_workspace = str(path or "")
        if path == self.workspace_candidate or next_workspace == str(
            self.workspace_candidate or ""
        ):
            return
        self.workspace_candidate = path
        if not self.is_mounted:
            self._workspace_label_key = self._workspace_label()
            return
        workspace_label = self._workspace_label()
        if workspace_label != self._workspace_label_key:
            self._workspace_label_static().update(workspace_label)
            self._workspace_label_key = workspace_label
        self.refresh_project_intake_summary()

    def _submit(self, prompt: str) -> None:
        text = prompt.strip()
        if not text:
            composer = self._prompt_composer()
            composer.focus_text_area()
            return
        if is_slash_command_text(text):
            self._prompt_composer().clear()
            self.post_message(self.SlashCommandSubmitted(text))
            return
        selector = self._agent_selector()
        target_agents = selector.selected_agents()
        if not target_agents:
            self.app.notify(self._label("select_agent_warning"), severity="warning")
            return
        self.post_message(
            self.Submitted(
                text,
                self.workspace_candidate,
                target_agents,
                selector.model_overrides(),
            )
        )

    def _reset_widget_cache(self) -> None:
        self._composer = None
        self._recipient_selector = None
        self._workspace_label_widget = None
        self._provider_policy_widget = None
        self._provider_cli_setup_widget = None
        self._project_startup_readiness_widget = None
        self._project_start_choice_guide_widget = None
        self._project_mode_rail_widget = None
        self._project_plan_preview_widget = None
        self._project_generation_preview_widget = None
        self._project_validation_plan_widget = None
        self._project_existing_diagnostic_widget = None
        self._project_read_first_checklist_widget = None

    def _prompt_composer(self) -> PromptComposer:
        if self._composer is None:
            self._composer = self.query_one("#start-composer", PromptComposer)
        return self._composer

    def _agent_selector(self) -> AgentRecipientModelSelector:
        if self._recipient_selector is None:
            self._recipient_selector = self.query_one(AgentRecipientModelSelector)
        return self._recipient_selector

    def _workspace_label_static(self) -> Static:
        if self._workspace_label_widget is None:
            self._workspace_label_widget = self.query_one("#workspace-candidate", Static)
        return self._workspace_label_widget

    def _provider_policy_static(self) -> Static:
        if self._provider_policy_widget is None:
            self._provider_policy_widget = self.query_one(
                "#start-provider-policy",
                Static,
            )
        return self._provider_policy_widget

    def _provider_cli_setup_static(self) -> Static:
        if self._provider_cli_setup_widget is None:
            self._provider_cli_setup_widget = self.query_one(
                "#start-provider-cli-setup",
                Static,
            )
        return self._provider_cli_setup_widget

    def _project_startup_readiness_static(self) -> Static:
        if self._project_startup_readiness_widget is None:
            self._project_startup_readiness_widget = self.query_one(
                "#project-startup-readiness",
                Static,
            )
        return self._project_startup_readiness_widget

    def _project_start_choice_guide_static(self) -> Static:
        if self._project_start_choice_guide_widget is None:
            self._project_start_choice_guide_widget = self.query_one(
                "#project-start-choice-guide",
                Static,
            )
        return self._project_start_choice_guide_widget

    def _project_plan_preview_static(self) -> Static:
        if self._project_plan_preview_widget is None:
            self._project_plan_preview_widget = self.query_one(
                "#project-plan-preview",
                Static,
            )
        return self._project_plan_preview_widget

    def _project_generation_preview_static(self) -> Static:
        if self._project_generation_preview_widget is None:
            self._project_generation_preview_widget = self.query_one(
                "#project-generation-preview",
                Static,
            )
        return self._project_generation_preview_widget

    def _project_validation_plan_static(self) -> Static:
        if self._project_validation_plan_widget is None:
            self._project_validation_plan_widget = self.query_one(
                "#project-validation-plan",
                Static,
            )
        return self._project_validation_plan_widget

    def _project_read_first_checklist_static(self) -> Static:
        if self._project_read_first_checklist_widget is None:
            self._project_read_first_checklist_widget = self.query_one(
                "#project-read-first-checklist",
                Static,
            )
        return self._project_read_first_checklist_widget

    def _project_existing_diagnostic_static(self) -> Static:
        if self._project_existing_diagnostic_widget is None:
            self._project_existing_diagnostic_widget = self.query_one(
                "#project-existing-diagnostic",
                Static,
            )
        return self._project_existing_diagnostic_widget

    def _project_mode_rail_static(self) -> Static:
        if self._project_mode_rail_widget is None:
            self._project_mode_rail_widget = self.query_one(
                "#project-mode-rail",
                Static,
            )
        return self._project_mode_rail_widget

    def _workspace_label(self) -> str:
        return target_workspace_state_label(
            self.workspace_candidate,
            control_repo=self.config.project_dir,
            lang=self.lang,
        )

    def _project_intake_label(self) -> str:
        return project_intake_state_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_plan_preview_label(self) -> str:
        return project_plan_preview_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_generation_preview_label(self) -> str:
        return project_generation_preview_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_validation_plan_label(self) -> str:
        return project_validation_plan_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_read_first_checklist_label(self) -> str:
        return project_read_first_checklist_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_existing_diagnostic_label(self) -> str:
        return project_existing_diagnostic_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_startup_readiness_label(
        self,
        selected_agents: tuple[str, ...] | None = None,
    ) -> str:
        if selected_agents is None and self.is_mounted:
            selected_agents = self._agent_selector().selected_agents()
        return project_startup_readiness_label(
            self.config.effective_state_dir,
            self.config.agents,
            selected_agents=selected_agents,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_start_choice_guide_label(self) -> str:
        return project_start_choice_guide_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _provider_policy_label(
        self,
        selected_agents: tuple[str, ...] | None = None,
    ) -> str:
        if selected_agents is None and self.is_mounted:
            selected_agents = self._agent_selector().selected_agents()
        return provider_execution_review_policy_label(
            self.config.agents,
            selected_agents=selected_agents,
            lang=self.lang,
        )

    def _provider_cli_setup_label(
        self,
        selected_agents: tuple[str, ...] | None = None,
    ) -> str:
        if selected_agents is None and self.is_mounted:
            selected_agents = self._agent_selector().selected_agents()
        return provider_cli_setup_label(
            self.config.agents,
            selected_agents=selected_agents,
            lang=self.lang,
        )

    def _project_mode_rail_label(self) -> str:
        return project_mode_rail_label(
            self.config.effective_state_dir,
            lang=self.lang,
            target_workspace=self.workspace_candidate,
        )

    def _project_brief_action_variant(self) -> str:
        return project_brief_action_variant(
            self.config.effective_state_dir,
            target_workspace=self.workspace_candidate,
        )

    def _project_brief_action_label_key(self) -> str:
        return project_brief_action_label_key(
            self.config.effective_state_dir,
            target_workspace=self.workspace_candidate,
        )

    def _project_analyze_action_presentation(
        self,
    ) -> ProjectAnalyzeActionPresentation:
        return project_analyze_action_presentation(
            self.config.effective_state_dir,
            target_workspace=self.workspace_candidate,
        )

    def _project_create_action_variant(self) -> str:
        return project_create_action_variant(
            self.config.effective_state_dir,
            target_workspace=self.workspace_candidate,
        )

    def refresh_project_intake_summary(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#project-intake-summary", Static).update(
            self._project_intake_label()
        )
        self._project_startup_readiness_static().update(
            self._project_startup_readiness_label()
        )
        self._project_start_choice_guide_static().update(
            self._project_start_choice_guide_label()
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
        self._project_existing_diagnostic_static().update(
            self._project_existing_diagnostic_label()
        )
        self._project_read_first_checklist_static().update(
            self._project_read_first_checklist_label()
        )
        self._project_mode_rail_static().update(
            self._project_mode_rail_label()
        )
        analyze_action = self._project_analyze_action_presentation()
        analyze_button = self.query_one("#analyze-workspace", Button)
        analyze_button.label = self._label(analyze_action.label_key)
        analyze_button.variant = analyze_action.variant
        self.query_one("#create-project", Button).variant = (
            self._project_create_action_variant()
        )
        brief_button = self.query_one("#edit-project-brief", Button)
        brief_button.label = self._label(self._project_brief_action_label_key())
        brief_button.variant = self._project_brief_action_variant()
        self._refresh_project_mode_focus_buttons()

    def _set_project_mode_focus(self, mode: str) -> None:
        normalized = mode if mode in {"existing", "new"} else "auto"
        if self.project_mode_focus == normalized:
            return
        self.project_mode_focus = normalized
        self._refresh_project_mode_focus_buttons()

    def _refresh_project_mode_focus_buttons(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#focus-existing-project", Button).variant = (
            self._project_mode_focus_variant("existing")
        )
        self.query_one("#focus-new-project", Button).variant = (
            self._project_mode_focus_variant("new")
        )

    def _project_mode_focus_variant(self, mode: str) -> str:
        if self.project_mode_focus == mode:
            return "primary"
        return "default"

    def _refresh_provider_policy_label(
        self,
        selected_agents: tuple[str, ...] | None = None,
    ) -> None:
        if not self.is_mounted:
            return
        self._provider_policy_static().update(
            self._provider_policy_label(selected_agents)
        )
        self._provider_cli_setup_static().update(
            self._provider_cli_setup_label(selected_agents)
        )
        self._project_startup_readiness_static().update(
            self._project_startup_readiness_label(selected_agents)
        )

    def _label(self, key: str) -> str:
        labels = START_LABELS.get(self.lang, START_LABELS["en"])
        return labels.get(key, START_LABELS["en"][key])
