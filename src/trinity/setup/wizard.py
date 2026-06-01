"""Interactive setup wizard — guided `trinity init` with CLI detection.

Provides a Rich-based interactive setup flow:
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
from rich.text import Text

from trinity.models import AgentSpec, Provider
from trinity.setup.detector import (
    PROVIDER_DEFAULT_ARGS,
    PROVIDER_DEFAULT_BUDGETS,
    PROVIDER_DEFAULT_ROLES,
    PROVIDER_DISPLAY_NAMES,
    PROVIDER_INSTALL_URLS,
    CLIDetectionResult,
    CLIDetector,
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

    def run(self, project_dir: Path | None = None) -> dict[str, AgentSpec] | None:
        """Run the interactive setup wizard.

        Args:
            project_dir: Project directory for the setup.

        Returns:
            Dict of agent_name → AgentSpec for selected agents, or None if cancelled.
        """
        self.console.print()
        self.console.print(Panel.fit(
            "[bold cyan]🧠 Trinity Setup Wizard[/bold cyan]\n\n"
            "Let's configure your multi-agent AI environment.",
            title="Welcome",
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

    def _step_detect(self) -> bool:
        """Step 1: Detect installed CLI tools."""
        self.console.print("[bold]🔍 Step 1: Detecting AI CLI tools...[/bold]")
        self.console.print()

        self.detections = self.detector.detect_all()

        # Display results
        table = Table(show_header=True, header_style="bold")
        table.add_column("Tool", style="cyan", min_width=15)
        table.add_column("Status", min_width=12)
        table.add_column("Version / Info", style="dim")

        for d in self.detections:
            if d.installed:
                status = "[green]✅ Detected[/green]"
                info = f"{d.version}" if d.version else f"at {d.path}"
            else:
                status = "[red]❌ Not found[/red]"
                info = f"[dim]{d.error}[/dim]"

            table.add_row(d.display_name, status, info)

        self.console.print(table)
        self.console.print()

        # Show install hints for missing tools
        missing = [d for d in self.detections if not d.installed]
        if missing:
            self.console.print("[dim]💡 Install missing tools:[/dim]")
            for d in missing:
                self.console.print(f"[dim]   {d.display_name}: {d.install_url}[/dim]")
            self.console.print()

        installed = [d for d in self.detections if d.installed]
        if not installed:
            self.console.print(
                "[red]No AI CLI tools detected. Install at least one of: "
                "claude, codex, gemini[/red]"
            )
            return False

        return True

    def _step_select(self) -> bool:
        """Step 2: Select which agents to enable."""
        installed = [d for d in self.detections if d.installed]

        self.console.print("[bold]📋 Step 2: Select agents to enable[/bold]")
        self.console.print()

        for d in installed:
            agent_name = PROVIDER_AGENT_NAMES.get(d.provider, d.provider.value)
            default = "Y" if d.provider == Provider.CLAUDE_CODE else "y"
            msg = f"Enable [cyan]{d.display_name}[/cyan] ({agent_name})?"
            if d.provider == Provider.CLAUDE_CODE:
                msg += " [dim](recommended)[/dim]"

            enabled = Confirm.ask(msg, default=d.provider == Provider.CLAUDE_CODE)

            if enabled:
                budget = PROVIDER_DEFAULT_BUDGETS.get(d.provider, 200_000)
                role = PROVIDER_DEFAULT_ROLES.get(d.provider, "")
                extra_args = PROVIDER_DEFAULT_ARGS.get(d.provider, [])

                self.selected_agents[agent_name] = AgentSpec(
                    name=agent_name,
                    provider=d.provider,
                    cli_command=d.path.split("/")[-1].split("\\")[-1] if d.path else agent_name,
                    role_prompt=role,
                    context_budget=budget,
                    enabled=True,
                    extra_args=extra_args,
                )

        if not self.selected_agents:
            self.console.print("[yellow]No agents selected. Setup cancelled.[/yellow]")
            return False

        self.console.print()
        self.console.print(
            f"[green]Selected {len(self.selected_agents)} agent(s): "
            f"{', '.join(self.selected_agents.keys())}[/green]"
        )
        self.console.print()
        return True

    def _step_customize_roles(self) -> None:
        """Step 3: Customize role prompts and context budgets."""
        self.console.print("[bold]⚙️  Step 3: Customize agent roles[/bold]")
        self.console.print("[dim]Press Enter to accept defaults, or type custom values.[/dim]")
        self.console.print()

        for name, spec in self.selected_agents.items():
            display = PROVIDER_DISPLAY_NAMES.get(spec.provider, name)
            self.console.print(f"[bold cyan]── {display} ({name}) ──[/bold cyan]")

            # Role prompt
            current_role = spec.role_prompt
            self.console.print(f"  Current role: [dim]{current_role[:60]}...[/dim]")
            customize = Confirm.ask(f"  Customize role for {name}?", default=False)
            if customize:
                new_role = Prompt.ask(
                    "  Enter role prompt",
                    default=current_role,
                )
                spec.role_prompt = new_role

            # Context budget
            budget = spec.effective_context_budget
            self.console.print(f"  Context budget: {budget:,} tokens")
            change_budget = Confirm.ask(
                f"  Change context budget?", default=False,
            )
            if change_budget:
                new_budget = IntPrompt.ask(
                    "  Enter context budget (tokens)",
                    default=budget,
                )
                spec.context_budget = new_budget

            self.console.print()

    def _step_review(self) -> bool:
        """Step 4: Review and confirm configuration."""
        self.console.print("[bold]📝 Step 4: Review configuration[/bold]")
        self.console.print()

        table = Table(title="Agent Configuration", show_header=True, header_style="bold")
        table.add_column("Agent", style="cyan")
        table.add_column("Provider", style="green")
        table.add_column("Role", max_width=40)
        table.add_column("Context Budget", justify="right")

        for name, spec in self.selected_agents.items():
            role_preview = spec.role_prompt[:40] + "..." if len(spec.role_prompt) > 40 else spec.role_prompt
            budget = f"{spec.effective_context_budget:,}"
            table.add_row(name, spec.provider.value, role_preview, budget)

        self.console.print(table)
        self.console.print()

        return Confirm.ask("Save this configuration?", default=True)

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

        for provider in Provider:
            if provider not in installed_providers:
                name = PROVIDER_AGENT_NAMES.get(provider, provider.value)
                budget = PROVIDER_DEFAULT_BUDGETS.get(provider, 200_000)
                role = PROVIDER_DEFAULT_ROLES.get(provider, "")
                extra_args = PROVIDER_DEFAULT_ARGS.get(provider, [])

                missing_specs[name] = AgentSpec(
                    name=name,
                    provider=provider,
                    cli_command=name,
                    role_prompt=role,
                    context_budget=budget,
                    enabled=False,
                    extra_args=extra_args,
                )

        return missing_specs
