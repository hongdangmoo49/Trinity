"""Provider readiness detection for interactive CLI sessions."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence

from trinity.agents.base import AgentWrapper
from trinity.models import Provider
from trinity.platform.process import CommandSpec, ProcessRunner
from trinity.providers.model_discovery import (
    ModelChoiceSource,
    ProviderModelChoice,
    discover_provider_models,
)
from trinity.providers.permissions import ProviderPermissionPolicy
from trinity.providers.policy import InvocationAccess


class ProviderState(str, Enum):
    """Classified provider state before a deliberation request is sent."""

    READY = "ready"
    AUTH_REQUIRED = "auth_required"
    MODEL_LOADING = "model_loading"
    WORKSPACE_TRUST_REQUIRED = "workspace_trust_required"
    CLI_BANNER_ONLY = "cli_banner_only"
    PROMPT_NOT_SENT = "prompt_not_sent"
    PROCESS_DEAD = "process_dead"
    CWD_INACCESSIBLE = "cwd_inaccessible"
    CLI_NOT_FOUND = "cli_not_found"
    CLI_PROBE_FAILED = "cli_probe_failed"
    MODEL_UNAVAILABLE = "model_unavailable"
    PERMISSION_PLAN_INVALID = "permission_plan_invalid"
    UNKNOWN_NOT_READY = "unknown_not_ready"


@dataclass(frozen=True)
class ReadinessResult:
    """Readiness check result for one configured agent."""

    agent_name: str
    provider: Provider
    ready: bool
    state: ProviderState
    reason: str
    action_hint: str
    excerpt: str = ""


@dataclass(frozen=True)
class OneShotPreflightResult(ReadinessResult):
    """Runtime preflight result for a one-shot provider invocation."""

    cwd: str = ""
    cli_command: str = ""
    resolved_executable: str = ""
    probe_command: tuple[str, ...] = ()
    probe_returncode: int | None = None
    model: str = "default"
    model_source: ModelChoiceSource | str = "unavailable"
    model_source_reason: str = ""
    discovered_models: tuple[str, ...] = ()
    access: InvocationAccess = InvocationAccess.READ_ONLY
    permission_args: tuple[str, ...] = ()
    permission_extra_args: tuple[str, ...] = ()
    permission_diagnostics: tuple[str, ...] = field(default_factory=tuple)


_PROMPT_RE = re.compile(
    r"^\s*(?:[>$❯›]|trinity>|claude>|codex>|agy>)\s*$"
)


def _normalize_lines(lines: Iterable[str], limit: int = 40) -> list[str]:
    normalized = [str(line).rstrip() for line in lines]
    return [line for line in normalized if line.strip()][-limit:]


def _excerpt(lines: Iterable[str], limit: int = 8) -> str:
    selected = _normalize_lines(lines, limit=limit)
    return "\n".join(selected)


def _contains(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE | re.MULTILINE) for pattern in patterns)


def _has_ready_prompt(lines: list[str], provider: Provider) -> bool:
    tail = lines[-8:]
    tail_text = "\n".join(tail).lower()
    if _contains(tail_text, _READY_PROMPT_PATTERNS[provider]):
        return True
    return any(_PROMPT_RE.match(line.strip()) for line in tail)


def _provider_label(provider: Provider) -> str:
    return provider.value


class OneShotProviderPreflight:
    """Validate one-shot provider runtime prerequisites before first use."""

    def __init__(
        self,
        timeout_seconds: float = 3.0,
        *,
        runner: ProcessRunner | None = None,
        permission_policy: ProviderPermissionPolicy | None = None,
        use_model_cache: bool = True,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.runner = runner or ProcessRunner()
        self.permission_policy = permission_policy or ProviderPermissionPolicy()
        self.use_model_cache = use_model_cache

    def check_all(
        self,
        agents: dict[str, AgentWrapper],
        *,
        access: InvocationAccess = InvocationAccess.READ_ONLY,
    ) -> dict[str, OneShotPreflightResult]:
        """Check all configured one-shot agents."""
        return {
            name: self.check(agent, access=access)
            for name, agent in agents.items()
        }

    def check(
        self,
        agent: AgentWrapper,
        *,
        access: InvocationAccess = InvocationAccess.READ_ONLY,
    ) -> OneShotPreflightResult:
        """Validate cwd, CLI probe, model selection, and permission plan."""
        spec = agent.spec
        provider = spec.provider
        cwd = Path(getattr(agent, "launch_cwd", None) or Path.cwd())
        env = dict(getattr(agent, "env_overrides", {}) or {})
        model = (spec.model or "default").strip() or "default"
        cli_command = (spec.cli_command or "").strip()

        cwd_error = self._validate_cwd(cwd)
        if cwd_error:
            return self._result(
                agent,
                state=ProviderState.CWD_INACCESSIBLE,
                reason=cwd_error,
                cwd=cwd,
                cli_command=cli_command,
                model=model,
                access=access,
            )

        resolved = self._resolve_executable(cli_command, cwd=cwd, env=env)
        if not resolved:
            return self._result(
                agent,
                state=ProviderState.CLI_NOT_FOUND,
                reason=(
                    f"{provider.value} CLI command {cli_command!r} was not found"
                    if cli_command
                    else f"{provider.value} CLI command is empty"
                ),
                cwd=cwd,
                cli_command=cli_command,
                model=model,
                access=access,
            )

        probe_result = self._probe_cli(
            provider=provider,
            cli_command=cli_command,
            cwd=cwd,
            env=env,
        )
        if probe_result is not None:
            state, reason, probe_command, returncode, excerpt = probe_result
            return self._result(
                agent,
                state=state,
                reason=reason,
                cwd=cwd,
                cli_command=cli_command,
                resolved_executable=resolved,
                probe_command=probe_command,
                probe_returncode=returncode,
                model=model,
                access=access,
                excerpt=excerpt,
            )

        permission = self._permission_plan(agent, cwd=cwd, access=access)
        if isinstance(permission, OneShotPreflightResult):
            return permission

        choices, model_source, source_reason, discoverable = self._discover_models(
            provider=provider,
            cli_command=cli_command,
            cwd=cwd,
            env=env,
        )
        discovered = tuple(
            choice.model
            for choice in choices
            if choice.model and choice.model != "default"
        )
        if discoverable and model != "default":
            available = {choice.model for choice in choices}
            if model not in available:
                return self._result(
                    agent,
                    state=ProviderState.MODEL_UNAVAILABLE,
                    reason=(
                        f"{provider.value} model {model!r} was not found in "
                        f"discoverable {model_source} choices"
                    ),
                    cwd=cwd,
                    cli_command=cli_command,
                    resolved_executable=resolved,
                    probe_command=self._probe_argv(cli_command, provider),
                    probe_returncode=0,
                    model=model,
                    model_source=model_source,
                    model_source_reason=source_reason,
                    discovered_models=discovered,
                    access=access,
                    permission_args=permission.args,
                    permission_extra_args=permission.extra_args,
                    permission_diagnostics=permission.diagnostics,
                    excerpt=self._model_excerpt(discovered),
                )

        return self._result(
            agent,
            state=ProviderState.READY,
            reason=f"{provider.value} one-shot preflight passed",
            cwd=cwd,
            cli_command=cli_command,
            resolved_executable=resolved,
            probe_command=self._probe_argv(cli_command, provider),
            probe_returncode=0,
            model=model,
            model_source=model_source,
            model_source_reason=source_reason,
            discovered_models=discovered,
            access=access,
            permission_args=permission.args,
            permission_extra_args=permission.extra_args,
            permission_diagnostics=permission.diagnostics,
        )

    def _permission_plan(
        self,
        agent: AgentWrapper,
        *,
        cwd: Path,
        access: InvocationAccess,
    ):
        spec = agent.spec
        try:
            return self.permission_policy.plan(
                provider=spec.provider,
                access=access,
                cwd=cwd,
                extra_args=tuple(spec.extra_args),
            )
        except Exception as exc:
            return self._result(
                agent,
                state=ProviderState.PERMISSION_PLAN_INVALID,
                reason=f"could not build provider permission plan: {exc}",
                cwd=cwd,
                cli_command=spec.cli_command,
                model=(spec.model or "default").strip() or "default",
                access=access,
            )

    def _discover_models(
        self,
        *,
        provider: Provider,
        cli_command: str,
        cwd: Path,
        env: dict[str, str],
    ) -> tuple[tuple[ProviderModelChoice, ...], str, str, bool]:
        def run(argv: Sequence[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
            return self.runner.run(
                CommandSpec(
                    argv=tuple(argv),
                    cwd=cwd,
                    env=env,
                    timeout_seconds=timeout_seconds,
                )
            )

        try:
            choices = tuple(
                discover_provider_models(
                    provider,
                    cli_command,
                    timeout_seconds=self.timeout_seconds,
                    use_cache=self.use_model_cache,
                    runner=run,
                )
            )
        except Exception as exc:
            return (), "unavailable", f"model discovery failed: {exc}", False

        first_with_source = next((choice for choice in choices if choice.source), None)
        model_source = first_with_source.source if first_with_source else "unavailable"
        source_reason = (
            first_with_source.source_reason
            if first_with_source and first_with_source.source_reason
            else ""
        )
        discoverable = any(
            choice.source in {"cli-live", "cli-bundled"}
            for choice in choices
            if choice.model != "default"
        )
        if discoverable:
            first_live = next(
                choice
                for choice in choices
                if choice.model != "default" and choice.source in {"cli-live", "cli-bundled"}
            )
            model_source = first_live.source
            source_reason = first_live.source_reason
        return choices, model_source, source_reason, discoverable

    def _probe_cli(
        self,
        *,
        provider: Provider,
        cli_command: str,
        cwd: Path,
        env: dict[str, str],
    ) -> tuple[ProviderState, str, tuple[str, ...], int | None, str] | None:
        argv = self._probe_argv(cli_command, provider)
        try:
            completed = self.runner.run(
                CommandSpec(
                    argv=argv,
                    cwd=cwd,
                    env=env,
                    timeout_seconds=self.timeout_seconds,
                )
            )
        except FileNotFoundError:
            return (
                ProviderState.CLI_NOT_FOUND,
                f"{provider.value} CLI command {cli_command!r} was not found",
                argv,
                None,
                "",
            )
        except subprocess.TimeoutExpired:
            return (
                ProviderState.CLI_PROBE_FAILED,
                f"{provider.value} CLI probe timed out after {self.timeout_seconds}s",
                argv,
                None,
                "",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return (
                ProviderState.CLI_PROBE_FAILED,
                f"{provider.value} CLI probe failed: {exc}",
                argv,
                None,
                "",
            )

        if completed.returncode != 0:
            return (
                ProviderState.CLI_PROBE_FAILED,
                (
                    f"{provider.value} CLI probe failed with exit code "
                    f"{completed.returncode}"
                ),
                argv,
                completed.returncode,
                self._completed_excerpt(completed),
            )
        return None

    @staticmethod
    def _probe_argv(cli_command: str, provider: Provider) -> tuple[str, ...]:
        if provider in {
            Provider.CLAUDE_CODE,
            Provider.CODEX,
            Provider.ANTIGRAVITY_CLI,
        }:
            return (cli_command, "--version")
        return (cli_command, "--version")

    @staticmethod
    def _validate_cwd(cwd: Path) -> str:
        if not cwd.exists():
            return f"provider cwd does not exist: {cwd}"
        if not cwd.is_dir():
            return f"provider cwd is not a directory: {cwd}"
        try:
            with os.scandir(cwd) as entries:
                next(entries, None)
        except OSError as exc:
            return f"provider cwd is not accessible: {exc}"
        return ""

    @staticmethod
    def _resolve_executable(
        cli_command: str,
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> str:
        command = (cli_command or "").strip()
        if not command:
            return ""

        separators = [os.sep]
        if os.altsep:
            separators.append(os.altsep)
        has_path_separator = any(separator in command for separator in separators)
        if has_path_separator:
            path = Path(command).expanduser()
            candidate = path if path.is_absolute() else cwd / path
            return str(candidate) if candidate.exists() and candidate.is_file() else ""

        path_value = env.get("PATH")
        if path_value is None:
            path_value = os.environ.get("PATH")
        resolved = shutil.which(command, path=path_value)
        return resolved or ""

    @staticmethod
    def _completed_excerpt(completed: subprocess.CompletedProcess[str]) -> str:
        text = "\n".join(
            part
            for part in (completed.stdout or "", completed.stderr or "")
            if part.strip()
        )
        return _excerpt(text.splitlines())

    @staticmethod
    def _model_excerpt(models: tuple[str, ...]) -> str:
        if not models:
            return "No non-default models were discovered."
        visible = ", ".join(models[:12])
        if len(models) > 12:
            visible = f"{visible}, ... (+{len(models) - 12} more)"
        return f"Discovered models: {visible}"

    def _result(
        self,
        agent: AgentWrapper,
        *,
        state: ProviderState,
        reason: str,
        cwd: Path,
        cli_command: str,
        resolved_executable: str = "",
        probe_command: tuple[str, ...] = (),
        probe_returncode: int | None = None,
        model: str = "default",
        model_source: ModelChoiceSource | str = "unavailable",
        model_source_reason: str = "",
        discovered_models: tuple[str, ...] = (),
        access: InvocationAccess = InvocationAccess.READ_ONLY,
        permission_args: tuple[str, ...] = (),
        permission_extra_args: tuple[str, ...] = (),
        permission_diagnostics: tuple[str, ...] = (),
        excerpt: str = "",
    ) -> OneShotPreflightResult:
        return OneShotPreflightResult(
            agent_name=agent.name,
            provider=agent.spec.provider,
            ready=state == ProviderState.READY,
            state=state,
            reason=reason,
            action_hint=_action_hint(agent.spec.provider, state),
            excerpt=excerpt,
            cwd=str(cwd),
            cli_command=cli_command,
            resolved_executable=resolved_executable,
            probe_command=probe_command,
            probe_returncode=probe_returncode,
            model=model,
            model_source=model_source,
            model_source_reason=model_source_reason,
            discovered_models=discovered_models,
            access=access,
            permission_args=permission_args,
            permission_extra_args=permission_extra_args,
            permission_diagnostics=tuple(permission_diagnostics),
        )


def _action_hint(provider: Provider, state: ProviderState) -> str:
    provider_name = _provider_label(provider)
    if state == ProviderState.READY:
        return ""
    if state == ProviderState.CWD_INACCESSIBLE:
        return (
            "Choose an existing target workspace directory that Trinity can list, "
            "then retry."
        )
    if state == ProviderState.CLI_NOT_FOUND:
        return (
            f"Install the {provider_name} CLI or update the agent cli_command "
            "to the executable path."
        )
    if state == ProviderState.CLI_PROBE_FAILED:
        return (
            f"Run the configured {provider_name} CLI with `--version` in your "
            "normal shell and fix the reported runtime error."
        )
    if state == ProviderState.MODEL_UNAVAILABLE:
        return (
            "Choose an available model for this provider, or use `default` to "
            "let the provider CLI choose."
        )
    if state == ProviderState.PERMISSION_PLAN_INVALID:
        return (
            "Review the provider extra_args and Trinity permission policy for "
            "this invocation access level."
        )
    if state == ProviderState.AUTH_REQUIRED:
        if provider == Provider.CLAUDE_CODE:
            return (
                "Run `claude` in your normal shell and complete login. "
                "Use `trinity bootstrap --agents claude` only for isolated mode."
            )
        if provider == Provider.CODEX:
            return (
                "Run `codex login` or `codex` in your normal shell and complete "
                "authentication. Use `trinity bootstrap --agents codex` only "
                "for isolated mode."
            )
        if provider == Provider.ANTIGRAVITY_CLI:
            return (
                "Run `agy` in your normal shell and complete auth/workspace trust. "
                "Trinity uses your existing Antigravity auth through `agy --print` "
                "in one-shot mode."
            )
    if state == ProviderState.MODEL_LOADING:
        return f"Wait for {provider_name} model initialization to finish, then retry."
    if state == ProviderState.WORKSPACE_TRUST_REQUIRED:
        return (
            "Run the provider CLI in your normal shell and accept the workspace "
            "trust prompt. Use `trinity bootstrap` only for isolated mode."
        )
    if state == ProviderState.CLI_BANNER_ONLY:
        return f"Wait until {provider_name} shows an input prompt, then retry."
    if state == ProviderState.PROMPT_NOT_SENT:
        return f"Wait until {provider_name} reaches its input prompt, then retry."
    if state == ProviderState.PROCESS_DEAD:
        return f"Restart the {provider_name} CLI session and retry."
    return f"Inspect the {provider_name} pane, resolve the blocking prompt, then retry."


class ProviderReadinessGate:
    """Classify provider pane state before deliberation starts."""

    def __init__(self, timeout: float = 5.0, poll_interval: float = 0.25):
        self.timeout = timeout
        self.poll_interval = poll_interval

    def check(self, agent: AgentWrapper) -> ReadinessResult:
        """Check one agent once without waiting."""
        return self.classify_agent(agent)

    def wait_until_ready(
        self,
        agent: AgentWrapper,
        timeout: float | None = None,
    ) -> ReadinessResult:
        """Poll one agent until ready or a terminal not-ready state is found."""
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        last = self.classify_agent(agent)
        while time.monotonic() < deadline:
            last = self.classify_agent(agent)
            if last.ready or last.state in {
                ProviderState.AUTH_REQUIRED,
                ProviderState.WORKSPACE_TRUST_REQUIRED,
                ProviderState.PROCESS_DEAD,
            }:
                return last
            time.sleep(self.poll_interval)
        return last

    def check_all(
        self,
        agents: dict[str, AgentWrapper],
        timeout: float | None = None,
    ) -> dict[str, ReadinessResult]:
        """Check every agent and return results keyed by agent name."""
        return {
            name: self.wait_until_ready(agent, timeout=timeout)
            for name, agent in agents.items()
        }

    def classify_agent(self, agent: AgentWrapper) -> ReadinessResult:
        """Capture an agent pane if present and classify the provider state."""
        pane = getattr(agent, "pane", None) or getattr(agent, "_pane", None)
        if pane is None:
            return ReadinessResult(
                agent_name=agent.name,
                provider=agent.spec.provider,
                ready=True,
                state=ProviderState.READY,
                reason="print-mode agent does not require pane readiness gating",
                action_hint="",
            )

        try:
            alive = pane.is_alive()
        except Exception:
            alive = False
        if not alive:
            return self._result(
                agent.name,
                agent.spec.provider,
                ProviderState.PROCESS_DEAD,
                "provider pane is not alive",
                [],
            )

        try:
            captured = pane.capture(lines=-80)
        except Exception as exc:
            return self._result(
                agent.name,
                agent.spec.provider,
                ProviderState.UNKNOWN_NOT_READY,
                f"could not capture provider pane: {exc}",
                [],
            )

        lines = captured.splitlines() if isinstance(captured, str) else list(captured)
        return self.classify_pane_state(
            lines,
            provider=agent.spec.provider,
            agent_name=agent.name,
        )

    def classify_pane_state(
        self,
        lines: Iterable[str],
        provider: Provider,
        agent_name: str = "",
    ) -> ReadinessResult:
        """Classify captured pane lines for a provider."""
        normalized = _normalize_lines(lines)
        text = "\n".join(normalized).lower()
        name = agent_name or provider.value

        if not normalized:
            return self._result(
                name,
                provider,
                ProviderState.PROMPT_NOT_SENT,
                "provider pane has no visible prompt yet",
                normalized,
            )

        state = self._classify(provider, normalized, text)
        reason = self._reason(provider, state)
        return self._result(name, provider, state, reason, normalized)

    def _classify(
        self,
        provider: Provider,
        lines: list[str],
        text: str,
    ) -> ProviderState:
        prompt_ready = _has_ready_prompt(lines, provider)
        if prompt_ready:
            return ProviderState.READY
        if _contains(text, _PROCESS_DEAD_PATTERNS):
            return ProviderState.PROCESS_DEAD
        if _contains(text, _WORKSPACE_TRUST_PATTERNS):
            return ProviderState.WORKSPACE_TRUST_REQUIRED
        if _contains(text, _AUTH_PATTERNS[provider]):
            return ProviderState.AUTH_REQUIRED
        if _contains(text, _MODEL_LOADING_PATTERNS[provider]):
            return ProviderState.MODEL_LOADING

        banner_only = _contains(text, _BANNER_PATTERNS[provider])
        if banner_only:
            return ProviderState.CLI_BANNER_ONLY
        return ProviderState.UNKNOWN_NOT_READY

    def _reason(self, provider: Provider, state: ProviderState) -> str:
        label = _provider_label(provider)
        reasons = {
            ProviderState.READY: f"{label} is ready for input",
            ProviderState.AUTH_REQUIRED: f"{label} requires authentication",
            ProviderState.MODEL_LOADING: f"{label} is still loading a model",
            ProviderState.WORKSPACE_TRUST_REQUIRED: f"{label} requires workspace trust",
            ProviderState.CLI_BANNER_ONLY: f"{label} only shows the CLI banner",
            ProviderState.PROMPT_NOT_SENT: f"{label} prompt is not visible yet",
            ProviderState.PROCESS_DEAD: f"{label} process is not running",
            ProviderState.UNKNOWN_NOT_READY: f"{label} is not ready",
        }
        return reasons[state]

    def _result(
        self,
        agent_name: str,
        provider: Provider,
        state: ProviderState,
        reason: str,
        lines: Iterable[str],
    ) -> ReadinessResult:
        return ReadinessResult(
            agent_name=agent_name,
            provider=provider,
            ready=state == ProviderState.READY,
            state=state,
            reason=reason,
            action_hint=_action_hint(provider, state),
            excerpt=_excerpt(lines),
        )


_COMMON_AUTH_PATTERNS = (
    r"\blog\s*in\b",
    r"\blogin\s+required\b",
    r"\bauth\s+login\b",
    r"\bauth(?:entication)?\s+required\b",
    r"\brequires\s+authentication\b",
    r"\bnot\s+authenticated\b",
    r"\bauthorization\s+code\b",
    r"\bsign\s*in\b",
    r"\boauth\b",
    r"\binvalid\s+code\b",
    r"\bapi\s+key\b.*(?:missing|required|not\s+set)",
)

_AUTH_PATTERNS: dict[Provider, tuple[str, ...]] = {
    Provider.CLAUDE_CODE: (
        *_COMMON_AUTH_PATTERNS,
        r"claude\.ai/(?:login|oauth|auth)",
        r"complete\s+authentication\s+in\s+your\s+browser",
        r"select\s+login\s+method",
        r"claude\s+account\s+with\s+subscription",
        r"anthropic\s+console\s+account",
    ),
    Provider.CODEX: (
        *_COMMON_AUTH_PATTERNS,
        r"\bcodex\s+login\b",
        r"openai\s+api\s+key",
    ),
    Provider.ANTIGRAVITY_CLI: (
        *_COMMON_AUTH_PATTERNS,
        r"\bagy\b.*\bauth\b",
        r"antigravity\b.*\bauth\b",
        r"google\s+account",
        r"workspace\s+trust",
    ),
}

_MODEL_LOADING_PATTERNS: dict[Provider, tuple[str, ...]] = {
    Provider.CLAUDE_CODE: (
        r"\bloading\b.*\bmodel\b",
        r"\binitializing\b.*\bmodel\b",
    ),
    Provider.CODEX: (
        r"\bloading\b.*\bmodel\b",
        r"\bmodel\b.*\bloading\b",
    ),
    Provider.ANTIGRAVITY_CLI: (
        r"\bloading\b.*\bmodel\b",
        r"\binitializing\b.*\bantigravity\b",
        r"\binitializing\b.*\bagy\b",
    ),
}

_READY_PROMPT_PATTERNS: dict[Provider, tuple[str, ...]] = {
    Provider.CLAUDE_CODE: (
        r"\btype\s+your\s+message\b",
    ),
    Provider.CODEX: (
        r"^\s*›\s+",
        r"\buse\s+/skills\b",
        r"\brun\s+/review\b",
    ),
    Provider.ANTIGRAVITY_CLI: (
        r"\btype\s+your\s+message\b",
        r"^\s*›\s+",
    ),
}

_BANNER_PATTERNS: dict[Provider, tuple[str, ...]] = {
    Provider.CLAUDE_CODE: (
        r"\bclaude\s+code\b",
        r"\bwelcome\s+to\s+claude\b",
    ),
    Provider.CODEX: (
        r"\bcodex\b",
        r"/model\s+to\s+change",
        r"/help\s+for\s+commands",
    ),
    Provider.ANTIGRAVITY_CLI: (
        r"\bantigravity\b",
        r"\bagy\b",
        r"/help\s+for\s+commands",
    ),
}

_WORKSPACE_TRUST_PATTERNS = (
    r"\bworkspace\s+trust\b",
    r"\btrust\s+this\s+workspace\b",
    r"\btrust\b.*\b(?:file|folder|workspace)s?\b",
    r"\bdo\s+you\s+trust\b.*\bworkspace\b",
    r"\bdo\s+you\s+trust\b.*\b(?:file|folder)s?\b",
    r"\btrusted\s+workspace\b",
)

_PROCESS_DEAD_PATTERNS = (
    r"\bprocess\s+exited\b",
    r"\bexited\s+with\s+code\b",
    r"\bno\s+such\s+process\b",
    r"\[exited\]",
)
