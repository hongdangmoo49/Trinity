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
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
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
from trinity.project_intake import (
    GitWorkspaceAnalysis,
    ProjectIntake,
    ProjectIntakePaths,
    analyze_git_workspace,
    build_project_intake,
    detect_package_managers,
    detect_scope_candidates,
    existing_project_intake_drift_fields,
    load_project_intake,
    missing_new_project_brief_field_keys,
    missing_new_project_brief_fields,
    suggest_test_commands,
    write_project_intake,
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
from trinity.textual_app.workspace_labels import (
    PROJECT_INTAKE_STALE_AFTER_DAYS,
    format_project_intake_label,
    format_project_generation_preview_label,
    format_project_read_first_checklist_label,
    format_project_validation_plan_label,
    project_analyze_action_variant,
    project_brief_action_variant,
    project_create_action_variant,
)
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


@dataclass(frozen=True)
class InitNewProjectRequest:
    """New-project workspace request collected during `trinity init`."""

    name: str
    parent: Path
    git_init: bool
    product_goal: str = ""
    project_type: str = ""
    starter_profile: str = ""
    target_users: str = ""
    success_criteria: str = ""
    stack_preferences: tuple[str, ...] = ()
    first_milestone: str = ""
    constraints: tuple[str, ...] = ()
    notes: str = ""


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
@click.option(
    "--mode",
    type=click.Choice(["existing", "new"]),
    default=None,
    help="Record a new/existing project intake during init.",
)
@click.option(
    "--project-name",
    default="",
    help="Create a new project workspace during init.",
)
@click.option(
    "--parent",
    "project_parent",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Parent directory for --project-name.",
)
@click.option(
    "--project-git/--no-project-git",
    "project_git_init",
    default=False,
    show_default=True,
    help="Initialize Git in the created project workspace.",
)
@click.option(
    "--goal",
    "product_goal",
    default="",
    help="Product goal for the new project brief.",
)
@click.option(
    "--project-type",
    default="",
    help="Project type or product category for the new project brief.",
)
@click.option(
    "--starter-profile",
    "--starter",
    default="",
    help="Initial implementation/repository shape for the new project.",
)
@click.option(
    "--target-users",
    default="",
    help="Target users or audience for the new project brief.",
)
@click.option(
    "--success-criteria",
    default="",
    help="Success criteria for the new project brief.",
)
@click.option(
    "--stack",
    "stack_preferences",
    multiple=True,
    help="Preferred stack item for the new project brief. Repeat or comma-separate.",
)
@click.option(
    "--milestone",
    "first_milestone",
    default="",
    help="First milestone for the new project brief.",
)
@click.option(
    "--constraint",
    "constraints",
    multiple=True,
    help="New project constraint. Repeat or comma-separate.",
)
@click.option("--notes", default="", help="Optional notes for the new project intake.")
def init(
    force: bool,
    non_interactive: bool,
    mode: str | None,
    project_name: str,
    project_parent: Path,
    project_git_init: bool,
    product_goal: str,
    project_type: str,
    starter_profile: str,
    target_users: str,
    success_criteria: str,
    stack_preferences: tuple[str, ...],
    first_milestone: str,
    constraints: tuple[str, ...],
    notes: str,
):
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

    new_project = _build_init_new_project_request(
        mode,
        project_name=project_name,
        project_parent=project_parent,
        project_git_init=project_git_init,
        product_goal=product_goal,
        project_type=project_type,
        starter_profile=starter_profile,
        target_users=target_users,
        success_criteria=success_criteria,
        stack_preferences=stack_preferences,
        first_milestone=first_milestone,
        constraints=constraints,
        notes=notes,
    )
    effective_mode = mode or ("new" if new_project is not None else None)

    if non_interactive:
        _init_default(target, force, effective_mode, new_project)
    else:
        _init_interactive(target, force, effective_mode, new_project)


def _init_interactive(
    target: Path,
    force: bool,
    mode: str | None,
    new_project: InitNewProjectRequest | None = None,
) -> None:
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
    project_mode = _resolve_init_project_mode(
        mode,
        lang=wizard.language,
        interactive=True,
    )
    project_intake = _build_init_project_intake(project_mode)

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
    intake_paths = _write_init_project_intake(target, project_intake)
    new_project_intake, new_project_paths, new_project_git = (
        _write_init_new_project(target, new_project)
    )

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
    if new_project_intake is not None and new_project_paths is not None:
        summary_lines.extend(
            [
                f"  New project workspace: {new_project_intake.target_workspace}",
                f"  Git init: {new_project_git}",
                f"  Project intake: {new_project_paths.markdown_path}",
                _project_intake_next_steps_for_intake(new_project_intake),
            ]
        )
    elif intake_paths is not None:
        summary_lines.append(f"  Project intake: {intake_paths.markdown_path}")
        summary_lines.append(_project_intake_next_steps(project_mode))
    elif project_mode == "new":
        summary_lines.append(_project_intake_next_steps(project_mode))

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


def _init_default(
    target: Path,
    force: bool,
    mode: str | None = None,
    new_project: InitNewProjectRequest | None = None,
) -> None:
    """Non-interactive init with defaults (original behavior)."""
    config = TrinityConfig.default_config(project_dir=Path.cwd())
    state = target
    project_mode = mode
    project_intake = _build_init_project_intake(project_mode)

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
    intake_paths = _write_init_project_intake(state, project_intake)
    new_project_intake, new_project_paths, new_project_git = (
        _write_init_new_project(state, new_project)
    )
    new_project_line = (
        f"  New project workspace: {new_project_intake.target_workspace}\n"
        f"  Git init: {new_project_git}\n"
        f"  Project intake: {new_project_paths.markdown_path}\n"
        f"{_project_intake_next_steps_for_intake(new_project_intake)}\n"
        if new_project_intake is not None and new_project_paths is not None
        else ""
    )
    intake_line = (
        f"  Project intake: {intake_paths.markdown_path}\n"
        f"{_project_intake_next_steps(project_mode)}\n"
        if intake_paths is not None and not new_project_line
        else ""
    )
    next_steps_line = (
        f"{_project_intake_next_steps(project_mode)}\n"
        if project_mode == "new" and intake_paths is None and not new_project_line
        else ""
    )

    console.print(Panel.fit(
        "[green]✓ Trinity initialized![/green]\n\n"
        f"  Directory: {state}\n"
        f"  Config:    {state / 'trinity.config'}\n"
        f"  Shared:    {state / 'shared.md'}\n"
        f"{new_project_line}"
        f"{intake_line}\n"
        f"{next_steps_line}"
        "[dim]Edit .trinity/trinity.config to customize agents and settings.[/dim]",
        title="Trinity Init",
    ))


def _project_intake_next_steps(mode: str | None = "existing") -> str:
    steps = ["  Next steps:"]
    if mode == "new":
        steps.append("    trinity project new NAME --parent PATH")
    steps.extend(
        [
            "    trinity project status",
            "    trinity",
        ]
    )
    return "\n".join(steps)


def _project_intake_next_steps_for_intake(intake: ProjectIntake) -> str:
    return "\n".join(["  Next steps:", *_project_next_step_lines(intake)])


def _resolve_init_project_mode(
    mode: str | None,
    *,
    lang: str,
    interactive: bool,
) -> str | None:
    """Resolve the optional project intake mode for init."""
    if mode:
        return mode
    if not interactive:
        return None
    prompt = "프로젝트 모드" if lang == "ko" else "Project mode"
    return Prompt.ask(
        prompt,
        choices=["existing", "new"],
        default="existing",
        console=console,
    )


def _build_init_new_project_request(
    mode: str | None,
    *,
    project_name: str,
    project_parent: Path,
    project_git_init: bool,
    product_goal: str,
    project_type: str,
    starter_profile: str,
    target_users: str,
    success_criteria: str,
    stack_preferences: tuple[str, ...],
    first_milestone: str,
    constraints: tuple[str, ...],
    notes: str,
) -> InitNewProjectRequest | None:
    name = project_name.strip()
    if not name:
        return None
    if mode == "existing":
        raise click.ClickException("--project-name requires --mode new.")
    _resolve_project_workspace_target(project_parent, name)
    return InitNewProjectRequest(
        name=name,
        parent=project_parent,
        git_init=project_git_init,
        product_goal=product_goal,
        project_type=project_type,
        starter_profile=starter_profile,
        target_users=target_users,
        success_criteria=success_criteria,
        stack_preferences=_split_option_values(stack_preferences),
        first_milestone=first_milestone,
        constraints=_split_option_values(constraints),
        notes=notes,
    )


def _build_init_project_intake(mode: str | None) -> ProjectIntake | None:
    if mode is None:
        return None
    if mode == "new":
        return None
    return build_project_intake(mode=mode, target_workspace=Path.cwd())


def _write_init_project_intake(
    state: Path,
    intake: ProjectIntake | None,
) -> ProjectIntakePaths | None:
    if intake is None:
        return None
    return write_project_intake(state, intake)


def _write_init_new_project(
    state: Path,
    request: InitNewProjectRequest | None,
) -> tuple[ProjectIntake | None, ProjectIntakePaths | None, str]:
    if request is None:
        return None, None, ""
    target_workspace = _create_project_workspace(request.parent, request.name)
    git_status = _maybe_init_git_repo(target_workspace, git_init=request.git_init)
    intake = build_project_intake(
        mode="new",
        target_workspace=target_workspace,
        product_goal=request.product_goal,
        project_type=request.project_type,
        starter_profile=request.starter_profile,
        target_users=request.target_users,
        success_criteria=request.success_criteria,
        stack_preferences=request.stack_preferences,
        first_milestone=request.first_milestone,
        constraints=request.constraints,
        notes=request.notes,
    )
    paths = write_project_intake(state, intake)
    return intake, paths, git_status


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


# ─── trinity project ─────────────────────────────────────────────────────

@main.group()
def project() -> None:
    """Project onboarding and analysis utilities."""


@project.command("new")
@click.argument("name")
@click.option(
    "--parent",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Parent directory where the new project folder will be created.",
)
@click.option(
    "--git/--no-git",
    "git_init",
    default=False,
    show_default=True,
    help="Initialize a Git repository in the new project folder.",
)
@click.option(
    "--goal",
    "product_goal",
    default="",
    help="Product goal for the new project brief.",
)
@click.option(
    "--project-type",
    default="",
    help="Project type or product category for the brief.",
)
@click.option(
    "--starter-profile",
    "--starter",
    default="",
    help="Initial implementation/repository shape for the new project.",
)
@click.option(
    "--target-users",
    default="",
    help="Target users or audience for the brief.",
)
@click.option(
    "--success-criteria",
    default="",
    help="Success criteria for the brief.",
)
@click.option(
    "--stack",
    "stack_preferences",
    multiple=True,
    help="Preferred stack item for the project brief. Repeat or comma-separate.",
)
@click.option(
    "--milestone",
    "first_milestone",
    default="",
    help="First milestone for the project brief.",
)
@click.option(
    "--constraint",
    "constraints",
    multiple=True,
    help="Project constraint for the brief. Repeat or comma-separate.",
)
@click.option("--notes", default="", help="Optional notes to store in project intake.")
def project_new(
    name: str,
    parent: Path,
    git_init: bool,
    product_goal: str,
    project_type: str,
    starter_profile: str,
    target_users: str,
    success_criteria: str,
    stack_preferences: tuple[str, ...],
    first_milestone: str,
    constraints: tuple[str, ...],
    notes: str,
) -> None:
    """Create a new target project folder and write project intake artifacts."""
    config_path = find_config_path()
    if config_path is None:
        raise click.ClickException("No Trinity project found. Run `trinity init` first.")

    config = TrinityConfig.load(config_path)
    target_workspace = _create_project_workspace(parent, name)
    git_status = _maybe_init_git_repo(target_workspace, git_init=git_init)
    intake = build_project_intake(
        mode="new",
        target_workspace=target_workspace,
        product_goal=product_goal,
        project_type=project_type,
        starter_profile=starter_profile,
        target_users=target_users,
        success_criteria=success_criteria,
        stack_preferences=_split_option_values(stack_preferences),
        first_milestone=first_milestone,
        constraints=_split_option_values(constraints),
        notes=notes,
    )
    paths = write_project_intake(config.effective_state_dir, intake)
    _display_project_new_summary(
        intake,
        paths.json_path,
        paths.markdown_path,
        git_status=git_status,
    )


@project.command("analyze")
@click.argument("path", required=False, type=click.Path(path_type=Path))
@click.option(
    "--mode",
    type=click.Choice(["existing", "new"]),
    default="existing",
    show_default=True,
    help="Project onboarding mode to store in the intake artifact.",
)
@click.option(
    "--goal",
    "product_goal",
    default="",
    help="Product goal to store in project intake.",
)
@click.option(
    "--project-type",
    default="",
    help="Project type or product category to store in project intake.",
)
@click.option(
    "--starter-profile",
    "--starter",
    default="",
    help="Initial implementation/repository shape to store in project intake.",
)
@click.option(
    "--target-users",
    default="",
    help="Target users or audience to store in project intake.",
)
@click.option(
    "--success-criteria",
    default="",
    help="Success criteria to store in project intake.",
)
@click.option(
    "--stack",
    "stack_preferences",
    multiple=True,
    help="Preferred stack item for project intake. Repeat or comma-separate.",
)
@click.option(
    "--milestone",
    "first_milestone",
    default="",
    help="First milestone to store in project intake.",
)
@click.option(
    "--constraint",
    "constraints",
    multiple=True,
    help="Project constraint to store in intake. Repeat or comma-separate.",
)
@click.option(
    "--scope",
    "selected_scope",
    default="",
    help="Existing-project relative work scope to store in project intake.",
)
@click.option("--notes", default="", help="Optional notes to store in project intake.")
def project_analyze(
    path: Path | None,
    mode: str,
    product_goal: str,
    project_type: str,
    starter_profile: str,
    target_users: str,
    success_criteria: str,
    stack_preferences: tuple[str, ...],
    first_milestone: str,
    constraints: tuple[str, ...],
    selected_scope: str,
    notes: str,
) -> None:
    """Analyze a target workspace and write project intake artifacts."""
    config_path = find_config_path()
    if config_path is None:
        raise click.ClickException(
            "No Trinity project found. Run `trinity init` first."
        )

    config = TrinityConfig.load(config_path)
    target_workspace = path or Path.cwd()
    intake = build_project_intake(
        mode=mode,
        target_workspace=target_workspace,
        product_goal=product_goal,
        project_type=project_type,
        starter_profile=starter_profile,
        target_users=target_users,
        success_criteria=success_criteria,
        stack_preferences=_split_option_values(stack_preferences),
        first_milestone=first_milestone,
        constraints=_split_option_values(constraints),
        selected_scope=selected_scope,
        notes=notes,
    )
    paths = write_project_intake(config.effective_state_dir, intake)
    _display_project_intake_summary(intake, paths.json_path, paths.markdown_path)


@project.command("status")
@click.option("--json", "json_output", is_flag=True, help="Print status as JSON.")
@click.option(
    "--refresh",
    is_flag=True,
    help="Refresh saved intake from the current target workspace before display.",
)
def project_status(json_output: bool, refresh: bool) -> None:
    """Show the currently recorded project intake."""
    config_path = find_config_path()
    if config_path is None:
        raise click.ClickException("No Trinity project found. Run `trinity init` first.")

    config = TrinityConfig.load(config_path)
    try:
        intake = load_project_intake(config.effective_state_dir)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if intake is None:
        if json_output:
            _display_project_status_json(
                None,
                state_dir=config.effective_state_dir,
            )
            return
        _display_missing_project_intake_status()
        return
    paths: ProjectIntakePaths | None = None
    if refresh:
        intake, paths = _refresh_project_intake(config, intake)
    if json_output:
        _display_project_status_json(
            intake,
            state_dir=config.effective_state_dir,
            refreshed=refresh,
            paths=paths,
        )
        return
    _display_project_status(intake, refreshed=refresh, paths=paths)


def _refresh_project_intake(
    config: TrinityConfig,
    intake: ProjectIntake,
) -> tuple[ProjectIntake, ProjectIntakePaths]:
    refreshed = build_project_intake(
        mode=intake.mode,
        target_workspace=intake.target_workspace,
        product_goal=intake.product_goal,
        project_type=intake.project_type,
        starter_profile=intake.starter_profile,
        target_users=intake.target_users,
        success_criteria=intake.success_criteria,
        stack_preferences=intake.stack_preferences,
        first_milestone=intake.first_milestone,
        constraints=intake.constraints,
        selected_scope=intake.selected_scope,
        notes=intake.notes,
    )
    paths = write_project_intake(config.effective_state_dir, refreshed)
    return refreshed, paths


def _create_project_workspace(parent: Path, name: str) -> Path:
    target = _resolve_project_workspace_target(parent, name)
    try:
        target.mkdir()
    except OSError as exc:
        raise click.ClickException(
            f"Could not create project directory: {exc}"
        ) from exc
    return target.resolve()


def _resolve_project_workspace_target(parent: Path, name: str) -> Path:
    project_name = name.strip()
    if not project_name:
        raise click.ClickException("Project name is required.")
    name_path = Path(project_name)
    if name_path.is_absolute() or len(name_path.parts) != 1:
        raise click.ClickException("Project name must be a single folder name.")

    parent_path = parent.expanduser()
    if not parent_path.exists():
        raise click.ClickException(f"Parent directory does not exist: {parent_path}")
    if not parent_path.is_dir():
        raise click.ClickException(f"Parent path is not a directory: {parent_path}")

    target = parent_path / project_name
    if target.exists():
        raise click.ClickException(f"Project directory already exists: {target}")
    return target


def _maybe_init_git_repo(target: Path, *, git_init: bool) -> str:
    if not git_init:
        return "skipped"
    if shutil.which("git") is None:
        raise click.ClickException("git command not found. Re-run with --no-git.")
    try:
        completed = subprocess.run(
            ["git", "init"],
            cwd=target,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise click.ClickException(f"git init failed: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise click.ClickException(f"git init failed: {detail or completed.returncode}")
    return "initialized"


def _display_project_new_summary(
    intake: ProjectIntake,
    json_path: Path,
    markdown_path: Path,
    *,
    git_status: str,
) -> None:
    body = "\n".join(
        [
            "[green]New project workspace created.[/green]",
            "",
            f"Target workspace: {intake.target_workspace}",
            f"Git init: {git_status}",
            *_project_brief_readiness_lines(intake),
            *_project_brief_lines(intake),
            "",
            f"JSON: {json_path}",
            f"Markdown: {markdown_path}",
            "",
            "Next steps:",
            *_project_next_step_lines(intake),
        ]
    )
    console.print(Panel.fit(body, title="Trinity Project"))


def _display_project_intake_summary(
    intake: ProjectIntake,
    json_path: Path,
    markdown_path: Path,
) -> None:
    """Display a compact project intake write summary."""
    body = "\n".join(
        [
            "[green]Project intake written.[/green]",
            "",
            f"Mode: {intake.mode}",
            f"Target workspace: {intake.target_workspace}",
            f"Git repo: {intake.git_repo}",
            f"Branch: {intake.branch}",
            f"Dirty count: {_unknown_if_none(intake.dirty_count)}",
            f"Untracked count: {_unknown_if_none(intake.untracked_count)}",
            f"Package managers: {_csv_or_none(intake.package_managers)}",
            f"Test commands: {_csv_or_none(intake.test_commands)}",
            f"Selected scope: {_text_or_none(intake.selected_scope)}",
            *_project_brief_readiness_lines(intake),
            *_project_brief_lines(intake),
            "",
            f"JSON: {json_path}",
            f"Markdown: {markdown_path}",
            "",
            "Next steps:",
            *_project_next_step_lines(intake),
        ]
    )
    console.print(Panel.fit(body, title="Trinity Project"))


def _display_missing_project_intake_status() -> None:
    body = "\n".join(
        [
            "[yellow]No project intake recorded.[/yellow]",
            "",
            "Existing project: run `trinity project analyze [PATH]`.",
            "New project: run `trinity project new NAME`.",
            "Then run `trinity` to start planning.",
        ]
    )
    console.print(Panel.fit(body, title="Trinity Project"))


def _display_project_status_json(
    intake: ProjectIntake | None,
    *,
    state_dir: Path | None = None,
    refreshed: bool = False,
    paths: ProjectIntakePaths | None = None,
) -> None:
    click.echo(
        json.dumps(
            _project_status_payload(
                intake,
                state_dir=state_dir,
                refreshed=refreshed,
                paths=paths,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


def _project_status_payload(
    intake: ProjectIntake | None,
    *,
    state_dir: Path | None = None,
    refreshed: bool = False,
    paths: ProjectIntakePaths | None = None,
) -> dict[str, object]:
    if intake is None:
        return {
            "project_intake": None,
            "current_analysis": None,
            "refreshed": False,
            "project_intake_paths": None,
            "next_steps": [
                "trinity project analyze [PATH]",
                "trinity project new NAME",
                "trinity",
            ],
        }

    target_exists = intake.target_workspace.exists()
    live_git = analyze_git_workspace(intake.target_workspace) if target_exists else None
    live_package_managers = (
        detect_package_managers(intake.target_workspace)
        if target_exists
        else intake.package_managers
    )
    live_test_commands = (
        suggest_test_commands(intake.target_workspace, live_package_managers)
        if target_exists
        else intake.test_commands
    )
    live_scope_candidates = (
        detect_scope_candidates(intake.target_workspace)
        if target_exists
        else intake.scope_candidates
    )
    analysis_changed_fields = _project_intake_analysis_changed_fields_for_status(
        intake,
        target_exists=target_exists,
        live_git=live_git,
    )
    return {
        "project_intake": {
            "summary": format_project_intake_label(intake),
            "generation_preview": format_project_generation_preview_label(
                intake,
                target_workspace=intake.target_workspace,
            ),
            "validation_plan": format_project_validation_plan_label(
                intake,
                target_workspace=intake.target_workspace,
            ),
            "read_first_checklist": format_project_read_first_checklist_label(
                intake,
                target_workspace=intake.target_workspace,
            ),
            "mode": intake.mode,
            "target_name": intake.target_workspace.name or "(root)",
            "target_workspace": str(intake.target_workspace),
            "created_at": intake.created_at,
            "git_repo": intake.git_repo,
            "branch": intake.branch,
            "dirty_count": intake.dirty_count,
            "untracked_count": intake.untracked_count,
            "package_managers": list(intake.package_managers),
            "test_commands": list(intake.test_commands),
            "scope_candidates": list(intake.scope_candidates),
            "selected_scope": intake.selected_scope,
            "brief_readiness": _project_brief_readiness_payload(intake),
            "readiness": _project_intake_readiness_payload(
                intake,
                target_exists=target_exists,
                analysis_changed_fields=analysis_changed_fields,
            ),
            "action_variants": _project_intake_action_variants_payload(
                state_dir,
                intake,
            ),
            "product_goal": intake.product_goal,
            "project_type": intake.project_type,
            "starter_profile": intake.starter_profile,
            "target_users": intake.target_users,
            "success_criteria": intake.success_criteria,
            "stack_preferences": list(intake.stack_preferences),
            "first_milestone": intake.first_milestone,
            "constraints": list(intake.constraints),
            "notes": intake.notes,
        },
        "current_analysis": {
            "target_exists": target_exists,
            "git_repo": live_git.git_repo if live_git is not None else False,
            "branch": live_git.branch if live_git is not None else "unknown",
            "dirty_count": live_git.dirty_count if live_git is not None else None,
            "untracked_count": (
                live_git.untracked_count if live_git is not None else None
            ),
            "package_managers": list(live_package_managers),
            "test_commands": list(live_test_commands),
            "scope_candidates": list(live_scope_candidates),
        },
        "refreshed": refreshed,
        "project_intake_paths": _project_intake_paths_payload(paths),
        "next_steps": _project_next_steps(
            intake,
            include_status=False,
            analysis_changed_fields=analysis_changed_fields,
        ),
    }


def _project_intake_readiness_payload(
    intake: ProjectIntake,
    *,
    target_exists: bool,
    analysis_changed_fields: tuple[str, ...] = (),
) -> dict[str, object]:
    stale_days = _project_intake_analysis_stale_days_for_status(intake)
    sparse = _project_intake_analysis_sparse_for_status(intake)
    target_missing = not target_exists
    missing_brief_fields = list(missing_new_project_brief_field_keys(intake))
    recommended_action = _project_intake_recommended_action(
        intake,
        target_missing=target_missing,
        analysis_sparse=sparse,
        analysis_stale=stale_days is not None,
        analysis_changed=bool(analysis_changed_fields),
        missing_brief_fields=tuple(missing_brief_fields),
        scope_choice_required=_project_scope_choice_required(intake),
    )
    return {
        "ready": recommended_action == "start_trinity",
        "recommended_action": recommended_action,
        "target_exists": target_exists,
        "target_missing": target_missing,
        "analysis_sparse": sparse,
        "analysis_missing_anchors": list(
            _project_intake_missing_analysis_anchors_for_status(intake)
        ),
        "analysis_stale": stale_days is not None,
        "analysis_stale_days": stale_days,
        "analysis_changed": bool(analysis_changed_fields),
        "analysis_changed_fields": list(analysis_changed_fields),
        "missing_brief_fields": missing_brief_fields,
        "scope_choice_required": _project_scope_choice_required(intake),
        "scope_candidates": list(intake.scope_candidates),
    }


def _project_intake_action_variants_payload(
    state_dir: Path | None,
    intake: ProjectIntake,
) -> dict[str, str]:
    if state_dir is None:
        return {}
    target_workspace = intake.target_workspace
    return {
        "analyze_workspace": project_analyze_action_variant(
            state_dir,
            target_workspace=target_workspace,
        ),
        "create_project": project_create_action_variant(
            state_dir,
            target_workspace=target_workspace,
        ),
        "edit_brief": project_brief_action_variant(
            state_dir,
            target_workspace=target_workspace,
        ),
    }


def _project_intake_recommended_action(
    intake: ProjectIntake,
    *,
    target_missing: bool,
    analysis_sparse: bool,
    analysis_stale: bool,
    analysis_changed: bool = False,
    missing_brief_fields: tuple[str, ...],
    scope_choice_required: bool = False,
) -> str:
    if target_missing:
        return "create_project" if intake.mode == "new" else "analyze_workspace"
    if intake.mode == "new" and missing_brief_fields:
        return "edit_brief"
    if analysis_sparse or analysis_stale or analysis_changed:
        return "analyze_workspace"
    if scope_choice_required:
        return "choose_scope"
    return "start_trinity"


def _project_intake_analysis_changed_fields_for_status(
    intake: ProjectIntake,
    *,
    target_exists: bool,
    live_git: GitWorkspaceAnalysis | None = None,
) -> tuple[str, ...]:
    if not target_exists or intake.mode != "existing":
        return ()
    return existing_project_intake_drift_fields(
        intake,
        intake.target_workspace,
        live_git=live_git,
    )


def _project_analysis_changed_status_lines(
    fields: tuple[str, ...],
) -> list[str]:
    if not fields:
        return []
    return [
        f"  Analysis changed: {_csv_or_none(fields)}",
        "  Refresh: trinity project status --refresh",
    ]


def _project_intake_analysis_sparse_for_status(intake: ProjectIntake) -> bool:
    if intake.mode != "existing":
        return False
    return not (
        intake.test_commands
        or intake.source_roots
        or intake.scope_candidates
        or intake.docs_found
    )


def _project_intake_missing_analysis_anchors_for_status(
    intake: ProjectIntake,
) -> tuple[str, ...]:
    if intake.mode != "existing":
        return ()
    missing: list[str] = []
    if not intake.test_commands:
        missing.append("tests")
    if not intake.source_roots:
        missing.append("source_roots")
    if not intake.docs_found:
        missing.append("docs")
    return tuple(missing)


def _project_intake_analysis_stale_days_for_status(
    intake: ProjectIntake,
) -> int | None:
    if intake.mode != "existing":
        return None
    text = intake.created_at.strip()
    if len(text) < 10:
        return None
    try:
        created_on = date.fromisoformat(text[:10])
    except ValueError:
        return None
    age_days = (date.today() - created_on).days
    if age_days <= PROJECT_INTAKE_STALE_AFTER_DAYS:
        return None
    return age_days


def _project_intake_paths_payload(
    paths: ProjectIntakePaths | None,
) -> dict[str, str] | None:
    if paths is None:
        return None
    return {
        "json": str(paths.json_path),
        "markdown": str(paths.markdown_path),
    }


def _display_project_status(
    intake: ProjectIntake,
    *,
    refreshed: bool = False,
    paths: ProjectIntakePaths | None = None,
) -> None:
    target_exists = intake.target_workspace.exists()
    live_git = analyze_git_workspace(intake.target_workspace) if target_exists else None
    live_package_managers = (
        detect_package_managers(intake.target_workspace)
        if target_exists
        else intake.package_managers
    )
    live_test_commands = (
        suggest_test_commands(intake.target_workspace, live_package_managers)
        if target_exists
        else intake.test_commands
    )
    live_scope_candidates = (
        detect_scope_candidates(intake.target_workspace)
        if target_exists
        else intake.scope_candidates
    )
    live_branch = live_git.branch if live_git is not None else "unknown"
    live_dirty = live_git.dirty_count if live_git is not None else None
    live_untracked = live_git.untracked_count if live_git is not None else None
    analysis_changed_fields = _project_intake_analysis_changed_fields_for_status(
        intake,
        target_exists=target_exists,
        live_git=live_git,
    )
    lines = [
        "[green]Project intake active.[/green]",
        f"Summary: {format_project_intake_label(intake)}",
    ]
    generation_preview = format_project_generation_preview_label(
        intake,
        target_workspace=intake.target_workspace,
    )
    if generation_preview:
        lines.append(generation_preview)
    validation_plan = format_project_validation_plan_label(
        intake,
        target_workspace=intake.target_workspace,
    )
    if validation_plan:
        lines.append(validation_plan)
    read_first_checklist = format_project_read_first_checklist_label(
        intake,
        target_workspace=intake.target_workspace,
    )
    if read_first_checklist:
        lines.append(read_first_checklist)
    if refreshed:
        lines.extend(
            [
                "[green]Project intake refreshed.[/green]",
                f"JSON: {paths.json_path if paths is not None else '(unknown)'}",
                f"Markdown: {paths.markdown_path if paths is not None else '(unknown)'}",
            ]
        )
    lines.extend(
        [
            "",
            f"Mode: {intake.mode}",
            f"Target name: {intake.target_workspace.name or '(root)'}",
            f"Target workspace: {intake.target_workspace}",
            f"Target exists: {target_exists}",
            f"Created at: {intake.created_at}",
            "",
            "Saved analysis:",
            f"  Git repo: {intake.git_repo}",
            f"  Branch: {intake.branch}",
            f"  Dirty count: {_unknown_if_none(intake.dirty_count)}",
            f"  Untracked count: {_unknown_if_none(intake.untracked_count)}",
            f"  Package managers: {_csv_or_none(intake.package_managers)}",
            f"  Test commands: {_csv_or_none(intake.test_commands)}",
            f"  Scope candidates: {_csv_or_none(intake.scope_candidates)}",
            f"  Selected scope: {_text_or_none(intake.selected_scope)}",
            *_project_brief_readiness_status_lines(intake),
            *_project_brief_status_lines(intake),
            "",
            "Current analysis:",
            f"  Branch: {live_branch}",
            f"  Dirty count: {_unknown_if_none(live_dirty)}",
            f"  Untracked count: {_unknown_if_none(live_untracked)}",
            f"  Package managers: {_csv_or_none(live_package_managers)}",
            f"  Test commands: {_csv_or_none(live_test_commands)}",
            f"  Scope candidates: {_csv_or_none(live_scope_candidates)}",
            *_project_analysis_changed_status_lines(analysis_changed_fields),
            "",
            "Next steps:",
            *_project_next_step_lines(
                intake,
                include_status=False,
                analysis_changed_fields=analysis_changed_fields,
            ),
        ]
    )
    body = "\n".join(lines)
    console.print(Panel.fit(body, title="Trinity Project"))


def _unknown_if_none(value: int | None) -> str:
    return str(value) if value is not None else "unknown"


def _csv_or_none(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "(none)"


def _text_or_none(value: str) -> str:
    text = value.strip()
    return text if text else "(none)"


def _split_option_values(values: tuple[str, ...]) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        items.extend(part.strip() for part in value.split(","))
    return tuple(dict.fromkeys(item for item in items if item))


def _project_next_steps(
    intake: ProjectIntake,
    *,
    include_status: bool = True,
    analysis_changed_fields: tuple[str, ...] = (),
) -> list[str]:
    recovery = _project_target_recovery_command(intake)
    if recovery:
        return [recovery]
    steps: list[str] = []
    completion = _project_brief_completion_command(intake)
    if completion:
        steps.append(completion)
    if analysis_changed_fields:
        steps.append("trinity project status --refresh")
    else:
        scope_command = _project_scope_choice_command(intake)
        if scope_command:
            steps.append(scope_command)
    if include_status:
        steps.append("trinity project status")
    steps.append("trinity")
    return steps


def _project_next_step_lines(
    intake: ProjectIntake,
    *,
    include_status: bool = True,
    analysis_changed_fields: tuple[str, ...] = (),
) -> list[str]:
    recovery = _project_target_recovery_lines(intake)
    if recovery:
        return recovery
    lines = _project_brief_completion_lines(intake)
    if analysis_changed_fields:
        lines.append("  trinity project status --refresh")
    else:
        lines.extend(_project_scope_choice_lines(intake))
    if include_status:
        lines.append("  trinity project status")
    lines.append("  trinity")
    return lines


def _project_target_recovery_command(intake: ProjectIntake) -> str:
    if not _project_target_missing(intake):
        return ""
    if intake.mode == "new" and intake.target_workspace.name:
        return " ".join(
            [
                "trinity project new",
                _quote_cli_arg(intake.target_workspace.name),
                "--parent",
                _quote_cli_arg(str(intake.target_workspace.parent)),
            ]
        )
    return "trinity project analyze [PATH]"


def _project_target_recovery_lines(intake: ProjectIntake) -> list[str]:
    if not _project_target_missing(intake):
        return []
    if intake.mode == "new" and intake.target_workspace.name:
        return [
            f"  trinity project new {_quote_cli_arg(intake.target_workspace.name)}",
            f"    --parent {_quote_cli_arg(str(intake.target_workspace.parent))}",
        ]
    return ["  trinity project analyze [PATH]"]


def _project_target_missing(intake: ProjectIntake) -> bool:
    try:
        return not intake.target_workspace.exists()
    except OSError:
        return True


def _project_scope_choice_required(intake: ProjectIntake) -> bool:
    if intake.mode != "existing":
        return False
    return bool(intake.scope_candidates and not intake.selected_scope.strip())


def _project_scope_choice_command(intake: ProjectIntake) -> str:
    if not _project_scope_choice_required(intake):
        return ""
    return " ".join(
        [
            "trinity project analyze",
            _quote_cli_arg(str(intake.target_workspace)),
            "--scope",
            "<scope>",
        ]
    )


def _project_scope_choice_lines(intake: ProjectIntake) -> list[str]:
    if not _project_scope_choice_required(intake):
        return []
    target = _project_human_cli_target(intake.target_workspace)
    command = " ".join(
        [
            "trinity project analyze",
            _quote_cli_arg(target),
            "--scope",
            "<scope>",
        ]
    )
    return [
        f"  {command}",
        f"    choose one of: {_csv_or_none(intake.scope_candidates)}",
    ]


def _project_human_cli_target(target: Path) -> str:
    """Return a compact target path for human-facing CLI examples."""
    try:
        return target.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except (OSError, ValueError):
        return str(target)


def _project_brief_completion_command(intake: ProjectIntake) -> str:
    missing = missing_new_project_brief_field_keys(intake)
    if not missing:
        return ""
    options = [
        _project_brief_completion_option(field_name)
        for field_name in missing
    ]
    return " ".join(
        [
            "trinity project analyze",
            _quote_cli_arg(str(intake.target_workspace)),
            "--mode new",
            *options,
        ]
    )


def _project_brief_completion_lines(intake: ProjectIntake) -> list[str]:
    missing = missing_new_project_brief_field_keys(intake)
    if not missing:
        return []
    return [
        "  trinity project analyze",
        f"    {_quote_cli_arg(str(intake.target_workspace))}",
        "    --mode new",
        *[
            f"    {_project_brief_completion_option(field_name)}"
            for field_name in missing
        ],
    ]


def _project_brief_completion_option(field_name: str) -> str:
    option_map = {
        "product_goal": '--goal "<goal>"',
        "project_type": '--project-type "<type>"',
        "target_users": '--target-users "<users>"',
        "success_criteria": '--success-criteria "<success>"',
        "first_milestone": '--milestone "<milestone>"',
    }
    return option_map[field_name]


def _quote_cli_arg(value: str) -> str:
    if not value:
        return '""'
    if not any(char.isspace() or char == '"' for char in value):
        return value
    return '"' + value.replace('"', '\\"') + '"'


def _project_brief_readiness_payload(intake: ProjectIntake) -> dict[str, object]:
    missing = missing_new_project_brief_fields(intake)
    return {
        "required": intake.mode == "new",
        "complete": intake.mode != "new" or not missing,
        "missing_fields": list(missing),
    }


def _project_brief_readiness_lines(intake: ProjectIntake) -> list[str]:
    if intake.mode != "new":
        return []
    missing = missing_new_project_brief_fields(intake)
    if not missing:
        return ["Brief readiness: complete"]
    return [f"Brief readiness: missing {_csv_or_none(missing)}"]


def _project_brief_readiness_status_lines(intake: ProjectIntake) -> list[str]:
    return [f"  {line}" for line in _project_brief_readiness_lines(intake)]


def _project_brief_lines(intake: ProjectIntake) -> list[str]:
    lines: list[str] = []
    if intake.product_goal:
        lines.append(f"Product goal: {intake.product_goal}")
    if intake.project_type:
        lines.append(f"Project type: {intake.project_type}")
    if intake.starter_profile:
        lines.append(f"Starter profile: {intake.starter_profile}")
    if intake.target_users:
        lines.append(f"Target users: {intake.target_users}")
    if intake.success_criteria:
        lines.append(f"Success criteria: {intake.success_criteria}")
    if intake.stack_preferences:
        lines.append(f"Stack preferences: {_csv_or_none(intake.stack_preferences)}")
    if intake.first_milestone:
        lines.append(f"First milestone: {intake.first_milestone}")
    if intake.constraints:
        lines.append(f"Constraints: {_csv_or_none(intake.constraints)}")
    if lines:
        return ["", "Project brief:", *lines]
    return []


def _project_brief_status_lines(intake: ProjectIntake) -> list[str]:
    lines = _project_brief_lines(intake)
    if not lines:
        return []
    return [
        line if not line or line == "Project brief:" else f"  {line}"
        for line in lines
    ]


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

    from trinity.context.commands import engine_from_config

    engine = engine_from_config(config)

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


# ─── trinity memory ──────────────────────────────────────────────────────

@main.group()
def memory():
    """Inspect or compact the shared context memory index."""


@memory.command("stats")
def memory_stats():
    """Show shared context memory stats."""
    config = load_config()
    from trinity.context.commands import engine_from_config, memory_stats_rows

    engine = engine_from_config(config)
    table = Table(title="Memory Stats")
    table.add_column("Item")
    table.add_column("Value")
    for key, value in memory_stats_rows(engine):
        table.add_row(key, value)
    console.print(table)


@memory.command("compact")
def memory_compact():
    """Rebuild shared.md as a bounded memory projection."""
    config = load_config()
    from trinity.context.commands import compact_memory_markdown, engine_from_config

    engine = engine_from_config(config)
    console.print(
        compact_memory_markdown(
            engine,
            target_bytes=config.shared_compact_target_bytes,
            recent_records=config.memory_recent_records,
        )
    )


@memory.command("cleanup")
@click.option(
    "--oversized-backups",
    is_flag=True,
    help="Target shared.md.oversized-* backup files.",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    help="Delete cleanup candidates. Without this flag, only show a dry-run.",
)
@click.option(
    "--keep-latest",
    type=int,
    default=1,
    show_default=True,
    help="Retain the latest N oversized backup files.",
)
def memory_cleanup(oversized_backups: bool, apply_changes: bool, keep_latest: int):
    """Show or apply shared context memory cleanup candidates."""
    if not oversized_backups:
        console.print(
            "[yellow]Usage: trinity memory cleanup --oversized-backups "
            "[--apply] [--keep-latest N][/yellow]"
        )
        return
    if keep_latest < 0:
        raise click.BadParameter("--keep-latest must be 0 or greater")
    config = load_config()
    from trinity.context.commands import (
        cleanup_oversized_backups_markdown,
        engine_from_config,
    )

    console.print(
        cleanup_oversized_backups_markdown(
            engine_from_config(config),
            apply=apply_changes,
            keep_latest=keep_latest,
        )
    )


@main.command()
@click.argument("record_id")
def artifact(record_id: str):
    """Show an indexed memory artifact reference."""
    config = load_config()
    from trinity.context.commands import artifact_markdown, engine_from_config

    console.print(artifact_markdown(engine_from_config(config), record_id))


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
