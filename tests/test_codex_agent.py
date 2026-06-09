"""Tests for trinity.agents.codex_agent — CodexAgent."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock

from trinity.agents.codex_agent import CodexAgent
from trinity.completion.base import CompletionResult
from trinity.models import AgentSpec, ContextUsage, MessageRole, Provider, ResponseStatus
from trinity.providers.invoker import ProviderTurnResult
from trinity.providers.policy import InvocationAccess


@pytest.fixture
def codex_spec():
    return AgentSpec(
        name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        role_prompt="You are the Implementer.",
        context_budget=128_000,
    )


@pytest.fixture
def agent(codex_spec):
    return CodexAgent(codex_spec)


class TestCodexInit:
    def test_name(self, agent):
        assert agent.name == "codex"

    def test_context_budget(self, agent):
        assert agent.context_usage.total == 128_000

    def test_context_budget_uses_selected_model_budget(self, codex_spec):
        codex_spec.model = "gpt-5.4-mini"
        codex_spec.context_budget = 0
        agent = CodexAgent(codex_spec)
        assert agent.context_usage.total == 400_000

    def test_not_started(self, agent):
        assert not agent._started

    def test_session_dir(self, agent, tmp_path):
        agent.session_dir = tmp_path
        assert agent.session_dir == tmp_path


class TestCodexStart:
    @pytest.mark.asyncio
    async def test_start_print_mode(self, agent):
        await agent.start()
        assert agent._started

    @pytest.mark.asyncio
    async def test_start_with_initial_prompt(self, agent):
        await agent.start(initial_prompt="Welcome.")
        assert agent._initial_prompt == "Welcome."


class TestCodexSendAndWait:
    @pytest.mark.asyncio
    async def test_raises_if_not_started(self, agent):
        with pytest.raises(RuntimeError, match="not started"):
            await agent.send_and_wait("test")

    @pytest.mark.asyncio
    async def test_print_mode_subprocess(self, agent):
        await agent.start()

        agent._invoker.invoke = AsyncMock(
            return_value=ProviderTurnResult(
                agent_name="codex",
                content="I'll implement the auth module.",
                raw_output="raw",
                status=ResponseStatus.OK,
                elapsed_seconds=0.2,
                usage=ContextUsage(used=5000, total=0),
                tool_activity_summary=["command_execution:1"],
                metadata={
                    "provider_session": {
                        "provider_session_id": "thread-1",
                    }
                },
            )
        )
        msg = await agent.send_and_wait("Implement auth.")

        assert msg.source == "codex"
        assert msg.role == MessageRole.OPINION
        assert "auth" in msg.content
        assert msg.metadata["token_count"] == 5000
        assert msg.metadata["response_status"] == "ok"
        assert msg.metadata["tool_activity_summary"] == ["command_execution:1"]
        request = agent._invoker.invoke.call_args.args[0]
        assert request.prompt == "Implement auth."
        assert request.role_prompt == "You are the Implementer."
        assert request.continuity_enabled is True
        assert agent.provider_session_id == "thread-1"

        await agent.send_and_wait("Continue auth.")
        followup_request = agent._invoker.invoke.call_args.args[0]
        assert followup_request.provider_session_id == "thread-1"

    @pytest.mark.asyncio
    async def test_print_mode_forwards_invocation_access(self, agent):
        await agent.start()

        agent._invoker.invoke = AsyncMock(
            return_value=ProviderTurnResult(
                agent_name="codex",
                content="Implemented.",
                raw_output="raw",
                status=ResponseStatus.OK,
                elapsed_seconds=0.2,
            )
        )

        await agent.send_and_wait(
            "Implement auth.",
            access=InvocationAccess.WORKSPACE_WRITE,
        )

        request = agent._invoker.invoke.call_args.args[0]
        assert request.access == InvocationAccess.WORKSPACE_WRITE

    @pytest.mark.asyncio
    async def test_timeout(self, agent):
        await agent.start()

        agent._invoker.invoke = AsyncMock(
            return_value=ProviderTurnResult(
                agent_name="codex",
                content="[Timeout after 120s]",
                raw_output="",
                status=ResponseStatus.TIMEOUT,
                elapsed_seconds=120,
            )
        )
        msg = await agent.send_and_wait("test", timeout=120)

        assert "Timeout" in msg.content
        assert msg.metadata["response_status"] == "timeout"

    @pytest.mark.asyncio
    async def test_error_exit_code(self, agent):
        await agent.start()

        agent._invoker.invoke = AsyncMock(
            return_value=ProviderTurnResult(
                agent_name="codex",
                content="[Error: exit code 1]",
                raw_output="auth required",
                status=ResponseStatus.AUTH_REQUIRED,
                elapsed_seconds=0.1,
                diagnostics=["auth required"],
            )
        )
        msg = await agent.send_and_wait("test")

        assert "Error" in msg.content
        assert msg.metadata["response_status"] == "auth_required"

    @pytest.mark.asyncio
    async def test_interactive_mode_sends_prompt_before_waiting(self, codex_spec):
        pane = MagicMock()
        pane.is_alive.return_value = True
        detector = AsyncMock()
        detector.wait_for_completion.return_value = CompletionResult(
            completed=True,
            output="Codex response",
            detector_name="mock",
        )
        agent = CodexAgent(codex_spec, pane=pane, detector=detector)

        await agent.start(initial_prompt="Welcome.")
        msg = await agent.send_and_wait("Implement auth.")

        sent_prompt = pane.send_text_heredoc.call_args.args[0]
        assert "[System Role]" in sent_prompt
        assert "Welcome." in sent_prompt
        assert "Implement auth." in sent_prompt
        detector.wait_for_completion.assert_awaited_once_with(pane, timeout=300.0)
        assert msg.content == "Codex response"

    @pytest.mark.asyncio
    async def test_interactive_mode_extracts_after_pane_boundary(self, codex_spec):
        pane = MagicMock()
        pane.is_alive.return_value = True
        detector = AsyncMock()
        detector.wait_for_completion.return_value = CompletionResult(
            completed=True,
            output="thinking for 2s\n> ",
            detector_name="mock",
        )
        agent = CodexAgent(codex_spec, pane=pane, detector=detector)

        await agent.start(initial_prompt="Welcome.")
        sent_prompt = agent._build_prompt("Implement auth.")
        before_lines = ["codex ready", "> "]
        after_lines = (
            before_lines
            + sent_prompt.splitlines()
            + [
                "thinking for 2s",
                "Use JWT with rotating refresh tokens.",
                "> ",
            ]
        )
        pane.capture.side_effect = [before_lines, after_lines]

        msg = await agent.send_and_wait("Implement auth.")

        assert msg.content == "Use JWT with rotating refresh tokens."
        assert "Implement auth." not in msg.content
        assert "thinking" not in msg.content.lower()
        assert ">" not in msg.content

    @pytest.mark.asyncio
    async def test_interactive_mode_prefers_detector_scoped_output(self, codex_spec):
        pane = MagicMock()
        pane.is_alive.return_value = True
        detector = AsyncMock()
        agent = CodexAgent(codex_spec, pane=pane, detector=detector)

        await agent.start(initial_prompt="Welcome.")
        sent_prompt = agent._build_prompt("Implement auth.")
        detector.wait_for_completion.return_value = CompletionResult(
            completed=True,
            output="\n".join(
                sent_prompt.splitlines()
                + [
                    "Use the detector scoped Codex answer.",
                    "> ",
                ]
            ),
            detector_name="mock",
        )
        pane.capture.return_value = ["stale pane response", "> "]

        msg = await agent.send_and_wait("Implement auth.")

        assert msg.content == "Use the detector scoped Codex answer."
        assert "stale pane" not in msg.content
        assert "Implement auth." not in msg.content

    @pytest.mark.asyncio
    async def test_interactive_mode_preserves_timeout_detector_metadata(
        self, codex_spec
    ):
        pane = MagicMock()
        pane.is_alive.return_value = True
        pane.capture.return_value = ["fallback response"]
        detector = AsyncMock()
        detector.wait_for_completion.return_value = CompletionResult(
            completed=False,
            output="thinking for 2s\n> ",
            detector_name="mock",
            metadata={"reason": "timeout"},
        )
        agent = CodexAgent(codex_spec, pane=pane, detector=detector)

        await agent.start()
        msg = await agent.send_and_wait("Implement auth.")

        assert msg.metadata["completed"] is False
        assert msg.metadata["completion_timeout"] is True
        assert msg.metadata["completion_timeout_reason"] == "timeout"
        assert msg.metadata["detector_metadata"] == {"reason": "timeout"}


class TestCodexBuildPrompt:
    def test_with_role(self, agent):
        prompt = agent._build_prompt("Implement auth.")
        assert "[System Role]" in prompt
        assert "Implementer" in prompt
        assert "Implement auth" in prompt


class TestCodexSessionUsage:
    def test_parse_session_usage(self, agent, tmp_path):
        agent.session_dir = tmp_path
        (tmp_path / "session.json").write_text(
            json.dumps({"usage": {"total_tokens": 10000}}),
            encoding="utf-8",
        )
        result = agent._parse_session_usage()
        assert result is not None
        assert result.used == 10000

    def test_no_session_files(self, agent, tmp_path):
        agent.session_dir = tmp_path
        result = agent._parse_session_usage()
        assert result is None

    def test_no_session_dir(self, agent):
        agent.session_dir = None
        result = agent._parse_session_usage()
        assert result is None


class TestCodexIsAlive:
    @pytest.mark.asyncio
    async def test_alive_after_start(self, agent):
        await agent.start()
        assert await agent.is_alive() is True

    @pytest.mark.asyncio
    async def test_not_alive_after_shutdown(self, agent):
        await agent.start()
        await agent.graceful_shutdown()
        assert await agent.is_alive() is False


class TestCodexGetContextUsage:
    @pytest.mark.asyncio
    async def test_returns_usage(self, agent):
        usage = await agent.get_context_usage()
        assert isinstance(usage, ContextUsage)
        assert usage.total == 128_000
