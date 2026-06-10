"""One-shot provider invocation contracts and CLI invokers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

try:  # pragma: no cover - Python 3.10 compatibility path.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from trinity.models import ContextUsage, Provider, ResponseStatus
from trinity.platform.process import CommandSpec, ProcessRunner
from trinity.providers.policy import ExecutionAuthority, InvocationAccess


@dataclass(frozen=True)
class PromptRequest:
    """Provider-agnostic request for one model turn."""

    agent_name: str
    provider: Provider
    cli_command: str
    prompt: str
    cwd: Path
    timeout_seconds: float = 300.0
    request_id: str = ""
    role_prompt: str = ""
    context_prompt: str = ""
    round_num: int = 0
    env: dict[str, str] = field(default_factory=dict)
    model: str = "default"
    extra_args: tuple[str, ...] = ()
    access: InvocationAccess = InvocationAccess.READ_ONLY
    provider_session_id: str = ""
    continuity_enabled: bool = False
    resource_prompt: str = ""
    resource_projections: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class ProviderTurnResult:
    """Normalized result returned by one provider invocation."""

    agent_name: str
    content: str
    raw_output: str
    status: ResponseStatus
    elapsed_seconds: float
    usage: ContextUsage | None = None
    diagnostics: list[str] = field(default_factory=list)
    execution_authority: ExecutionAuthority = ExecutionAuthority.PROVIDER_MANAGED
    tool_activity_summary: list[str] = field(default_factory=list)
    artifact_paths: list[Path] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ProviderInvoker(Protocol):
    """Protocol implemented by one-shot provider invokers."""

    async def invoke(self, request: PromptRequest) -> ProviderTurnResult:
        """Run one provider turn and return a normalized result."""
        ...


class CliProviderInvoker:
    """Base class for provider CLI one-shot invokers."""

    execution_authority = ExecutionAuthority.PROVIDER_MANAGED

    def __init__(self, runner: ProcessRunner | None = None):
        self.runner = runner or ProcessRunner()

    async def invoke(self, request: PromptRequest) -> ProviderTurnResult:
        """Run the provider command in a subprocess."""
        command = self.build_command(request)
        started = time.time()
        try:
            completed = await asyncio.to_thread(
                self._run_subprocess,
                command,
                request,
            )
        except subprocess.TimeoutExpired:
            return ProviderTurnResult(
                agent_name=request.agent_name,
                content=f"[Timeout after {request.timeout_seconds}s]",
                raw_output="",
                status=ResponseStatus.TIMEOUT,
                elapsed_seconds=time.time() - started,
                diagnostics=["Provider invocation timed out."],
                execution_authority=self.execution_authority,
                metadata={"command": command},
            )

        elapsed = time.time() - started
        return self.parse_completed_process(request, command, completed, elapsed)

    def build_command(self, request: PromptRequest) -> list[str]:
        """Build argv for this provider invocation."""
        raise NotImplementedError

    def stdin_text(self, request: PromptRequest) -> str | None:
        """Return stdin payload for providers that read prompts from stdin."""
        return None

    def parse_completed_process(
        self,
        request: PromptRequest,
        command: list[str],
        completed: subprocess.CompletedProcess[str],
        elapsed_seconds: float,
    ) -> ProviderTurnResult:
        """Parse provider stdout/stderr into a normalized result."""
        raise NotImplementedError

    def _run_subprocess(
        self,
        command: list[str],
        request: PromptRequest,
    ) -> subprocess.CompletedProcess[str]:
        return self.runner.run(
            CommandSpec(
                argv=tuple(command),
                cwd=request.cwd,
                env=request.env,
                timeout_seconds=request.timeout_seconds,
                input_text=self.stdin_text(request),
            )
        )

    @staticmethod
    def _model_args(request: PromptRequest) -> list[str]:
        model = (request.model or "").strip()
        if not model or model == "default":
            return []
        return ["--model", model]

    @staticmethod
    def _render_prompt(request: PromptRequest, include_role: bool = True) -> str:
        parts: list[str] = []
        if include_role and request.role_prompt:
            parts.append(f"[System Role]\n{request.role_prompt}")
        if request.context_prompt:
            parts.append(f"[Context]\n{request.context_prompt}")
        if request.resource_prompt:
            parts.append(request.resource_prompt)
        parts.append(request.prompt)
        return "\n\n".join(parts)

    @staticmethod
    def _failure_status(text: str) -> ResponseStatus:
        lowered = text.lower()
        auth_terms = (
            "auth",
            "authentication",
            "login",
            "log in",
            "sign in",
            "oauth",
            "api key",
        )
        if any(term in lowered for term in auth_terms):
            return ResponseStatus.AUTH_REQUIRED
        if not text.strip():
            return ResponseStatus.EMPTY
        return ResponseStatus.INVALID


def _provider_session_metadata(
    request: PromptRequest,
    *,
    provider_session_id: str,
    session_kind: str,
    resolved_model: str = "",
    diagnostics: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return a normalized provider session observation."""
    session_id = str(provider_session_id or "").strip()
    if not session_id:
        return None

    model = str(resolved_model or request.model or "").strip()
    cwd_hash = hashlib.sha1(str(request.cwd).encode("utf-8")).hexdigest()[:12]
    lane = "read-only" if request.access == InvocationAccess.READ_ONLY else "workspace-write"
    session_key = ":".join(
        [
            request.provider.value,
            request.agent_name,
            lane,
            request.access.value,
            cwd_hash,
            model or "default",
        ]
    )
    return {
        "provider": request.provider.value,
        "agent_name": request.agent_name,
        "session_key": session_key,
        "provider_session_id": session_id,
        "session_kind": session_kind,
        "lane": lane,
        "access": request.access.value,
        "cwd": str(request.cwd),
        "configured_model": request.model,
        "resolved_model": model,
        "last_request_id": request.request_id,
        "last_observed_at": time.time(),
        "diagnostics": list(diagnostics or []),
    }


