"""Trinity CLI — command-line interface.

Supports:
  trinity             → Interactive TUI mode (Phase 6)
  trinity init        → Interactive setup wizard with CLI detection (Phase 6)
  trinity ask "..."   → One-shot deliberation
  trinity status      → Show agent status
  trinity ...         → Various management commands
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from trinity import __version__
from trinity.config import TrinityConfig
from trinity.context.analytics import TokenAnalytics, analytics_history_path
from trinity.orchestrator import TrinityOrchestrator
from trinity.platform import (
    detect_platform_info,
    detect_terminal_capabilities,
    has_command,
    legacy_tmux_hint,
)
from trinity.providers.bootstrap import (
    ProviderBootstrapError,
    ProviderBootstrapRunResult,
    ProviderBootstrapper,
    attach_to_bootstrap_session,
    render_provider_command,
)
from trinity.setup.detector import CLIDetector
from trinity.textual_app.runtime import resolve_tui_runtime
from trinity.updater import (
    StartupUpdate,
    apply_startup_update,
    check_for_startup_update,
    startup_update_check_disabled,
)


def _configure_stdio_encoding_errors(*streams) -> None:
    """Avoid UnicodeEncodeError on legacy Windows code pages.

    Some Windows CI shells expose stdout/stderr as cp1252. Rich can then fail
    when a command prints symbols such as check marks. Replacing unsupported
    characters is better than crashing during non-interactive smoke commands.
    """
    target_streams = streams or (sys.stdout, sys.stderr)
    for stream in target_streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(errors="replace")
        except (OSError, TypeError, ValueError):
            continue


_configure_stdio_encoding_errors()

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


def load_config(silent: bool = False) -> TrinityConfig:
    """Load config from file or return default.

    Args:
        silent: If True, suppress the "Loaded config from..." message.
    """
    config_path = find_config_path()
    if config_path:
        if not silent:
            console.print(f"[dim]Loaded config from {config_path}[/dim]")
        return TrinityConfig.load(config_path)
    return TrinityConfig.default_config()


def _stdio_is_interactive() -> bool:
    """Return True when startup prompts can safely read from the terminal."""
    stdin_is_tty = getattr(sys.stdin, "isatty", lambda: False)
    stdout_is_tty = getattr(sys.stdout, "isatty", lambda: False)
    return bool(stdin_is_tty() and stdout_is_tty())


def _startup_update_lang() -> str:
    """Resolve the configured language for pre-TUI startup prompts."""
    try:
        config_path = find_config_path()
        if config_path:
            return TrinityConfig.load(config_path).lang
    except Exception:
        return "en"
    return "en"


def _startup_update_strings(lang: str) -> dict[str, str]:
    if lang == "ko":
        return {
            "title": "Trinity 업데이트",
            "available": "Trinity 업데이트가 있습니다.",
            "current": "현재 버전",
            "latest": "새 버전",
            "prompt": "지금 업데이트할까요?",
            "declined": "업데이트를 건너뛰고 현재 버전으로 시작합니다.",
            "done": "업데이트가 완료되었습니다.",
            "restart": "새 버전을 적용하려면 trinity를 다시 실행하세요.",
            "failed": "업데이트에 실패했습니다. 현재 버전으로 계속 시작합니다.",
            "details": "상세 내용",
        }
    return {
        "title": "Trinity Update",
        "available": "A Trinity update is available.",
        "current": "Current",
        "latest": "Latest",
        "prompt": "Update now?",
        "declined": "Skipping update and starting the current version.",
        "done": "Update completed.",
        "restart": "Run trinity again to use the updated version.",
        "failed": "Update failed. Starting the current version.",
        "details": "Details",
    }


def _render_startup_update(update: StartupUpdate, lang: str) -> Panel:
    strings = _startup_update_strings(lang)
    body = "\n".join(
        [
            f"[bold]{strings['available']}[/bold]",
            "",
            f"{strings['current']}: [cyan]{update.current_version}[/cyan]",
            f"{strings['latest']}: [green]{update.latest_version}[/green]",
        ]
    )
    return Panel.fit(body, title=strings["title"], border_style="yellow")


def _maybe_run_startup_update(*, skip: bool = False) -> bool:
    """Prompt for a startup update and return True when the CLI should exit."""
    if skip or startup_update_check_disabled() or not _stdio_is_interactive():
        return False

    lang = _startup_update_lang()
    update = check_for_startup_update(__version__)
    if update is None:
        return False

    strings = _startup_update_strings(lang)
    console.print(_render_startup_update(update, lang))
    if not Confirm.ask(strings["prompt"], default=False, console=console):
        console.print(f"[dim]{strings['declined']}[/dim]")
        return False

    result = apply_startup_update(update)
    if result.succeeded:
        console.print(f"[green]{strings['done']}[/green]")
        if result.output:
            console.print(f"[dim]{result.output}[/dim]")
        console.print(f"[yellow]{strings['restart']}[/yellow]")
        return True

    console.print(f"[red]{strings['failed']}[/red]")
    if result.output:
        console.print(
            Panel.fit(result.output, title=strings["details"], border_style="red")
        )
    return False


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="trinity")
@click.option("--interactive/--no-interactive", default=None, help="Force interactive TUI mode")
@click.option("--plain", is_flag=True, help="Use the legacy Rich/prompt_toolkit TUI")
@click.option(
    "--no-update-check",
    is_flag=True,
    help="Skip the startup update check before launching the interactive TUI",
)
@click.pass_context
def main(
    ctx: click.Context,
    interactive: bool | None,
    plain: bool,
    no_update_check: bool,
):
    """Trinity — Three minds, one context.

    Multi-agent AI orchestrator that unifies Claude Code, Codex, and Antigravity
    through shared context, round-based deliberation, and task distribution.

    Run without arguments to enter interactive TUI mode.
    """
    ctx.ensure_object(dict)
    ctx.obj["force_interactive"] = interactive

    if ctx.invoked_subcommand is None:
        if _maybe_run_startup_update(skip=no_update_check):
            ctx.exit(0)
        # No subcommand → enter interactive TUI mode
        _run_interactive_tui(plain=plain)


def _run_interactive_tui(*, plain: bool = False) -> None:
    """Launch the selected interactive TUI session."""
    config = load_config(silent=True)

    # If no .trinity/ directory exists, suggest running init first
    state_dir = config.effective_state_dir
    if not (state_dir / "trinity.config").exists():
        console.print(Panel.fit(
            "[yellow]No Trinity project found in current directory.[/yellow]\n\n"
            "Run [cyan]trinity init[/cyan] first to set up a project.",
            title="Trinity",
        ))
        sys.exit(1)

    try:
        runtime = resolve_tui_runtime("plain" if plain else None)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if runtime.use_textual:
        try:
            _run_textual_interactive_tui(config)
            return
        except ImportError:
            console.print(
                "[yellow]Textual is unavailable; falling back to plain TUI.[/yellow]"
            )

    _run_plain_interactive_tui(config)


def _run_textual_interactive_tui(config: TrinityConfig) -> None:
    """Launch the Textual workbench."""
    from trinity.textual_app.app import run_textual_app

    run_textual_app(config)


def _run_plain_interactive_tui(config: TrinityConfig) -> None:
    """Launch the legacy Rich/prompt_toolkit interactive session."""
    from trinity.tui.session import InteractiveSession

    session = InteractiveSession(config, console)
    try:
        session.run()
    except KeyboardInterrupt:
        console.print("\n[bold cyan]👋 Goodbye from Trinity![/bold cyan]")


# ─── trinity init ────────────────────────────────────────────────────────

@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing .trinity/ directory")
@click.option("--non-interactive", is_flag=True, help="Skip interactive setup, use defaults")
def init(force: bool, non_interactive: bool):
    """Initialize .trinity/ in the current directory.

    Runs an interactive setup wizard that:
    1. Detects installed AI CLI tools (claude, codex, agy)
    2. Lets you choose which agents to enable
    3. Customizes role prompts and context budgets
    4. Saves the configuration

    Use --non-interactive to skip the wizard and use defaults.
    """
    target = Path.cwd() / ".trinity"

    if target.exists() and not force:
        console.print("[yellow].trinity/ already exists. Use --force to overwrite.[/yellow]")
        return

    if non_interactive:
        _init_default(target, force)
    else:
        _init_interactive(target, force)


def _init_interactive(target: Path, force: bool) -> None:
    """Run interactive setup wizard for init."""
    from trinity.i18n import get_strings
    from trinity.setup.wizard import SetupWizard

    wizard = SetupWizard(console=console)

    # Run the wizard
    selected_agents = wizard.run(project_dir=Path.cwd())
    if selected_agents is None:
        S = get_strings(wizard.language)
        console.print(f"[yellow]{S.cancelled}[/yellow]")
        return

    S = get_strings(wizard.language)

    # Build full agent dict including disabled agents for missing CLIs
    all_agents = dict(selected_agents)
    missing = wizard.build_missing_agent_specs()
    all_agents.update(missing)

    # Create config from selections
    config = TrinityConfig(
        project_dir=Path.cwd(),
        agents=all_agents,
    )

    # Create directory structure
    _create_directory_structure(target, list(all_agents.keys()))

    # Save config
    config.save(target / "trinity.config")

    # Create initial shared.md
    (target / "shared.md").write_text(
        "# Shared Context\n\n## Current Goal\n(No goal set yet)\n", encoding="utf-8"
    )

    # Create role files
    for name, spec in all_agents.items():
        role_path = target / "agents" / name / "role.md"
        role_path.parent.mkdir(parents=True, exist_ok=True)
        role_path.write_text(spec.role_prompt, encoding="utf-8")

    # Add to .gitignore
    _update_gitignore()

    # Show summary
    active_names = [n for n, s in all_agents.items() if s.enabled]
    inactive_names = [n for n, s in all_agents.items() if not s.enabled]

    summary_lines = [
        f"[green bold]{S.summary_initialized}[/green bold]\n",
        f"  {S.summary_directory.format(path=target)}",
        f"  {S.summary_config.format(path=target / 'trinity.config')}",
        f"  {S.summary_shared.format(path=target / 'shared.md')}\n",
        f"  {S.summary_agents.format(agents=', '.join(active_names))}",
    ]
    if inactive_names:
        summary_lines.append(
            f"  {S.summary_skipped.format(agents=', '.join(inactive_names))}"
        )

    summary_lines.append(
        f"\n{S.summary_start_hint}\n"
        f"   [cyan]{S.summary_start_tui}[/cyan]\n"
        f"   [cyan]{S.summary_start_ask}[/cyan]"
    )

    console.print(Panel.fit(
        "\n".join(summary_lines),
        title="Trinity Init",
        border_style="green",
    ))


def _init_default(target: Path, force: bool) -> None:
    """Non-interactive init with defaults (original behavior)."""
    config = TrinityConfig.default_config(project_dir=Path.cwd())
    state = target

    # Create directory structure
    _create_directory_structure(state, list(config.agents.keys()))

    # Save config
    config.save(state / "trinity.config")

    # Create initial shared.md
    (state / "shared.md").write_text(
        "# Shared Context\n\n## Current Goal\n(No goal set yet)\n", encoding="utf-8"
    )

    # Create role files
    for name, spec in config.agents.items():
        role_path = state / "agents" / name / "role.md"
        role_path.parent.mkdir(parents=True, exist_ok=True)
        role_path.write_text(spec.role_prompt, encoding="utf-8")

    # Add to .gitignore
    _update_gitignore()

    console.print(Panel.fit(
        "[green]✓ Trinity initialized![/green]\n\n"
        f"  Directory: {state}\n"
        f"  Config:    {state / 'trinity.config'}\n"
        f"  Shared:    {state / 'shared.md'}\n\n"
        "[dim]Edit .trinity/trinity.config to customize agents and settings.[/dim]",
        title="Trinity Init",
    ))


def _create_directory_structure(
    state: Path, agent_names: list[str] | None = None
) -> None:
    """Create the .trinity/ directory structure."""
    state.mkdir(exist_ok=True)
    names = agent_names or ["claude", "codex", "antigravity"]
    for name in names:
        (state / "agents" / name).mkdir(parents=True, exist_ok=True)
    (state / "history").mkdir(exist_ok=True)
    (state / "logs").mkdir(exist_ok=True)
    (state / "workspace").mkdir(exist_ok=True)


def _update_gitignore() -> None:
    """Add .trinity/ to .gitignore if not already present."""
    gitignore = Path.cwd() / ".gitignore"
    gitignore_lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    if ".trinity/" not in gitignore_lines:
        gitignore_lines.append(".trinity/")
        gitignore.write_text("\n".join(gitignore_lines) + "\n", encoding="utf-8")


# ─── trinity bootstrap ───────────────────────────────────────────────────

@main.command()
@click.option(
    "--agents",
    "agent_names",
    default=None,
    help="Comma-separated agent names to bootstrap. Explicit names may be disabled.",
)
@click.option(
    "--all",
    "include_disabled",
    is_flag=True,
    help="Bootstrap all configured agents, including disabled agents.",
)
@click.option("--check-only", is_flag=True, help="Only check selected provider CLIs")
@click.option("--skip-ready", is_flag=True, help="Skip provider CLI availability checks")
@click.option("--continue-on-error", is_flag=True, help="Continue after a provider exits non-zero")
@click.option("--legacy-tmux", is_flag=True, help="Use legacy tmux bootstrap session")
@click.option("--session-name", default=None, help="Override legacy bootstrap tmux session name")
@click.option("--force", is_flag=True, help="Recreate an existing legacy bootstrap session")
@click.option("--no-attach", is_flag=True, help="Start the legacy tmux session without attaching")
def bootstrap(
    agent_names: str | None,
    include_disabled: bool,
    check_only: bool,
    skip_ready: bool,
    continue_on_error: bool,
    legacy_tmux: bool,
    session_name: str | None,
    force: bool,
    no_attach: bool,
):
    """Launch provider CLIs for isolated first-run setup and authentication.

    This command prepares isolated provider homes under
    .trinity/agents/<agent>/provider-state. Normal Trinity runs reuse the
    user's existing CLI auth by default unless provider_state_mode is set to
    "isolated".
    """
    config_path = find_config_path()
    if config_path is None:
        console.print(
            "[yellow]No Trinity project found. Run `trinity init` first.[/yellow]"
        )
        sys.exit(1)
    config = TrinityConfig.load(config_path)
    selected_names = _parse_agent_names(agent_names)
    bootstrapper = ProviderBootstrapper()

    if legacy_tmux:
        _bootstrap_legacy_tmux(
            bootstrapper,
            config,
            selected_names=selected_names,
            include_disabled=include_disabled,
            session_name=session_name,
            force=force,
            no_attach=no_attach,
        )
        return

    if session_name or force or no_attach:
        console.print(
            "[yellow]--session-name, --force, and --no-attach are legacy tmux "
            "bootstrap options. Pass --legacy-tmux to use them.[/yellow]"
        )

    try:
        result = bootstrapper.run_sequential(
            config,
            agent_names=selected_names,
            include_disabled=include_disabled,
            check_only=check_only,
            skip_ready=skip_ready,
            continue_on_error=continue_on_error,
        )
    except ProviderBootstrapError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[red]Failed to start provider bootstrap: {exc}[/red]")
        _logger = logging.getLogger("trinity")
        _logger.exception("Provider bootstrap failed")
        sys.exit(1)

    _display_bootstrap_run_result(result)


def _bootstrap_legacy_tmux(
    bootstrapper: ProviderBootstrapper,
    config: TrinityConfig,
    *,
    selected_names: list[str] | None,
    include_disabled: bool,
    session_name: str | None,
    force: bool,
    no_attach: bool,
) -> None:
    """Run the legacy tmux bootstrap path."""
    try:
        result = bootstrapper.launch_legacy_tmux_session(
            config,
            agent_names=selected_names,
            include_disabled=include_disabled,
            session_name=session_name,
            force=force,
        )
    except ProviderBootstrapError as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[red]Failed to start provider bootstrap: {exc}[/red]")
        _logger = logging.getLogger("trinity")
        _logger.exception("Provider bootstrap failed")
        sys.exit(1)

    table = Table(title="Provider Bootstrap")
    table.add_column("Agent", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Isolated HOME")
    table.add_column("CWD")
    for target in result.targets:
        table.add_row(
            target.agent_name,
            target.spec.provider.value,
            str(target.managed_home or ""),
            str(target.cwd),
        )
    console.print(table)
    console.print(
        f"\n[green]Started tmux session '{result.session_name}'.[/green]\n"
        "Complete each provider's auth, theme, and workspace trust prompts in "
        "that session if this project uses provider_state_mode=\"isolated\"."
    )

    if no_attach:
        console.print(
            f"[dim]Attach later with: tmux attach-session -t {result.session_name}[/dim]"
        )
        return

    console.print("[dim]Attaching to bootstrap session...[/dim]")
    exit_code = attach_to_bootstrap_session(result.session_name)
    if exit_code != 0:
        console.print(
            f"[red]Failed to attach to tmux session '{result.session_name}'.[/red]"
        )


def _display_bootstrap_run_result(result: ProviderBootstrapRunResult) -> None:
    """Display sequential bootstrap status."""
    table = Table(title="Provider Bootstrap")
    table.add_column("Agent", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Command")
    table.add_column("Installed")
    table.add_column("State")
    table.add_column("CWD")

    for target in result.targets:
        check = result.checks[target.agent_name]
        exit_code = result.exit_codes.get(target.agent_name)
        if result.check_only:
            state = "check only"
        elif exit_code is None:
            state = "not run"
        elif exit_code == 0:
            state = "completed"
        else:
            state = f"exit {exit_code}"
        table.add_row(
            target.agent_name,
            target.spec.provider.value,
            render_provider_command(target.spec),
            "yes" if check.installed else "no",
            state,
            str(target.cwd),
        )

    console.print(table)
    if result.check_only:
        console.print("[dim]Check only; no provider CLI was launched.[/dim]")
        return

    failed = result.failed_agents
    if failed:
        console.print(
            "[yellow]Provider bootstrap finished with failures: "
            f"{', '.join(failed)}[/yellow]"
        )
    else:
        console.print(
            "[green]Provider bootstrap finished in the current terminal.[/green]"
        )


def _parse_agent_names(agent_names: str | None) -> list[str] | None:
    """Parse a comma-separated agent list from CLI input."""
    if not agent_names:
        return None
    names = [part.strip() for part in agent_names.split(",") if part.strip()]
    return names or None


def _uses_legacy_tmux_transport(config: TrinityConfig, force_tmux: bool = False) -> bool:
    """Whether this invocation should use the legacy tmux agent transport."""
    return force_tmux or config.transport_mode == "tmux"


def _transport_mode_label(use_tmux: bool) -> str:
    """Human-readable transport label for CLI output."""
    return "legacy tmux" if use_tmux else "one-shot"


def _print_legacy_tmux_notice() -> None:
    """Show a short notice when the legacy transport is explicitly selected."""
    console.print(
        "[yellow]Using legacy tmux agent transport. "
        "One-shot remains the default transport.[/yellow]"
    )


# ─── trinity ask ─────────────────────────────────────────────────────────

@main.command()
@click.argument("prompt")
@click.option("--max-rounds", type=int, default=None, help="Override max deliberation rounds")
@click.option("--agents", "agent_names", default=None, help="Comma-separated agent names to use")
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    help="Use legacy tmux agent transport for this request",
)
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
    use_tmux = _uses_legacy_tmux_transport(config, force_tmux=interactive)
    mode_str = _transport_mode_label(use_tmux)
    if use_tmux:
        _print_legacy_tmux_notice()
    console.print(Panel.fit(
        f"[bold]{prompt}[/bold]\n\n"
        f"Agents: {', '.join(active.keys())}\n"
        f"Max rounds: {config.max_deliberation_rounds}\n"
        f"Mode: {mode_str}",
        title="Trinity Deliberation",
    ))

    # Run orchestrator
    orchestrator = TrinityOrchestrator(config, interactive=use_tmux)

    try:
        result = asyncio.run(orchestrator.ask(prompt))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        _logger = logging.getLogger("trinity")
        _logger.exception("Deliberation failed")
        sys.exit(1)

    # Display results
    _display_result(result)


# ─── trinity status ──────────────────────────────────────────────────────

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
    console.print(f"[dim]Transport: {status_data['transport_mode']}[/dim]")
    synthesis = status_data.get("synthesis", {})
    if synthesis:
        source = synthesis.get("source", "heuristic")
        provider = synthesis.get("provider") or synthesis.get("provider_agent") or ""
        model = synthesis.get("model", "")
        fallback = synthesis.get("fallback_used", False)
        suffix = f" {provider}/" if provider else " "
        console.print(
            f"[dim]Synthesis:{suffix}{model or source} "
            f"(source={source}, fallback={fallback})[/dim]"
        )


# ─── trinity doctor ──────────────────────────────────────────────────────

@main.command()
def doctor():
    """Show cross-platform runtime diagnostics."""
    config_path = find_config_path()
    config = (
        TrinityConfig.load(config_path)
        if config_path
        else TrinityConfig.default_config()
    )
    info = detect_platform_info()
    caps = detect_terminal_capabilities(info)
    detector = CLIDetector()

    table = Table(title="Trinity Doctor")
    table.add_column("Area", style="cyan")
    table.add_column("Value")
    table.add_column("Status")

    table.add_row("Trinity", __version__, "ok")
    table.add_row("Python", sys.version.split()[0], "ok")
    table.add_row("OS", info.os_name, "ok")
    table.add_row(
        "Shell",
        info.shell_name,
        "ok" if info.shell_name != "unknown" else "unknown",
    )
    table.add_row(
        "Terminal",
        info.terminal_name,
        "ok" if info.terminal_name != "unknown" else "unknown",
    )
    table.add_row("TTY", str(info.is_tty), "ok" if info.is_tty else "plain")
    table.add_row("CI", str(info.is_ci), "plain" if info.is_ci else "ok")
    table.add_row("Render Mode", caps.render_mode, "ok")
    table.add_row(
        "Live Render",
        str(caps.supports_live_render),
        "ok" if caps.supports_live_render else "plain",
    )
    table.add_row(
        "Config",
        str(config_path or "not found"),
        "ok" if config_path else "default",
    )
    table.add_row("State Dir", str(config.effective_state_dir), "ok")
    table.add_row(
        "Transport",
        config.transport_mode,
        "ok" if config.transport_mode == "one-shot" else "legacy",
    )
    table.add_row("Provider State", config.provider_state_mode, "ok")
    table.add_row("tmux", "available" if has_command("tmux") else "not found", "legacy")

    for name, spec in config.agents.items():
        result = detector.detect(spec.provider)
        status = "ok" if result.installed else "missing"
        value = result.path or result.error or spec.cli_command
        table.add_row(f"Provider {name}", value, status)

    console.print(table)
    console.print(f"[dim]{legacy_tmux_hint(info)}[/dim]")


# ─── trinity status-watch ────────────────────────────────────────────────

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


# ─── trinity attach ──────────────────────────────────────────────────────

@main.command()
def attach():
    """Attach to the legacy tmux transport session running Trinity agents."""
    config = load_config()

    if config.transport_mode != "tmux":
        console.print(
            "[yellow]Current transport is one-shot; no Trinity tmux transport "
            "session is expected. Set transport_mode = \"tmux\" to use this "
            "legacy command.[/yellow]"
        )
        return

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


# ─── trinity logs ────────────────────────────────────────────────────────

@main.command()
@click.option("--follow", is_flag=True, help="Follow log output in real-time")
@click.option("--lines", default=50, help="Number of lines to show")
def logs(follow: bool, lines: int):
    """View Trinity orchestrator logs.

    Example: trinity logs --follow
    """
    config = load_config()
    log_path = config.effective_state_dir / "logs" / "trinity.log"

    if follow:
        from trinity.platform.log_tail import follow_log

        try:
            for event in follow_log(log_path, lines=lines):
                if event.kind == "line":
                    console.print(event.message)
                else:
                    console.print(event.message, style="yellow", markup=False)
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
    else:
        if not log_path.exists():
            console.print("[yellow]No log file found. Run 'trinity ask' first.[/yellow]")
            return

        content = log_path.read_text(encoding="utf-8")
        log_lines = content.splitlines()
        for line in log_lines[-lines:]:
            console.print(line)


# ─── trinity config ──────────────────────────────────────────────────────

_SAFE_CONFIG_KEYS = frozenset({
    "session_name", "lang", "max_deliberation_rounds",
    "consensus_threshold", "round_timeout_seconds",
    "context_rotate_threshold", "health_check_interval_seconds",
    "log_level", "log_file", "caveman_mode", "caveman_intensity",
    "provider_state_mode", "transport_mode",
    "synthesis_mode", "synthesis_agent", "synthesis_model",
    "synthesis_timeout_seconds", "synthesis_max_input_chars",
})


@main.command("config")
@click.argument("key", required=False)
def config_show(key: str | None):
    """Show configuration values.

    Example: trinity config max_deliberation_rounds
    """
    cfg = load_config()

    if key:
        if key not in _SAFE_CONFIG_KEYS:
            console.print(f"[yellow]Unknown config key: {key}[/yellow]")
            return
        console.print(f"{key} = {getattr(cfg, key)}")
    else:
        table = Table(title="Trinity Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        for attr in sorted(_SAFE_CONFIG_KEYS):
            table.add_row(attr, str(getattr(cfg, attr, "N/A")))

        console.print(table)


# ─── trinity reset ───────────────────────────────────────────────────────

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

    # Re-initialize with non-interactive defaults
    _init_default(state_dir, force=True)

    # Restore shared.md if requested
    if shared_backup and keep_context:
        shared_path = state_dir / "shared.md"
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_text(shared_backup, encoding="utf-8")
        console.print("[green]✓ Shared context preserved.[/green]")

    console.print("[green]✓ Trinity session reset.[/green]")


# ─── trinity analytics ────────────────────────────────────────────────────

@main.command()
def analytics():
    """Show persisted token usage analytics."""
    config = load_config()

    token_analytics = TokenAnalytics.from_file(
        analytics_history_path(config.effective_state_dir)
    )
    summary = token_analytics.summary() if token_analytics.history else None
    if not summary:
        console.print("[yellow]No analytics data available. Run a deliberation first.[/yellow]")
        return

    console.print(Panel.fit(
        f"Rounds: {summary['rounds_recorded']}\n"
        f"Total tokens: {summary['total_tokens']:,}\n"
        f"Avg tokens/round: {summary['avg_tokens_per_round']:,.0f}\n"
        f"Trend: {summary['trend']}",
        title="Token Analytics",
    ))

    if summary.get("agents"):
        table = Table(title="Agent Usage")
        table.add_column("Agent", style="cyan")
        table.add_column("Total Tokens", justify="right")
        table.add_column("Burn Rate (tok/round)", justify="right")

        for name, data in summary["agents"].items():
            table.add_row(
                name,
                f"{data['total']:,}",
                f"{data['burn_rate']:,.0f}",
            )
        console.print(table)


# ─── trinity context ─────────────────────────────────────────────────────

@main.command()
@click.option("--section", default=None, help="Show only a specific section")
def context(section: str | None):
    """Display the shared context (shared.md)."""
    config = load_config()

    from trinity.context.shared import SharedContextEngine

    engine = SharedContextEngine(
        path=config.shared_context_path,
        max_read_bytes=config.shared_max_bytes,
        section_entry_max_chars=config.shared_section_entry_max_chars,
        memory_index_enabled=config.memory_index_enabled,
    )

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


# ─── Helper ──────────────────────────────────────────────────────────────

def _display_result(result):
    """Pretty-print deliberation results."""
    # Consensus
    if result.has_consensus:
        console.print(Panel.fit(
            f"[green]{result.consensus.summary}[/green]",
            title=f"✓ Consensus (Round {result.rounds_completed})",
        ))
    else:
        summary = (
            result.consensus.summary
            if result.consensus and result.consensus.summary
            else "No consensus reached."
        )
        console.print(Panel.fit(
            f"[yellow]{summary}[/yellow]",
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
