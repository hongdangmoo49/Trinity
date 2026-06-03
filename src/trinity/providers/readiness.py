"""Provider readiness gate — classifies pane content to detect unready states."""

from __future__ import annotations

import re

from trinity.models import Provider, ProviderState, ReadinessResult

# ---------------------------------------------------------------------------
# Pattern definitions per provider
# ---------------------------------------------------------------------------

# Each entry is (state, regex).  Patterns are evaluated top-to-bottom; first
# match wins.  All matching is case-insensitive.

_CLAUDE_PATTERNS: list[tuple[ProviderState, re.Pattern[str]]] = [
    (ProviderState.AUTH_REQUIRED, re.compile(r"oauth|authorization code|auth login|requires authentication", re.I)),
    (ProviderState.WORKSPACE_TRUST_REQUIRED, re.compile(r"trust.*(file|folder|workspace)", re.I)),
    (ProviderState.PROCESS_DEAD, re.compile(r"process exited|no such process", re.I)),
    (ProviderState.READY, re.compile(r">\s*$")),
]

_CODEX_PATTERNS: list[tuple[ProviderState, re.Pattern[str]]] = [
    (ProviderState.AUTH_REQUIRED, re.compile(r"auth.*login|please login|authentication required", re.I)),
    (ProviderState.MODEL_LOADING, re.compile(r"model.*(loading|default)", re.I)),
    (ProviderState.CLI_BANNER_ONLY, re.compile(r"/model to change", re.I)),
    (ProviderState.PROCESS_DEAD, re.compile(r"process exited|no such process", re.I)),
    (ProviderState.READY, re.compile(r"codex>\s*$")),
]

_GEMINI_PATTERNS: list[tuple[ProviderState, re.Pattern[str]]] = [
    (
        ProviderState.AUTH_REQUIRED,
        re.compile(
            r"choose.*authentication|auth.*method|select.*auth"
            r"|VERTEX_AI_PROJECT.*not set|vertex.*env.*missing"
            r"|terms.*privacy",
            re.I,
        ),
    ),
    (ProviderState.MODEL_LOADING, re.compile(r"model.*loading", re.I)),
    (ProviderState.PROCESS_DEAD, re.compile(r"process exited|no such process", re.I)),
    (ProviderState.READY, re.compile(r"gemini>\s*$")),
]

_PROVIDER_PATTERNS: dict[Provider, list[tuple[ProviderState, re.Pattern[str]]]] = {
    Provider.CLAUDE_CODE: _CLAUDE_PATTERNS,
    Provider.CODEX: _CODEX_PATTERNS,
    Provider.GEMINI_CLI: _GEMINI_PATTERNS,
}

# ---------------------------------------------------------------------------
# Action hints
# ---------------------------------------------------------------------------

_PROVIDER_CLI: dict[Provider, str] = {
    Provider.CLAUDE_CODE: "claude",
    Provider.CODEX: "codex",
    Provider.GEMINI_CLI: "gemini",
}

_ACTION_HINTS: dict[tuple[Provider, ProviderState], str] = {
    (Provider.CLAUDE_CODE, ProviderState.AUTH_REQUIRED): "Run: claude auth login",
    (Provider.CLAUDE_CODE, ProviderState.WORKSPACE_TRUST_REQUIRED): "Select 'Yes, proceed' in the Claude pane",
    (Provider.CODEX, ProviderState.AUTH_REQUIRED): "Run: codex auth login",
    (Provider.CODEX, ProviderState.MODEL_LOADING): "Wait for model loading, or run: codex doctor",
    (Provider.CODEX, ProviderState.CLI_BANNER_ONLY): "Send a test message or wait for Codex to initialize",
    (Provider.GEMINI_CLI, ProviderState.AUTH_REQUIRED): "Run: gemini auth login",
}


def _action_hint(provider: Provider, state: ProviderState) -> str:
    """Return the action hint for a provider/state pair."""
    hint = _ACTION_HINTS.get((provider, state))
    if hint:
        return hint
    # Generic fallback for AUTH_REQUIRED when provider not in table
    if state == ProviderState.AUTH_REQUIRED:
        return f"Run: {_PROVIDER_CLI.get(provider, provider.value)} auth login"
    return ""


# ---------------------------------------------------------------------------
# ProviderReadinessGate
# ---------------------------------------------------------------------------


class ProviderReadinessGate:
    """Classifies tmux pane content into readiness states for each provider."""

    def classify_pane_state(self, provider: Provider, lines: list[str]) -> ProviderState:
        """Classify pane output lines into a readiness state.

        Empty or whitespace-only lines produce ``UNKNOWN_NOT_READY``.
        Patterns are evaluated in priority order; first match wins.
        """
        # All lines empty/whitespace → unknown
        if not any(line.strip() for line in lines):
            return ProviderState.UNKNOWN_NOT_READY

        # Unknown provider (no patterns registered) → unknown
        patterns = _PROVIDER_PATTERNS.get(provider)
        if patterns is None:
            return ProviderState.UNKNOWN_NOT_READY

        # Outer loop: patterns in priority order; inner loop: lines.
        # This ensures a higher-priority match on *any* line wins over a
        # lower-priority match on an earlier line.
        for state, pattern in patterns:
            for line in lines:
                if pattern.search(line):
                    return state

        # No pattern matched — treat as not ready (unknown reason)
        return ProviderState.UNKNOWN_NOT_READY

    def check(self, agent_name: str, provider: Provider, pane_lines: list[str]) -> ReadinessResult:
        """Check a single agent's pane and return a ``ReadinessResult``."""
        state = self.classify_pane_state(provider, pane_lines)
        hint = _action_hint(provider, state)
        ready = state == ProviderState.READY
        reason = state.value if not ready else ""
        # Grab the first non-empty line as an excerpt (up to 120 chars)
        excerpt = ""
        for line in pane_lines:
            stripped = line.strip()
            if stripped:
                excerpt = stripped[:120]
                break
        return ReadinessResult(
            agent_name=agent_name,
            ready=ready,
            state=state,
            reason=reason,
            action_hint=hint,
            excerpt=excerpt,
        )

    def check_batch(
        self,
        agents: dict[str, tuple[Provider, list[str]]],
    ) -> dict[str, ReadinessResult]:
        """Check readiness for multiple agents at once.

        Parameters
        ----------
        agents:
            Mapping of ``agent_name`` → ``(provider, pane_lines)``.

        Returns
        -------
        Mapping of ``agent_name`` → ``ReadinessResult``.
        """
        results: dict[str, ReadinessResult] = {}
        for agent_name, (provider, pane_lines) in agents.items():
            results[agent_name] = self.check(agent_name, provider, pane_lines)
        return results
