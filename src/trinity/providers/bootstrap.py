"""Provider bootstrap helpers for isolated Trinity agent homes."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from trinity.models import AgentSpec
from trinity.config import TrinityConfig
from trinity.legacy.tmux.session import TmuxSessionManager
from trinity.platform.process import CommandSpec, ProcessRunner, render_command
from trinity.workspace.isolation import WorkspaceIsolation
from trinity.workspace.managed_home import ManagedHome


class ProviderBootstrapError(RuntimeError):
    """Raised when provider bootstrap cannot be started."""


@dataclass(frozen=True)
class ProviderBootstrapTarget:
    """Resolved launch metadata for one provider bootstrap pane."""

    agent_name: str
    spec: AgentSpec
    cwd: Path
    env_overrides: dict[str, str] = field(default_factory=dict)
    managed_home: Path | None = None
    workspace_path: Path | None = None


@dataclass(frozen=True)
class ProviderBootstrapResult:
    """Summary of a launched provider bootstrap session."""

    session_name: str
    targets: tuple[ProviderBootstrapTarget, ...]
    commands: dict[str, str]


@dataclass(frozen=True)
class ProviderBootstrapCheck:
    """Install/readiness check for one bootstrap target."""

    agent_name: str
    cli_command: str
    installed: bool
    path: str = ""
    error: str = ""


@dataclass(frozen=True)
class ProviderBootstrapRunResult:
    """Summary of sequential current-terminal bootstrap execution."""

    targets: tuple[ProviderBootstrapTarget, ...]
    commands: dict[str, tuple[str, ...]]
    checks: dict[str, ProviderBootstrapCheck]
    exit_codes: dict[str, int]
    check_only: bool = False

    @property
    def failed_agents(self) -> tuple[str, ...]:
        return tuple(
            name for name, code in self.exit_codes.items()
            if code != 0
        )


class ProviderBootstrapper:
    """Launch provider CLIs in the same isolated homes Trinity normally uses."""

    def __init__(self, runner: ProcessRunner | None = None):
        self.runner = runner or ProcessRunner()

    def select_agent_specs(
        self,
        config: TrinityConfig,
        agent_names: list[str] | None = None,
        include_disabled: bool = False,
    ) -> dict[str, AgentSpec]:
        """Select configured agent specs for bootstrap.

        Explicitly named agents are allowed even if disabled so users can prepare
        a provider before enabling it in normal deliberations.
        """
        if agent_names:
            unknown = [name for name in agent_names if name not in config.agents]
            if unknown:
                raise ProviderBootstrapError(
                    "Unknown agent(s): " + ", ".join(sorted(unknown))
                )
            return {name: config.agents[name] for name in agent_names}

        selected = config.agents if include_disabled else config.active_agents
        if not selected:
            raise ProviderBootstrapError(
                "No agents selected. Enable at least one agent or pass --all."
            )
        return dict(selected)

    def prepare_targets(
        self,
        config: TrinityConfig,
        agent_names: list[str] | None = None,
        include_disabled: bool = False,
    ) -> tuple[ProviderBootstrapTarget, ...]:
        """Create isolated homes and resolve cwd/env for selected agents."""
        specs = self.select_agent_specs(
            config,
            agent_names=agent_names,
            include_disabled=include_disabled,
        )
        state_dir = config.effective_state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "agents").mkdir(exist_ok=True)
        (state_dir / "history").mkdir(exist_ok=True)
        (state_dir / "logs").mkdir(exist_ok=True)

        managed_home = ManagedHome(state_dir=state_dir)
        needs_worktree = any(
            spec.workspace_mode == "git-worktree" for spec in specs.values()
        )
        workspace_isolation = (
            WorkspaceIsolation(
                project_root=config.project_dir,
                state_dir=state_dir / "workspace",
            )
            if needs_worktree
            else None
        )

        targets: list[ProviderBootstrapTarget] = []
        for name, spec in specs.items():
            provider_name = getattr(spec.provider, "value", str(spec.provider))
            home = managed_home.setup(name, provider=provider_name)
            env_overrides = managed_home.get_env_overrides(name)

            cwd = config.project_dir.resolve()
            workspace_path: Path | None = None
            if spec.workspace_mode == "git-worktree":
                if workspace_isolation is None:
                    raise ProviderBootstrapError("Workspace isolation was not initialized")
                workspace_path = workspace_isolation.create(name)
                cwd = workspace_path
            elif spec.workspace_mode != "inplace":
                raise ProviderBootstrapError(
                    f"Unsupported workspace_mode for agent '{name}': "
                    f"{spec.workspace_mode!r}"
                )

            targets.append(
                ProviderBootstrapTarget(
                    agent_name=name,
                    spec=spec,
                    cwd=cwd,
                    env_overrides=env_overrides,
                    managed_home=home,
                    workspace_path=workspace_path,
                )
            )

        return tuple(targets)

    def run_sequential(
        self,
        config: TrinityConfig,
        agent_names: list[str] | None = None,
        include_disabled: bool = False,
        check_only: bool = False,
        skip_ready: bool = False,
        continue_on_error: bool = False,
    ) -> ProviderBootstrapRunResult:
        """Run provider CLIs one by one in the current terminal."""
        targets = self.prepare_targets(
            config,
            agent_names=agent_names,
            include_disabled=include_disabled,
        )
        checks = self.check_targets(targets)
        commands = {
            target.agent_name: build_provider_argv(target.spec)
            for target in targets
        }

        if check_only:
            return ProviderBootstrapRunResult(
                targets=targets,
                commands=commands,
                checks=checks,
                exit_codes={},
                check_only=True,
            )

        if not skip_ready:
            missing = [
                check for check in checks.values()
                if not check.installed
            ]
            if missing:
                details = ", ".join(
                    f"{check.agent_name} ({check.cli_command})"
                    for check in missing
                )
                raise ProviderBootstrapError(
                    "Provider CLI command not found: "
                    f"{details}. Install the provider CLI or pass --skip-ready "
                    "to run anyway."
                )

        exit_codes: dict[str, int] = {}
        for target in targets:
            command = CommandSpec(
                argv=commands[target.agent_name],
                cwd=target.cwd,
                env=target.env_overrides,
            )
            exit_code = self.runner.stream_interactive(command)
            exit_codes[target.agent_name] = exit_code
            if exit_code != 0 and not continue_on_error:
                raise ProviderBootstrapError(
                    f"Provider bootstrap for '{target.agent_name}' exited with "
                    f"code {exit_code}. Pass --continue-on-error to continue."
                )

        return ProviderBootstrapRunResult(
            targets=targets,
            commands=commands,
            checks=checks,
            exit_codes=exit_codes,
        )

    def check_targets(
        self,
        targets: tuple[ProviderBootstrapTarget, ...],
    ) -> dict[str, ProviderBootstrapCheck]:
        """Check whether selected provider CLI commands are available."""
        checks: dict[str, ProviderBootstrapCheck] = {}
        for target in targets:
            path = shutil.which(target.spec.cli_command)
            checks[target.agent_name] = ProviderBootstrapCheck(
                agent_name=target.agent_name,
                cli_command=target.spec.cli_command,
                installed=path is not None,
                path=path or "",
                error="" if path else f"'{target.spec.cli_command}' not found in PATH",
            )
        return checks

    def launch_legacy_tmux_session(
        self,
        config: TrinityConfig,
        agent_names: list[str] | None = None,
        include_disabled: bool = False,
        session_name: str | None = None,
        force: bool = False,
    ) -> ProviderBootstrapResult:
        """Create a tmux bootstrap session and launch selected provider CLIs."""
        targets = self.prepare_targets(
            config,
            agent_names=agent_names,
            include_disabled=include_disabled,
        )
        bootstrap_session = session_name or f"{config.session_name}-bootstrap"
        manager = TmuxSessionManager(session_name=bootstrap_session)
        if manager.session_exists():
            if not force:
                raise ProviderBootstrapError(
                    f"tmux session '{bootstrap_session}' already exists. "
                    "Use --force to recreate it."
                )
            manager.destroy()

        launch_contexts = {target.agent_name: target for target in targets}
        manager.create_session(
            [target.spec for target in targets],
            launch_contexts=launch_contexts,
        )

        commands: dict[str, str] = {}
        for target in targets:
            pane = manager.get_pane(target.agent_name)
            if pane is None:
                raise ProviderBootstrapError(
                    f"No tmux pane was created for agent '{target.agent_name}'"
                )
            command = build_provider_command(target.spec, target.env_overrides)
            commands[target.agent_name] = command
            pane.send_text(command)

        return ProviderBootstrapResult(
            session_name=bootstrap_session,
            targets=targets,
            commands=commands,
        )

    def launch_session(
        self,
        config: TrinityConfig,
        agent_names: list[str] | None = None,
        include_disabled: bool = False,
        session_name: str | None = None,
        force: bool = False,
    ) -> ProviderBootstrapResult:
        """Backward-compatible legacy tmux bootstrap entry point."""
        return self.launch_legacy_tmux_session(
            config,
            agent_names=agent_names,
            include_disabled=include_disabled,
            session_name=session_name,
            force=force,
        )


def build_provider_argv(spec: AgentSpec) -> tuple[str, ...]:
    """Build argv used to launch one provider CLI."""
    args: list[str] = [spec.cli_command]
    if spec.model and spec.model != "default":
        args.extend(["--model", spec.model])
    args.extend(str(arg) for arg in spec.extra_args)
    return tuple(args)


def render_provider_command(spec: AgentSpec) -> str:
    """Render a provider command for display only."""
    return render_command(build_provider_argv(spec))


def build_provider_command(spec: AgentSpec, env_overrides: dict[str, str]) -> str:
    """Build the legacy shell command used to launch one provider CLI in tmux."""
    command = " ".join(shlex.quote(str(arg)) for arg in build_provider_argv(spec))
    if not env_overrides:
        return command

    env_parts = [
        f"{key}={shlex.quote(str(value))}"
        for key, value in sorted(env_overrides.items())
    ]
    return " ".join(["env", *env_parts, command])


def attach_to_bootstrap_session(session_name: str) -> int:
    """Attach the user to a bootstrap tmux session."""
    result = subprocess.run(["tmux", "attach-session", "-t", session_name])
    return result.returncode