def _runtime_model_metadata(
    request: PromptRequest,
    *,
    actual_model: str = "",
    model_label: str = "",
    context_window: int = 0,
    max_output_tokens: int = 0,
    budget_source: str = "unsupported",
    confidence: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a normalized runtime model observation."""
    actual = str(actual_model or "").strip()
    label = str(model_label or "").strip()
    if not actual and not label and context_window <= 0:
        return None
    return {
        "provider": request.provider.value,
        "agent_name": request.agent_name,
        "configured_model": request.model,
        "actual_model": actual,
        "model_label": label,
        "context_window": max(0, int(context_window or 0)),
        "max_output_tokens": max(0, int(max_output_tokens or 0)),
        "budget_source": budget_source,
        "confidence": confidence,
        "observed_at": time.time(),
        "metadata": dict(metadata or {}),
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class ClaudePrintInvoker(CliProviderInvoker):
    """Invoke Claude Code with `claude -p --output-format json`."""

    def build_command(self, request: PromptRequest) -> list[str]:
        command = [
            request.cli_command,
            *self._model_args(request),
        ]
        if request.provider_session_id:
            command.extend(["--resume", request.provider_session_id])
        command.extend(["-p", "--output-format", "json"])
        if request.role_prompt:
            command.extend(["--append-system-prompt", request.role_prompt])
        command.extend(request.extra_args)
        command.append(self._render_prompt(request, include_role=False))
        return command

    def parse_completed_process(
        self,
        request: PromptRequest,
        command: list[str],
        completed: subprocess.CompletedProcess[str],
        elapsed_seconds: float,
    ) -> ProviderTurnResult:
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        raw = stdout if not stderr else f"{stdout}\n{stderr}".strip()
        diagnostics = [stderr.strip()] if stderr.strip() else []

        if completed.returncode != 0:
            status = self._failure_status(raw)
            return ProviderTurnResult(
                agent_name=request.agent_name,
                content=f"[Error: exit code {completed.returncode}]",
                raw_output=raw,
                status=status,
                elapsed_seconds=elapsed_seconds,
                diagnostics=diagnostics,
                execution_authority=self.execution_authority,
                metadata={"command": command, "returncode": completed.returncode},
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            content = stdout.strip()
            status = ResponseStatus.OK if content else ResponseStatus.EMPTY
            return ProviderTurnResult(
                agent_name=request.agent_name,
                content=content,
                raw_output=raw,
                status=status,
                elapsed_seconds=elapsed_seconds,
                diagnostics=diagnostics,
                execution_authority=self.execution_authority,
                metadata={"command": command, "returncode": completed.returncode},
            )

        content = str(data.get("result") or data.get("content") or "").strip()
        usage = self._parse_usage(data.get("usage", {}), request)
        status = ResponseStatus.OK if content else ResponseStatus.EMPTY
        runtime_model = self._parse_runtime_model(data, request)
        actual_model = (
            str(runtime_model.get("actual_model", ""))
            if isinstance(runtime_model, dict)
            else str(data.get("model") or "")
        )
        provider_session = _provider_session_metadata(
            request,
            provider_session_id=str(data.get("session_id") or ""),
            session_kind="claude_session",
            resolved_model=actual_model,
        )
        return ProviderTurnResult(
            agent_name=request.agent_name,
            content=content,
            raw_output=raw,
            status=status,
            elapsed_seconds=elapsed_seconds,
            usage=usage,
            diagnostics=diagnostics,
            execution_authority=self.execution_authority,
            metadata={
                "command": command,
                "returncode": completed.returncode,
                "model": actual_model or data.get("model"),
                "session_id": data.get("session_id"),
                "provider_session": provider_session,
                "runtime_model": runtime_model,
            },
        )

    @staticmethod
    def _parse_usage(data: Any, request: PromptRequest) -> ContextUsage:
        usage_data = data if isinstance(data, dict) else {}
        used = int(usage_data.get("input_tokens", 0)) + int(
            usage_data.get("output_tokens", 0)
        )
        return ContextUsage(used=used, total=0)

    @staticmethod
    def _parse_runtime_model(
        data: dict[str, Any],
        request: PromptRequest,
    ) -> dict[str, Any] | None:
        model_usage = data.get("modelUsage")
        if not isinstance(model_usage, dict) or not model_usage:
            model = str(data.get("model") or "").strip()
            return _runtime_model_metadata(
                request,
                actual_model=model,
                budget_source="runtime_metadata" if model else "unsupported",
                confidence="medium" if model else "unknown",
            )

        actual_model = str(data.get("model") or "").strip()
        usage_item: dict[str, Any] = {}
        if actual_model and isinstance(model_usage.get(actual_model), dict):
            usage_item = dict(model_usage[actual_model])
        else:
            first_model, first_usage = next(iter(model_usage.items()))
            actual_model = actual_model or str(first_model)
            usage_item = dict(first_usage) if isinstance(first_usage, dict) else {}

        context_window = _safe_int(
            usage_item.get("contextWindow")
            or usage_item.get("context_window")
            or usage_item.get("maxInputTokens")
        )
        max_output_tokens = _safe_int(
            usage_item.get("maxOutputTokens")
            or usage_item.get("max_output_tokens")
        )
        return _runtime_model_metadata(
            request,
            actual_model=actual_model,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
            budget_source="runtime_metadata",
            confidence="high" if context_window else "medium",
            metadata={"modelUsage": model_usage},
        )


class CodexExecInvoker(CliProviderInvoker):
    """Invoke Codex with `codex exec --json` and parse JSONL events."""

    def build_command(self, request: PromptRequest) -> list[str]:
        if (
            request.continuity_enabled
            and request.provider_session_id
            and request.access == InvocationAccess.READ_ONLY
        ):
            command = [
                request.cli_command,
                "exec",
                "resume",
                request.provider_session_id,
                "--json",
                "--skip-git-repo-check",
                *self._model_args(request),
            ]
            command.extend(request.extra_args)
            command.append("-")
            return command

        command = [
            request.cli_command,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            request.access.value,
            "--cd",
            str(request.cwd),
            *self._model_args(request),
        ]
        if not request.continuity_enabled:
            command.insert(3, "--ephemeral")
        command.extend(request.extra_args)
        command.append("-")
        return command

    def stdin_text(self, request: PromptRequest) -> str | None:
        return self._render_prompt(request, include_role=True)

    def parse_completed_process(
        self,
        request: PromptRequest,
        command: list[str],
        completed: subprocess.CompletedProcess[str],
        elapsed_seconds: float,
    ) -> ProviderTurnResult:
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        raw = stdout if not stderr else f"{stdout}\n{stderr}".strip()
        diagnostics = [stderr.strip()] if stderr.strip() else []

        if completed.returncode != 0:
            status = self._failure_status(raw)
            return ProviderTurnResult(
                agent_name=request.agent_name,
                content=f"[Error: exit code {completed.returncode}]",
                raw_output=raw,
                status=status,
                elapsed_seconds=elapsed_seconds,
                diagnostics=diagnostics,
                execution_authority=self.execution_authority,
                metadata={"command": command, "returncode": completed.returncode},
            )

        parsed = parse_codex_jsonl(stdout)
        diagnostics.extend(parsed["diagnostics"])
        content = parsed["content"].strip()
        if not content and stdout.strip():
            content = stdout.strip()
        status = parsed["status"]
        if status == ResponseStatus.EMPTY and content:
            status = ResponseStatus.OK

        runtime_model = resolve_codex_runtime_model(request, parsed.get("model"))
        resolved_model = (
            str(runtime_model.get("actual_model", ""))
            if isinstance(runtime_model, dict)
            else str(parsed.get("model") or "")
        )
        provider_session = _provider_session_metadata(
            request,
            provider_session_id=str(parsed.get("thread_id") or ""),
            session_kind="codex_thread",
            resolved_model=resolved_model,
        )
        return ProviderTurnResult(
            agent_name=request.agent_name,
            content=content,
            raw_output=raw,
            status=status,
            elapsed_seconds=elapsed_seconds,
            usage=parsed["usage"],
            diagnostics=diagnostics,
            execution_authority=self.execution_authority,
            tool_activity_summary=parsed["tool_activity_summary"],
            metadata={
                "command": command,
                "returncode": completed.returncode,
                "thread_id": parsed.get("thread_id"),
                "model": resolved_model or parsed.get("model"),
                "provider_session": provider_session,
                "runtime_model": runtime_model,
            },
        )


def parse_codex_jsonl(stdout: str) -> dict[str, Any]:
    """Parse `codex exec --json` JSONL stdout into normalized fields."""
    content = ""
    usage: ContextUsage | None = None
    diagnostics: list[str] = []
    tool_counts: dict[str, int] = {}
    status = ResponseStatus.EMPTY
    thread_id = ""
    model = ""

    for line_no, line in enumerate(stdout.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            diagnostics.append(f"Invalid JSONL line {line_no}.")
            continue

        if not isinstance(event, dict):
            diagnostics.append(f"Ignored non-object JSONL line {line_no}.")
            continue

        event_type = str(event.get("type", ""))
        if event_type == "thread.started":
            thread_id = str(event.get("thread_id") or event.get("session_id") or "")
            if event.get("model") is not None:
                model = str(event.get("model") or "")
            continue
        if event.get("model") is not None:
            model = str(event.get("model") or "")
        if event_type == "error":
            diagnostics.append(str(event.get("message") or event))
            status = ResponseStatus.INVALID
            continue
        if event_type == "turn.failed":
            diagnostics.append(str(event.get("error") or event))
            status = ResponseStatus.INVALID
            continue
        if event_type == "turn.completed":
            usage = _parse_codex_usage(event.get("usage"))
            continue
        if not event_type.startswith("item."):
            continue

        item = event.get("item")
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", ""))
        if item_type:
            tool_counts[item_type] = tool_counts.get(item_type, 0) + 1
        if event_type == "item.completed" and item_type == "agent_message":
            content = str(item.get("text") or item.get("content") or "")
            status = ResponseStatus.OK if content.strip() else ResponseStatus.EMPTY

    summary = [
        f"{item_type}:{count}"
        for item_type, count in sorted(tool_counts.items())
        if item_type != "agent_message"
    ]
    return {
        "content": content,
        "usage": usage,
        "diagnostics": diagnostics,
        "status": status,
        "thread_id": thread_id,
        "model": model,
        "tool_activity_summary": summary,
    }


def _parse_codex_usage(data: Any) -> ContextUsage | None:
    if not isinstance(data, dict):
        return None
    input_tokens = int(data.get("input_tokens", 0))
    output_tokens = int(data.get("output_tokens", 0))
    reasoning_tokens = int(data.get("reasoning_output_tokens", 0))
    return ContextUsage(used=input_tokens + output_tokens + reasoning_tokens, total=0)


def resolve_codex_runtime_model(
    request: PromptRequest,
    observed_model: Any = "",
) -> dict[str, Any] | None:
    """Resolve Codex model/context metadata from JSONL or local CLI files."""
    model = str(observed_model or "").strip()
    source = "runtime_metadata" if model else "unsupported"
    confidence = "high" if model else "unknown"
    metadata: dict[str, Any] = {}

    if not model and request.model and request.model != "default":
        model = request.model
        source = "trinity_config"
        confidence = "medium"

    codex_home = _codex_home(request)
    config_model = ""
    config_path = codex_home / "config.toml"
    if not model and config_path.exists():
        try:
            config_data = tomllib.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(config_data, dict):
                config_model = str(config_data.get("model") or "").strip()
        except (OSError, tomllib.TOMLDecodeError):
            config_model = ""
        if config_model:
            model = config_model
            source = "local_cli_config"
            confidence = "medium-high"
            metadata["config_path"] = str(config_path)

    context_window = 0
    cache_path = codex_home / "models_cache.json"
    if model and cache_path.exists():
        try:
            cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
            model_data = _find_codex_model_cache(cache_data, model)
            if model_data:
                context_window = _safe_int(
                    model_data.get("context_window")
                    or model_data.get("max_context_window")
                    or model_data.get("contextWindow")
                )
                metadata["models_cache_path"] = str(cache_path)
                metadata["models_cache_entry"] = model_data
                if source in {"unsupported", "local_cli_config", "trinity_config"}:
                    source = "local_cli_cache" if context_window else source
                    confidence = "medium-high" if context_window else confidence
        except (json.JSONDecodeError, OSError):
            pass

    return _runtime_model_metadata(
        request,
        actual_model=model,
        context_window=context_window,
        budget_source=source,
        confidence=confidence,
        metadata=metadata,
    )


def _codex_home(request: PromptRequest) -> Path:
    home = request.env.get("CODEX_HOME") if isinstance(request.env, dict) else None
    if home:
        return Path(home).expanduser()
    return Path.home() / ".codex"


def _find_codex_model_cache(data: Any, model: str) -> dict[str, Any]:
    """Find a model entry in Codex's local model cache regardless of shape."""
    if isinstance(data, dict):
        direct = data.get(model)
        if isinstance(direct, dict):
            return direct
        models = data.get("models")
        if isinstance(models, dict) and isinstance(models.get(model), dict):
            return models[model]
        if isinstance(models, list):
            for item in models:
                if isinstance(item, dict) and str(item.get("id") or item.get("model")) == model:
                    return item
        for value in data.values():
            found = _find_codex_model_cache(value, model)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and str(item.get("id") or item.get("model")) == model:
                return item
            found = _find_codex_model_cache(item, model)
            if found:
                return found
    return {}


class AntigravityPrintInvoker(CliProviderInvoker):
    """Invoke Antigravity CLI with `agy --print` and parse plain stdout."""

    output_metadata = {
        "output_format": "plain-text",
        "machine_readable_output": False,
        "usage_source": "unsupported",
    }

    def build_command(self, request: PromptRequest) -> list[str]:
        timeout_seconds = max(1, math.ceil(request.timeout_seconds))
        command = [
            request.cli_command,
            *self._model_args(request),
            f"--print-timeout={timeout_seconds}s",
        ]
        if request.access == InvocationAccess.READ_ONLY:
            command.append("--sandbox")
        if request.provider_session_id:
            command.extend(["--conversation", request.provider_session_id])
        extra_args = list(request.extra_args)
        if not _extract_flag_value(extra_args, "--log-file"):
            log_path = _default_antigravity_log_path(request)
            if log_path:
                command.extend(["--log-file", str(log_path)])
        command.extend(extra_args)
        command.append("--print")
        command.append(self._render_prompt(request, include_role=True))
        return command

    def parse_completed_process(
        self,
        request: PromptRequest,
        command: list[str],
        completed: subprocess.CompletedProcess[str],
        elapsed_seconds: float,
    ) -> ProviderTurnResult:
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        raw = stdout if not stderr else f"{stdout}\n{stderr}".strip()
        diagnostics = [stderr.strip()] if stderr.strip() else []

        if completed.returncode != 0:
            status = self._failure_status(raw)
            return ProviderTurnResult(
                agent_name=request.agent_name,
                content=f"[Error: exit code {completed.returncode}]",
                raw_output=raw,
                status=status,
                elapsed_seconds=elapsed_seconds,
                diagnostics=diagnostics,
                execution_authority=self.execution_authority,
                metadata={
                    "command": command,
                    "returncode": completed.returncode,
                    **self.output_metadata,
                },
            )

        content = stdout.strip()
        status = ResponseStatus.OK if content else ResponseStatus.EMPTY
        if not content:
            content = "[Empty response from Antigravity CLI]"
            raw = raw or content
            diagnostics.append("empty_response: Antigravity CLI returned empty output.")
        log_metadata = parse_antigravity_log_file(_extract_flag_value(command, "--log-file"))
        diagnostics.extend(log_metadata.get("diagnostics", []))
        model_label = str(log_metadata.get("model_label") or "")
        runtime_model = _runtime_model_metadata(
            request,
            model_label=model_label,
            budget_source="provider_log" if model_label else "unsupported",
            confidence="medium" if model_label else "unknown",
            metadata={
                key: value
                for key, value in log_metadata.items()
                if key not in {"diagnostics"}
            },
        )
        provider_session = _provider_session_metadata(
            request,
            provider_session_id=str(log_metadata.get("conversation_id") or ""),
            session_kind="antigravity_conversation",
            resolved_model=model_label or request.model,
        )
        return ProviderTurnResult(
            agent_name=request.agent_name,
            content=content,
            raw_output=raw,
            status=status,
            elapsed_seconds=elapsed_seconds,
            diagnostics=diagnostics,
            execution_authority=self.execution_authority,
            metadata={
                "command": command,
                "returncode": completed.returncode,
                "conversation_id": log_metadata.get("conversation_id"),
                "model_label": model_label,
                "provider_session": provider_session,
                "runtime_model": runtime_model,
                **self.output_metadata,
            },
        )


def _extract_flag_value(command: list[str], flag: str) -> str:
    """Extract `--flag value` or `--flag=value` from an argv list."""
    for index, item in enumerate(command):
        text = str(item)
        if text == flag and index + 1 < len(command):
            return str(command[index + 1])
        prefix = f"{flag}="
        if text.startswith(prefix):
            return text[len(prefix):]
    return ""


def _default_antigravity_log_path(request: PromptRequest) -> Path | None:
    """Return a per-call Antigravity log path for metadata parsing."""
    try:
        log_dir = request.cwd / ".trinity" / "provider-sessions"
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    request_part = request.request_id.strip() if request.request_id else ""
    if not request_part:
        request_part = str(int(time.time() * 1000))
    safe_agent = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.agent_name).strip("-")
    safe_request = re.sub(r"[^A-Za-z0-9_.-]+", "-", request_part).strip("-")
    return log_dir / f"{safe_agent or 'agy'}-{safe_request}.agy.log"


