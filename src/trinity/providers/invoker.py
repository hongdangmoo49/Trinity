"""One-shot provider invocation contracts and CLI invokers."""

from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from trinity.models import ContextUsage, Provider, ResponseStatus
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
        kwargs: dict[str, Any] = {"cwd": request.cwd}
        if request.env:
            env = os.environ.copy()
            env.update(request.env)
            kwargs["env"] = env
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=request.timeout_seconds,
            **kwargs,
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


class ClaudePrintInvoker(CliProviderInvoker):
    """Invoke Claude Code with `claude -p --output-format json`."""

    def build_command(self, request: PromptRequest) -> list[str]:
        command = [
            request.cli_command,
            *self._model_args(request),
            "-p",
            "--output-format",
            "json",
        ]
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
                "model": data.get("model"),
            },
        )

    @staticmethod
    def _parse_usage(data: Any, request: PromptRequest) -> ContextUsage:
        usage_data = data if isinstance(data, dict) else {}
        used = int(usage_data.get("input_tokens", 0)) + int(
            usage_data.get("output_tokens", 0)
        )
        return ContextUsage(used=used, total=0)


class CodexExecInvoker(CliProviderInvoker):
    """Invoke Codex with `codex exec --json` and parse JSONL events."""

    def build_command(self, request: PromptRequest) -> list[str]:
        command = [
            request.cli_command,
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            request.access.value,
            "--cd",
            str(request.cwd),
            *self._model_args(request),
        ]
        command.extend(request.extra_args)
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
            metadata={"command": command, "returncode": completed.returncode},
        )


def parse_codex_jsonl(stdout: str) -> dict[str, Any]:
    """Parse `codex exec --json` JSONL stdout into normalized fields."""
    content = ""
    usage: ContextUsage | None = None
    diagnostics: list[str] = []
    tool_counts: dict[str, int] = {}
    status = ResponseStatus.EMPTY

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
        "tool_activity_summary": summary,
    }


def _parse_codex_usage(data: Any) -> ContextUsage | None:
    if not isinstance(data, dict):
        return None
    input_tokens = int(data.get("input_tokens", 0))
    output_tokens = int(data.get("output_tokens", 0))
    reasoning_tokens = int(data.get("reasoning_output_tokens", 0))
    return ContextUsage(used=input_tokens + output_tokens + reasoning_tokens, total=0)


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
        command.append("--print")
        command.extend(request.extra_args)
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
                **self.output_metadata,
            },
        )
