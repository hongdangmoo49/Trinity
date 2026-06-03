"""Provider readiness detection for interactive CLI sessions."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from trinity.agents.base import AgentWrapper
from trinity.models import Provider


class ProviderState(str, Enum):
    """Classified provider state before a deliberation request is sent."""

    READY = "ready"
    AUTH_REQUIRED = "auth_required"
    MODEL_LOADING = "model_loading"
    WORKSPACE_TRUST_REQUIRED = "workspace_trust_required"
    CLI_BANNER_ONLY = "cli_banner_only"
    PROMPT_NOT_SENT = "prompt_not_sent"
    PROCESS_DEAD = "process_dead"
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


_PROMPT_RE = re.compile(
    r"^\s*(?:[>$❯›]|[>›]\s+.+|trinity>|claude>|codex>|gemini>)\s*$"
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


def _action_hint(provider: Provider, state: ProviderState) -> str:
    provider_name = _provider_label(provider)
    if state == ProviderState.READY:
        return ""
    if state == ProviderState.AUTH_REQUIRED:
        if provider == Provider.CLAUDE_CODE:
            return "Run `claude` in a terminal and complete login/authentication."
        if provider == Provider.CODEX:
            return "Run `codex login` or open `codex` and complete authentication."
        if provider == Provider.GEMINI_CLI:
            return "Run `gemini` and complete the authentication flow."
    if state == ProviderState.MODEL_LOADING:
        return f"Wait for {provider_name} model initialization to finish, then retry."
    if state == ProviderState.WORKSPACE_TRUST_REQUIRED:
        return "Accept the workspace trust prompt in the provider CLI, then retry."
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
        if _contains(text, _PROCESS_DEAD_PATTERNS):
            return ProviderState.PROCESS_DEAD
        if _contains(text, _WORKSPACE_TRUST_PATTERNS):
            return ProviderState.WORKSPACE_TRUST_REQUIRED
        if _contains(text, _AUTH_PATTERNS[provider]):
            return ProviderState.AUTH_REQUIRED
        if _contains(text, _MODEL_LOADING_PATTERNS[provider]):
            return ProviderState.MODEL_LOADING

        banner_only = _contains(text, _BANNER_PATTERNS[provider])
        prompt_ready = _has_ready_prompt(lines, provider)
        if prompt_ready:
            return ProviderState.READY
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
    Provider.GEMINI_CLI: (
        *_COMMON_AUTH_PATTERNS,
        r"\bauth\b.*\bmethod\b",
        r"select\s+(?:auth|authentication)\s+method",
        r"choose\s+(?:auth|authentication)",
        r"google\s+account",
        r"vertex_ai_project.*not\s+set",
        r"vertex.*env.*missing",
        r"vertex\s+ai.*(?:missing|required|not\s+configured)",
        r"terms.*privacy",
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
    Provider.GEMINI_CLI: (
        r"\bloading\b.*\bmodel\b",
        r"\binitializing\b.*\bgemini\b",
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
    Provider.GEMINI_CLI: (
        r"\btype\s+your\s+message\s+or\s+@path/to/file\b",
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
    Provider.GEMINI_CLI: (
        r"\bgemini\b",
        r"\bgoogle\s+gemini\b",
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