def parse_antigravity_log_file(path: str | Path | None) -> dict[str, Any]:
    """Parse Antigravity per-call log metadata when a log file is available."""
    if not path:
        return {"diagnostics": []}
    log_path = Path(path).expanduser()
    if not log_path.exists():
        return {
            "log_file": str(log_path),
            "diagnostics": [f"antigravity_log_missing: {log_path}"],
        }
    try:
        return parse_antigravity_log(log_path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        return {
            "log_file": str(log_path),
            "diagnostics": [f"antigravity_log_unreadable: {exc}"],
        }


def parse_antigravity_log(text: str) -> dict[str, Any]:
    """Parse Antigravity conversation/model observations from CLI log text."""
    conversation_id = ""
    model_label = ""
    backend_model = ""

    conversation_match = re.search(
        r"(?:conversation=|conversation[ _-]?id[=:]\s*)([0-9A-Za-z][0-9A-Za-z_.:-]*)",
        text,
        flags=re.IGNORECASE,
    )
    if conversation_match:
        conversation_id = conversation_match.group(1).strip().strip(",")

    label_match = re.search(r"label=\"([^\"]+)\"", text, flags=re.IGNORECASE)
    if label_match is None:
        label_match = re.search(
            r"selected model(?: override)?[^:\n]*:\s*([^\n]+)",
            text,
            flags=re.IGNORECASE,
        )
    if label_match:
        model_label = (label_match.group(1) or "").strip()

    backend_match = re.search(
        r"^(?:backend|backend model)(?:=|:\s*)([0-9A-Za-z][0-9A-Za-z_.:-]*)",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if backend_match:
        backend_model = backend_match.group(1).strip().strip(",")

    return {
        "conversation_id": conversation_id,
        "model_label": model_label,
        "backend_model": backend_model,
        "diagnostics": [],
    }
