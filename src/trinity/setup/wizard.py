"""Interactive setup wizard — guided `trinity init` with CLI detection.

Provides a Rich-based interactive setup flow:
0. Select language (English / Korean)
1. Detect installed CLI tools
2. Let user select which agents to enable
3. Customize role prompts and context budgets
4. Save configuration
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from trinity.i18n import Lang, get_strings, localized_roles_with_caveman
from trinity.models import (
    AgentSpec,
    ModelContextSpec,
    Provider,
    PROVIDER_DEFAULT_MODELS,
    provider_model_choices,
)
from trinity.setup.detector import (
    PROVIDER_DEFAULT_ARGS,
    PROVIDER_DEFAULT_BUDGETS,
    PROVIDER_DISPLAY_NAMES,
    CLIDetectionResult,
    CLIDetector,
    get_provider_role,
)

logger = logging.getLogger(__name__)

# Agent names mapped to providers
PROVIDER_AGENT_NAMES: dict[Provider, str] = {
    Provider.CLAUDE_CODE: "claude",
    Provider.CODEX: "codex",
    Provider.GEMINI_CLI: "gemini",
}


class SetupWizard:
    """Interactive setup wizard for Trinity initialization.

    Guides the user through:
    - Selecting language (en/ko)
    - Detecting installed AI CLI tools
    - Selecting which agents to enable
    - Customizing role prompts
    - Setting context budgets
    - Saving the configuration
    """

    def __init__(self, console: Console | None = None, detector: CLIDetector | None = None):
        self.console = console or Console()
        self.detector = detector or CLIDetector()
        self.detections: list[CLIDetectionResult] = []
        self.selected_agents: dict[str, AgentSpec] = {}
        self.lang: Lang = "en"

    @property
    def language(self) -> Lang:
        """The language selected by the user (for use by callers like cli.py)."""
        return self.lang

    def run(self, project_dir: Path | None = None) -> dict[str, AgentSpec] | None:
        """Run the interactive setup wizard.

        Args:
            project_dir: Project directory for the setup.

        Returns:
            Dict of agent_name → AgentSpec for selected agents, or None if cancelled.
        """
        self.console.print()

        # Step 0: Select language
        if not self._step_language():
            return None

        S = get_strings(self.lang)

        self.console.print(Panel.fit(
            f"[bold cyan]🧠 Trinity Setup Wizard[/bold cyan]\n\n"
            f"{S.wizard_body}",
            title=S.wizard_title,
            border_style="cyan",
        ))
        self.console.print()

        # Step 1: Detect CLI tools
        if not self._step_detect():
            return None

        # Step 2: Select agents
        if not self._step_select():
            return None

        # Step 3: Customize roles
        self._step_customize_roles()

        # Step 4: Review and confirm
        if not self._step_review():
            return None

        return self.selected_agents

    def _step_language(self) -> bool:
        """Step 0: Select interface language."""
        self.console.print("[bold]🌐 Language / 언어[/bold]")
        self.console.print()

        lang = Prompt.ask(
            "  [en] English   [ko] 한국어",
            choices=["en", "ko"],
            default="en",
        )
        self.lang = lang
        self.console.print()
        return True

    def _step_detect(self) -> bool:
        """Step 1: Detect installed CLI tools."""
        S = get_strings(self.lang)

        self.console.print(f"[bold]{S.step1_title}[/bold]")
        self.console.print()

        self.detections = self.detector.detect_all()

        # Display results
        table = Table(show_header=True, header_style="bold")
        table.add_column(S.col_tool, style="cyan", min_width=15)
        table.add_column(S.col_status, min_width=12)
        table.add_column(S.col_info, style="dim")

        for d in self.detections:
            if d.installed:
                status = f"[green]{S.detected}[/green]"
                info = f"{d.version}" if d.version else f"at {d.path}"
            else:
                status = f"[red]{S.not_found}[/red]"
                info = f"[dim]{d.error}[/dim]"

            table.add_row(d.display_name, status, info)

        self.console.print(table)
        self.console.print()

        # Show install hints for missing tools
        missing = [d for d in self.detections if not d.installed]
        if missing:
            self.console.print(f"[dim]{S.install_hint}[/dim]")
            for d in missing:
                self.console.print(f"[dim]   {d.display_name}: {d.install_url}[/dim]")
            self.console.print()

        installed = [d for d in self.detections if d.installed]
        if not installed:
            self.console.print(f"[red]{S.no_tools}[/red]")
            return False

        return True

    def _step_select(self) -> bool:
        """Step 2: Select which agents to enable."""
        S = get_strings(self.lang)
        installed = [d for d in self.detections if d.installed]

        self.console.print(f"[bold]{S.step2_title}[/bold]")
        self.console.print()

        roles = localized_roles_with_caveman(self.lang)

        for d in installed:
            agent_name = PROVIDER_AGENT_NAMES.get(d.provider, d.provider.value)
            display = PROVIDER_DISPLAY_NAMES.get(d.provider, d.provider.value)
            default = d.provider == Provider.CLAUDE_CODE

            msg = S.enable_prompt.format(display_name=display, agent_name=agent_name)
            if d.provider == Provider.CLAUDE_CODE:
                msg += f" [dim]{S.recommended}[/dim]"

            enabled = Confirm.ask(msg, default=default)

            if enabled:
                budget = PROVIDER_DEFAULT_BUDGETS.get(d.provider, 200_000)
                role = roles.get(agent_name, get_provider_role(d.provider, self.lang))
                extra_args = PROVIDER_DEFAULT_ARGS.get(d.provider, [])

                self.selected_agents[agent_name] = AgentSpec(
                    name=agent_name,
                    provider=d.provider,
                    cli_command=d.path.split("/")[-1].split("\\")[-1] if d.path else agent_name,
                    model=PROVIDER_DEFAULT_MODELS.get(d.provider, "default"),
                    role_prompt=role,
                    context_budget=budget,
                    enabled=True,
                    extra_args=extra_args,
                )

        if not self.selected_agents:
            self.console.print(f"[yellow]{S.no_agents}[/yellow]")
            return False

        names = ", ".join(self.selected_agents.keys())
        self.console.print()
        self.console.print(
            f"[green]{S.selected_agents.format(count=len(self.selected_agents), names=names)}[/green]"
        )
        self.console.print()
        return True

    def _step_customize_roles(self) -> None:
        """Step 3: Customize role prompts and context budgets."""
        S = get_strings(self.lang)

        self.console.print(f"[bold]{S.step3_title}[/bold]")
        self.console.print(f"[dim]{S.step3_hint}[/dim]")
        self.console.print()

        for name, spec in self.selected_agents.items():
            display = PROVIDER_DISPLAY_NAMES.get(spec.provider, name)
            self.console.print(f"[bold cyan]── {display} ({name}) ──[/bold cyan]")

            # Model and context budget
            selected_model = self._ask_model_choice(spec)
            if selected_model:
                spec.model = selected_model.model
                spec.context_budget = selected_model.context_budget
                self.console.print(
                    f"  {S.model_budget_applied.format(budget=spec.context_budget)}"
                )

            # Role prompt
            current_role = spec.role_prompt
            role_preview = current_role[:60] + "..." if len(current_role) > 60 else current_role
            self.console.print(f"  {S.current_role.format(role=role_preview)}")
            customize = Confirm.ask(
                f"  {S.customize_role.format(name=name)}", default=False,
            )
            if customize:
                new_role = Prompt.ask(
                    f"  {S.enter_role}",
                    default=current_role,
                )
                spec.role_prompt = new_role

            # Context budget override
            budget = spec.effective_context_budget
            self.console.print(f"  {S.context_budget.format(budget=budget)}")
            change_budget = Confirm.ask(
                f"  {S.change_budget}", default=False,
            )
            if change_budget:
                new_budget = IntPrompt.ask(
                    f"  {S.enter_budget}",
                    default=budget,
                )
                spec.context_budget = new_budget

            self.console.print()

    def _ask_model_choice(self, spec: AgentSpec) -> ModelContextSpec | None:
        """Prompt for a provider model and return its context metadata."""
        S = get_strings(self.lang)
        choices = list(provider_model_choices(spec.provider))
        if not choices:
            return None

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", justify="right")
        table.add_column(S.col_model, style="cyan")
        table.add_column(S.col_budget, justify="right")
        table.add_column(S.col_info, style="dim")
        for idx, choice in enumerate(choices, start=1):
            table.add_row(
                str(idx),
                f"{choice.display_name} ({choice.model})",
                f"{choice.context_budget:,}",
                choice.note,
            )
        table.add_row("c", S.custom_model, "-", S.custom_model_hint)
        self.console.print(table)

        current_model = spec.model or PROVIDER_DEFAULT_MODELS.get(spec.provider, "default")
        default_idx = "1"
        for idx, choice in enumerate(choices, start=1):
            if choice.model == current_model:
                default_idx = str(idx)
                break

        selected = Prompt.ask(
            f"  {S.select_model}",
            choices=[str(i) for i in range(1, len(choices) + 1)] + ["c"],
            default=default_idx,
        )

        if selected == "c":
            model_name = Prompt.ask(f"  {S.enter_model}", default=current_model)
            budget = IntPrompt.ask(
                f"  {S.enter_budget}",
                default=spec.effective_context_budget,
            )
            return ModelContextSpec(
                model=model_name,
                display_name=model_name,
                context_budget=budget,
                note="custom",
            )

        return choices[int(selected) - 1]

    def _step_review(self) -> bool:
        """Step 4: Review and confirm configuration."""
        S = get_strings(self.lang)

        self.console.print(f"[bold]{S.step4_title}[/bold]")
        self.console.print()

        table = Table(title="Agent Configuration", show_header=True, header_style="bold")
        table.add_column(S.col_agent, style="cyan")
        table.add_column(S.col_provider, style="green")
        table.add_column(S.col_model, style="magenta")
        table.add_column(S.col_role, max_width=40)
        table.add_column(S.col_budget, justify="right")

        for name, spec in self.selected_agents.items():
            role_preview = spec.role_prompt[:40] + "..." if len(spec.role_prompt) > 40 else spec.role_prompt
            budget = f"{spec.effective_context_budget:,}"
            table.add_row(name, spec.provider.value, spec.model, role_preview, budget)

        self.console.print(table)
        self.console.print()

        return Confirm.ask(S.save_prompt, default=True)

    def build_missing_agent_specs(self) -> dict[str, AgentSpec]:
        """Build AgentSpec entries for providers that are NOT installed.

        These are created as disabled agents so the user can enable them later
        after installing the CLI tool.

        Returns:
            Dict of agent_name → AgentSpec for missing providers (all disabled).
        """
        installed_providers = {
            d.provider for d in self.detections if d.installed
        }
        missing_specs: dict[str, AgentSpec] = {}
        roles = localized_roles_with_caveman(self.lang)

        for provider in Provider:
            if provider not in installed_providers:
                name = PROVIDER_AGENT_NAMES.get(provider, provider.value)
                budget = PROVIDER_DEFAULT_BUDGETS.get(provider, 200_000)
                role = roles.get(name, get_provider_role(provider, self.lang))
                extra_args = PROVIDER_DEFAULT_ARGS.get(provider, [])

                missing_specs[name] = AgentSpec(
                    name=name,
                    provider=provider,
                    cli_command=name,
                    model=PROVIDER_DEFAULT_MODELS.get(provider, "default"),
                    role_prompt=role,
                    context_budget=budget,
                    enabled=False,
                    extra_args=extra_args,
                )

        return missing_specs
