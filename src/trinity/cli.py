"""Trinity CLI — command-line interface."""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.logging import setup_logging
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
@click.option("-i", "--interactive", is_flag=True, help="Use tmux interactive mode (Phase 2)")
def ask(prompt: str, max_rounds: int | None, agent_names: str | None, interactive: bool):
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
    mode_str = "interactive (tmux)" if interactive else "print mode"
    console.print(Panel.fit(
        f"[bold]{prompt}[/bold]\n\n"
        f"Agents: {', '.join(active.keys())}\n"
        f"Max rounds: {config.max_deliberation_rounds}\n"
        f"Mode: {mode_str}",
        title="Trinity Deliberation",
    ))

    # Run orchestrator
    orchestrator = TrinityOrchestrator(config, interactive=interactive)

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


@main.command(name="status-watch")
@click.option("--interval", default=2.0, help="Refresh interval in seconds")
def status_watch(interval: float):
    """Live status dashboard (top-style). Updates every N seconds.

    Example: trinity status-watch --interval 3
    """
    config = load_config()
    orchestrator = TrinityOrchestrator(config)

    def build_table() -> Table:
        status_data = orchestrator.get_status()
        table = Table(title=f"Trinity Status  [dim]{time.strftime('%H:%M:%S')}[/dim]")
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
        return table

    try:
        with Live(build_table(), console=console, refresh_per_second=1) as live:
            while True:
                time.sleep(interval)
                live.update(build_table())
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


@main.command()
def attach():
    """Attach to the tmux session running Trinity agents."""
    config = load_config()

    if not config.session_name:
        console.print("[yellow]No tmux session configured.[/yellow]")
        return

    import subprocess
    result = subprocess.run(
        ["tmux", "attach-session", "-t", config.session_name],
    )
    if result.returncode != 0:
        console.print(
            f"[red]Failed to attach to tmux session '{config.session_name}'. "
            f"Is it running?[/red]"
        )


@main.command()
@click.option("--follow", is_flag=True, help="Follow log output in real-time")
@click.option("--lines", default=50, help="Number of lines to show")
def logs(follow: bool, lines: int):
    """View Trinity orchestrator logs.

    Example: trinity logs --follow
    """
    config = load_config()
    log_path = config.effective_state_dir / "logs" / "trinity.log"

    if not log_path.exists():
        console.print("[yellow]No log file found. Run 'trinity ask' first.[/yellow]")
        return

    if follow:
        import subprocess
        subprocess.run(["tail", "-f", "-n", str(lines), str(log_path)])
    else:
        content = log_path.read_text(encoding="utf-8")
        log_lines = content.splitlines()
        for line in log_lines[-lines:]:
            console.print(line)


@main.command("config")
@click.argument("key", required=False)
def config_show(key: str | None):
    """Show configuration values.

    Example: trinity config max_deliberation_rounds
    """
    cfg = load_config()

    if key:
        value = getattr(cfg, key, None)
        if value is None:
            console.print(f"[yellow]Unknown config key: {key}[/yellow]")
            return
        console.print(f"{key} = {value}")
    else:
        table = Table(title="Trinity Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        for attr in [
            "session_name", "max_deliberation_rounds", "consensus_threshold",
            "round_timeout_seconds", "context_rotate_threshold",
            "health_check_interval_seconds", "log_level",
        ]:
            table.add_row(attr, str(getattr(cfg, attr)))

        console.print(table)


@main.command()
@click.option("--keep-context", is_flag=True, help="Preserve shared.md when resetting")
def reset(keep_context: bool):
    """Reset the Trinity session state.

    Use --keep-context to preserve the shared context file.
    """
    config = load_config()
    state_dir = config.effective_state_dir

    if not state_dir.exists():
        console.print("[yellow]No .trinity/ directory found.[/yellow]")
        return

    # Optionally save shared.md
    shared_backup = None
    shared_path = state_dir / "shared.md"
    if keep_context and shared_path.exists():
        shared_backup = shared_path.read_text(encoding="utf-8")

    # Remove state directory
    shutil.rmtree(state_dir, ignore_errors=True)

    # Re-initialize
    init(force=True)

    # Restore shared.md if requested
    if shared_backup and keep_context:
        shared_path = state_dir / "shared.md"
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_text(shared_backup, encoding="utf-8")
        console.print("[green]✓ Shared context preserved.[/green]")

    console.print("[green]✓ Trinity session reset.[/green]")


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
