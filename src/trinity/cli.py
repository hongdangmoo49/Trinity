"""Trinity CLI — command-line interface."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.orchestrator import TrinityOrchestrator

console = Console()


def find_config_path() -> Path | None:
    """Find .trinity/trinity.config by walking up from cwd."""
    current = Path.cwd()
    for _ in range(10):
        candidate = current / ".trinity" / "trinity.config"
        if candidate.exists():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_config() -> TrinityConfig:
    """Load config from file or return default."""
    config_path = find_config_path()
    if config_path:
        console.print(f"[dim]Loaded config from {config_path}[/dim]")
        return TrinityConfig.load(config_path)
    return TrinityConfig.default_config()


@click.group()
@click.version_option(version=__version__, prog_name="trinity")
def main():
    """Trinity — Three minds, one context.

    Multi-agent AI orchestrator that unifies Claude Code, Codex, and Gemini
    through shared context, round-based deliberation, and task distribution.
    """
    pass


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing .trinity/ directory")
def init(force: bool):
    """Initialize .trinity/ in the current directory."""
    target = Path.cwd() / ".trinity"

    if target.exists() and not force:
        console.print(f"[yellow].trinity/ already exists. Use --force to overwrite.[/yellow]")
        return

    config = TrinityConfig.default_config(project_dir=Path.cwd())
    state = target

    # Create directory structure
    state.mkdir(exist_ok=True)
    (state / "agents" / "claude").mkdir(parents=True, exist_ok=True)
    (state / "agents" / "codex").mkdir(parents=True, exist_ok=True)
    (state / "agents" / "gemini").mkdir(parents=True, exist_ok=True)
    (state / "history").mkdir(exist_ok=True)
    (state / "logs").mkdir(exist_ok=True)
    (state / "workspace").mkdir(exist_ok=True)

    # Save config
    config.save(state / "trinity.config")

    # Create initial shared.md
    (state / "shared.md").write_text(
        "# Shared Context\n\n## Current Goal\n(No goal set yet)\n", encoding="utf-8"
    )

    # Create role files
    (state / "agents" / "claude" / "role.md").write_text(
        config.agents["claude"].role_prompt, encoding="utf-8"
    )
    (state / "agents" / "codex" / "role.md").write_text(
        config.agents["codex"].role_prompt, encoding="utf-8"
    )
    (state / "agents" / "gemini" / "role.md").write_text(
        config.agents["gemini"].role_prompt, encoding="utf-8"
    )

    # Add to .gitignore
    gitignore = Path.cwd() / ".gitignore"
    gitignore_lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if ".trinity/" not in gitignore_lines:
        gitignore_lines.append(".trinity/")
        gitignore.write_text("\n".join(gitignore_lines) + "\n", encoding="utf-8")

    console.print(Panel.fit(
        "[green]✓ Trinity initialized![/green]\n\n"
        f"  Directory: {state}\n"
        f"  Config:    {state / 'trinity.config'}\n"
        f"  Shared:    {state / 'shared.md'}\n\n"
        "[dim]Edit .trinity/trinity.config to customize agents and settings.[/dim]",
        title="Trinity Init",
    ))


@main.command()
@click.argument("prompt")
@click.option("--max-rounds", type=int, default=None, help="Override max deliberation rounds")
@click.option("--agents", "agent_names", default=None, help="Comma-separated agent names to use")
def ask(prompt: str, max_rounds: int | None, agent_names: str | None):
    """Run deliberation on a prompt.

    Example: trinity ask "What testing framework should we use?"
    """
    config = load_config()

    # Apply overrides
    if max_rounds is not None:
        config.max_deliberation_rounds = max_rounds

    if agent_names:
        selected = set(agent_names.split(","))
        for name in list(config.agents.keys()):
            if name not in selected:
                config.agents[name].enabled = False

    # Show header
    active = config.active_agents
    console.print(Panel.fit(
        f"[bold]{prompt}[/bold]\n\n"
        f"Agents: {', '.join(active.keys())}\n"
        f"Max rounds: {config.max_deliberation_rounds}",
        title="Trinity Deliberation",
    ))

    # Run orchestrator
    orchestrator = TrinityOrchestrator(config)

    try:
        result = asyncio.run(orchestrator.ask(prompt))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger = __import__("logging").getLogger("trinity")
        logger.exception("Deliberation failed")
        sys.exit(1)

    # Display results
    _display_result(result)


@main.command()
def status():
    """Show current Trinity status."""
    config = load_config()

    orchestrator = TrinityOrchestrator(config)
    status_data = orchestrator.get_status()

    table = Table(title="Trinity Status")
    table.add_column("Agent", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Status")
    table.add_column("Context")

    for name, info in status_data["agents"].items():
        table.add_row(
            name,
            info["provider"],
            "✓ active" if info["alive"] else "✗ offline",
            info["context"],
        )

    console.print(table)
    console.print(f"\n[dim]Shared context: {status_data['shared_context_path']}[/dim]")


@main.command()
@click.option("--section", default=None, help="Show only a specific section")
def context(section: str | None):
    """Display the shared context (shared.md)."""
    config = load_config()

    from trinity.context.shared import SharedContextEngine

    engine = SharedContextEngine(path=config.shared_context_path)

    if section:
        content = engine.read_section(section)
        if content is None:
            console.print(f"[yellow]Section '{section}' not found.[/yellow]")
            return
        console.print(Panel(content, title=section))
    else:
        content = engine.read()
        if not content.strip():
            console.print("[yellow]Shared context is empty.[/yellow]")
            return
        console.print(content)


def _display_result(result):
    """Pretty-print deliberation results."""
    # Consensus
    if result.has_consensus:
        console.print(Panel.fit(
            f"[green]{result.consensus.summary}[/green]",
            title=f"✓ Consensus (Round {result.rounds_completed})",
        ))
    else:
        console.print(Panel.fit(
            "[yellow]No consensus reached.[/yellow]",
            title=f"Deliberation Result ({result.rounds_completed} rounds)",
        ))

    # Tasks
    if result.tasks:
        table = Table(title="Task Distribution")
        table.add_column("Agent", style="cyan")
        table.add_column("Task", style="white")
        table.add_column("Priority", justify="right")

        for task in sorted(result.tasks, key=lambda t: -t.priority):
            table.add_row(
                task.agent_name,
                task.task_description[:80] + "..." if len(task.task_description) > 80 else task.task_description,
                str(task.priority),
            )

        console.print(table)

    # Stats
    console.print(
        f"\n[dim]Duration: {result.duration_seconds:.1f}s | "
        f"Tokens: {result.total_tokens_used:,} | "
        f"Rounds: {result.rounds_completed}[/dim]"
    )
