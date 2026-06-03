"""Tests for provider readiness classification."""

from trinity.agents.base import AgentWrapper
from trinity.models import AgentSpec, ContextUsage, DeliberationMessage, Provider
from trinity.providers.readiness import ProviderReadinessGate, ProviderState


class FakePane:
    def __init__(self, lines: list[str], alive: bool = True):
        self.lines = lines
        self.alive = alive

    def capture(self, lines: int = -80) -> list[str]:
        return self.lines

    def is_alive(self) -> bool:
        return self.alive


class FakeAgent(AgentWrapper):
    def __init__(
        self,
        provider: Provider,
        lines: list[str],
        alive: bool = True,
        name: str = "agent",
    ):
        super().__init__(
            AgentSpec(
                name=name,
                provider=provider,
                cli_command=provider.value,
            )
        )
        self.pane = FakePane(lines, alive=alive)

    async def start(self, initial_prompt: str = "") -> None:
        pass

    async def send_and_wait(
        self, prompt: str, timeout: float = 120.0
    ) -> DeliberationMessage:
        raise NotImplementedError

    async def get_context_usage(self) -> ContextUsage:
        return self.context_usage

    async def is_alive(self) -> bool:
        return True

    async def graceful_shutdown(self) -> None:
        pass


def test_claude_oauth_screen_is_auth_required():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Claude Code",
            "Open the following OAuth URL to authenticate:",
            "https://claude.ai/oauth/authorize?...",
            "Invalid code. Try again.",
        ],
        provider=Provider.CLAUDE_CODE,
        agent_name="claude",
    )

    assert result.ready is False
    assert result.state == ProviderState.AUTH_REQUIRED
    assert "authentication" in result.reason
    assert "claude" in result.action_hint
    assert "OAuth" in result.excerpt


def test_claude_auth_and_trust_variants_are_classified():
    gate = ProviderReadinessGate()

    for line in (
        "Enter authorization code to continue",
        "You need to auth login before proceeding",
        "Error: requires authentication",
        "Select login method:",
        "Claude account with subscription",
    ):
        result = gate.classify_pane_state(
            ["Claude Code", line],
            provider=Provider.CLAUDE_CODE,
            agent_name="claude",
        )
        assert result.state == ProviderState.AUTH_REQUIRED

    result = gate.classify_pane_state(
        ["Do you trust the files in this folder?"],
        provider=Provider.CLAUDE_CODE,
        agent_name="claude",
    )
    assert result.state == ProviderState.WORKSPACE_TRUST_REQUIRED


def test_gemini_auth_picker_is_auth_required():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Welcome to Gemini CLI",
            "Select authentication method:",
            "1. Sign in with Google",
            "2. Use API key",
        ],
        provider=Provider.GEMINI_CLI,
        agent_name="gemini",
    )

    assert result.ready is False
    assert result.state == ProviderState.AUTH_REQUIRED
    assert "gemini" in result.action_hint


def test_gemini_auth_env_terms_and_process_variants_are_classified():
    gate = ProviderReadinessGate()

    for line in (
        "Please choose authentication method:",
        "Error: VERTEX_AI_PROJECT not set",
        "vertex env missing, cannot proceed",
        "Please accept terms & privacy policy to continue",
    ):
        result = gate.classify_pane_state(
            ["Gemini CLI", line],
            provider=Provider.GEMINI_CLI,
            agent_name="gemini",
        )
        assert result.state == ProviderState.AUTH_REQUIRED

    result = gate.classify_pane_state(
        ["no such process"],
        provider=Provider.GEMINI_CLI,
        agent_name="gemini",
    )
    assert result.state == ProviderState.PROCESS_DEAD


def test_codex_model_loading_banner_is_model_loading():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "model: loading   /model to change",
            "gpt-5.5 default",
            "/model to change",
            "/help for commands",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is False
    assert result.state == ProviderState.MODEL_LOADING
    assert "loading" in result.reason


def test_codex_ready_prompt_with_default_model_is_ready():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "model:     gpt-5.5   /model to change",
            "Tip: Build faster with Codex.",
            "› Run /review on my changes",
            "gpt-5.5 default …",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is True
    assert result.state == ProviderState.READY


def test_codex_ready_prompt_wins_over_stale_loading_scrollback():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "model: loading   /model to change",
            "directory: /home/zaemi/workspace/Trinity",
            "› Summarize recent",
            "gpt-5.5 default …",
            "Codex",
            "model:     gpt-5.5   /model to change",
            "directory: /home/zaemi/workspace/Trinity",
            "Tip: New Build faster with Codex.",
            "› Summarize recent",
            "gpt-5.5 default …",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is True
    assert result.state == ProviderState.READY


def test_gemini_type_message_prompt_is_ready():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Gemini CLI v0.45.0",
            "Signed in with Google /auth",
            "Shift+Tab to accept edits",
            ">   Type your message or @path/to/file",
            "workspace (/directory)      branch      sandbox",
        ],
        provider=Provider.GEMINI_CLI,
        agent_name="gemini",
    )

    assert result.ready is True
    assert result.state == ProviderState.READY


def test_codex_auth_and_process_variants_are_classified():
    gate = ProviderReadinessGate()

    for line in (
        "please login to use Codex",
        "Error: authentication required",
        "Please auth login to continue",
    ):
        result = gate.classify_pane_state(
            ["Codex", line],
            provider=Provider.CODEX,
            agent_name="codex",
        )
        assert result.state == ProviderState.AUTH_REQUIRED

    result = gate.classify_pane_state(
        ["process exited with code 1"],
        provider=Provider.CODEX,
        agent_name="codex",
    )
    assert result.state == ProviderState.PROCESS_DEAD


def test_ready_prompt_is_ready():
    gate = ProviderReadinessGate()

    for provider in Provider:
        result = gate.classify_pane_state(
            ["Welcome", ">"],
            provider=provider,
            agent_name=provider.value,
        )
        assert result.ready is True
        assert result.state == ProviderState.READY
        assert result.action_hint == ""


def test_cli_banner_without_prompt_is_banner_only():
    gate = ProviderReadinessGate()

    result = gate.classify_pane_state(
        [
            "Codex",
            "/model to change",
            "/help for commands",
        ],
        provider=Provider.CODEX,
        agent_name="codex",
    )

    assert result.ready is False
    assert result.state == ProviderState.CLI_BANNER_ONLY


def test_agent_with_dead_pane_is_process_dead():
    gate = ProviderReadinessGate()
    agent = FakeAgent(
        provider=Provider.CLAUDE_CODE,
        lines=[">"],
        alive=False,
        name="claude",
    )

    result = gate.check(agent)

    assert result.ready is False
    assert result.state == ProviderState.PROCESS_DEAD
    assert "Restart" in result.action_hint
