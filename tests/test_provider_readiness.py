"""Tests for ProviderReadinessGate — pane state classification and action hints."""

from __future__ import annotations

import pytest

from trinity.models import Provider, ProviderState, ReadinessResult
from trinity.providers.readiness import ProviderReadinessGate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gate() -> ProviderReadinessGate:
    return ProviderReadinessGate()


# ===================================================================
# TestProviderReadinessClassifier
# ===================================================================


class TestProviderReadinessClassifier:
    """Pattern-based classification for each provider."""

    # -- Claude ---------------------------------------------------------

    def test_claude_oauth(self, gate: ProviderReadinessGate) -> None:
        lines = ["Welcome to Claude Code", "Please complete oauth to continue"]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.AUTH_REQUIRED

    def test_claude_auth_login(self, gate: ProviderReadinessGate) -> None:
        lines = ["You need to auth login before proceeding"]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.AUTH_REQUIRED

    def test_claude_requires_authentication(self, gate: ProviderReadinessGate) -> None:
        lines = ["Error: requires authentication"]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.AUTH_REQUIRED

    def test_claude_prompt_ready(self, gate: ProviderReadinessGate) -> None:
        lines = ["Welcome back!", "How can I help you today? > "]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.READY

    def test_claude_workspace_trust(self, gate: ProviderReadinessGate) -> None:
        lines = ["Do you trust the files in this folder?"]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.WORKSPACE_TRUST_REQUIRED

    def test_claude_workspace_trust_workspace(self, gate: ProviderReadinessGate) -> None:
        lines = ["Do you trust this workspace?"]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.WORKSPACE_TRUST_REQUIRED

    def test_claude_process_dead(self, gate: ProviderReadinessGate) -> None:
        lines = ["[exited]", "process exited with code 1"]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.PROCESS_DEAD

    # -- Codex ----------------------------------------------------------

    def test_codex_banner(self, gate: ProviderReadinessGate) -> None:
        lines = ["Codex CLI v1.0", "Type /model to change the active model"]
        assert gate.classify_pane_state(Provider.CODEX, lines) == ProviderState.CLI_BANNER_ONLY

    def test_codex_auth_required(self, gate: ProviderReadinessGate) -> None:
        lines = ["Error: authentication required"]
        assert gate.classify_pane_state(Provider.CODEX, lines) == ProviderState.AUTH_REQUIRED

    def test_codex_auth_login(self, gate: ProviderReadinessGate) -> None:
        lines = ["Please auth login to continue"]
        assert gate.classify_pane_state(Provider.CODEX, lines) == ProviderState.AUTH_REQUIRED

    def test_codex_please_login(self, gate: ProviderReadinessGate) -> None:
        lines = ["please login to use Codex"]
        assert gate.classify_pane_state(Provider.CODEX, lines) == ProviderState.AUTH_REQUIRED

    def test_codex_prompt_ready(self, gate: ProviderReadinessGate) -> None:
        lines = ["Ready.", "codex> "]
        assert gate.classify_pane_state(Provider.CODEX, lines) == ProviderState.READY

    def test_codex_model_loading(self, gate: ProviderReadinessGate) -> None:
        lines = ["Initializing...", "model loading, please wait"]
        assert gate.classify_pane_state(Provider.CODEX, lines) == ProviderState.MODEL_LOADING

    def test_codex_process_dead(self, gate: ProviderReadinessGate) -> None:
        lines = ["process exited"]
        assert gate.classify_pane_state(Provider.CODEX, lines) == ProviderState.PROCESS_DEAD

    # -- Gemini ---------------------------------------------------------

    def test_gemini_auth_picker(self, gate: ProviderReadinessGate) -> None:
        lines = ["Please choose authentication method:", "1. OAuth", "2. API Key"]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.AUTH_REQUIRED

    def test_gemini_select_auth(self, gate: ProviderReadinessGate) -> None:
        lines = ["Select auth method to continue"]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.AUTH_REQUIRED

    def test_gemini_vertex_env_missing(self, gate: ProviderReadinessGate) -> None:
        lines = ["Error: VERTEX_AI_PROJECT not set"]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.AUTH_REQUIRED

    def test_gemini_vertex_env_missing_alt(self, gate: ProviderReadinessGate) -> None:
        lines = ["vertex env missing, cannot proceed"]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.AUTH_REQUIRED

    def test_gemini_terms_privacy(self, gate: ProviderReadinessGate) -> None:
        lines = ["Please accept terms & privacy policy to continue"]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.AUTH_REQUIRED

    def test_gemini_prompt_ready(self, gate: ProviderReadinessGate) -> None:
        lines = ["Gemini CLI ready", "gemini> "]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.READY

    def test_gemini_model_loading(self, gate: ProviderReadinessGate) -> None:
        lines = ["model loading..."]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.MODEL_LOADING

    def test_gemini_process_dead(self, gate: ProviderReadinessGate) -> None:
        lines = ["no such process"]
        assert gate.classify_pane_state(Provider.GEMINI_CLI, lines) == ProviderState.PROCESS_DEAD

    # -- Generic --------------------------------------------------------

    def test_empty_lines_unknown_not_ready(self, gate: ProviderReadinessGate) -> None:
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, []) == ProviderState.UNKNOWN_NOT_READY
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, ["", "  "]) == ProviderState.UNKNOWN_NOT_READY

    def test_process_dead_all_providers(self, gate: ProviderReadinessGate) -> None:
        for provider in Provider:
            assert (
                gate.classify_pane_state(provider, ["process exited with code 0"])
                == ProviderState.PROCESS_DEAD
            )

    def test_unrecognized_output(self, gate: ProviderReadinessGate) -> None:
        """Lines that match no known pattern yield UNKNOWN_NOT_READY."""
        lines = ["some random output", "nothing recognizable here"]
        assert gate.classify_pane_state(Provider.CLAUDE_CODE, lines) == ProviderState.UNKNOWN_NOT_READY


# ===================================================================
# TestReadinessActionResult
# ===================================================================


class TestReadinessActionResult:
    """check() returns ReadinessResult with correct action hints."""

    def test_claude_auth_hint(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("claude-1", Provider.CLAUDE_CODE, ["requires authentication"])
        assert result.state == ProviderState.AUTH_REQUIRED
        assert result.action_hint == "Run: claude auth login"

    def test_claude_workspace_trust_hint(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("claude-1", Provider.CLAUDE_CODE, ["Do you trust the files here?"])
        assert result.state == ProviderState.WORKSPACE_TRUST_REQUIRED
        assert result.action_hint == "Select 'Yes, proceed' in the Claude pane"

    def test_codex_auth_hint(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("codex-1", Provider.CODEX, ["authentication required"])
        assert result.state == ProviderState.AUTH_REQUIRED
        assert result.action_hint == "Run: codex auth login"

    def test_codex_model_loading_hint(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("codex-1", Provider.CODEX, ["model loading..."])
        assert result.state == ProviderState.MODEL_LOADING
        assert result.action_hint == "Wait for model loading, or run: codex doctor"

    def test_codex_banner_hint(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("codex-1", Provider.CODEX, ["Type /model to change"])
        assert result.state == ProviderState.CLI_BANNER_ONLY
        assert result.action_hint == "Send a test message or wait for Codex to initialize"

    def test_gemini_auth_hint(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("gemini-1", Provider.GEMINI_CLI, ["choose authentication method"])
        assert result.state == ProviderState.AUTH_REQUIRED
        assert result.action_hint == "Run: gemini auth login"

    def test_ready_no_hint(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("claude-1", Provider.CLAUDE_CODE, ["> "])
        assert result.state == ProviderState.READY
        assert result.action_hint == ""
        assert result.ready is True

    def test_not_ready_flag(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("claude-1", Provider.CLAUDE_CODE, ["requires authentication"])
        assert result.ready is False
        assert result.reason == "auth_required"

    def test_result_fields(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("my-agent", Provider.CODEX, ["codex> "])
        assert result.agent_name == "my-agent"
        assert result.state == ProviderState.READY
        assert result.ready is True

    def test_excerpt_populated(self, gate: ProviderReadinessGate) -> None:
        result = gate.check("codex-1", Provider.CODEX, ["model loading, please wait"])
        assert result.excerpt == "model loading, please wait"


# ===================================================================
# TestBatchReadinessCheck
# ===================================================================


class TestBatchReadinessCheck:
    """check_batch() returns per-agent results."""

    def test_batch_mixed_states(self, gate: ProviderReadinessGate) -> None:
        agents = {
            "claude-1": (Provider.CLAUDE_CODE, ["> "]),
            "codex-1": (Provider.CODEX, ["authentication required"]),
            "gemini-1": (Provider.GEMINI_CLI, ["gemini> "]),
        }
        results = gate.check_batch(agents)

        assert len(results) == 3
        assert results["claude-1"].state == ProviderState.READY
        assert results["codex-1"].state == ProviderState.AUTH_REQUIRED
        assert results["gemini-1"].state == ProviderState.READY

    def test_batch_empty(self, gate: ProviderReadinessGate) -> None:
        results = gate.check_batch({})
        assert results == {}

    def test_batch_preserves_action_hints(self, gate: ProviderReadinessGate) -> None:
        agents = {
            "codex-1": (Provider.CODEX, ["model loading, please wait"]),
        }
        results = gate.check_batch(agents)
        assert results["codex-1"].action_hint == "Wait for model loading, or run: codex doctor"
