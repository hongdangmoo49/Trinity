"""Tests for trinity.agents.factory — AgentFactory."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from trinity.agents.claude_agent import InteractiveClaudeAgent, PrintModeClaudeAgent
from trinity.agents.codex_agent import CodexAgent
from trinity.agents.factory import AgentFactory
from trinity.agents.gemini_agent import GeminiAgent
from trinity.completion.hook import HookDetector
from trinity.completion.marker import MarkerDetector
from trinity.completion.prompt import PromptReturnDetector
from trinity.models import AgentSpec, Provider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def claude_spec():
    return AgentSpec(
        name="claude",
        provider=Provider.CLAUDE_CODE,
        cli_command="claude",
        context_budget=100_000,
    )


@pytest.fixture
def codex_spec():
    return AgentSpec(
        name="codex",
        provider=Provider.CODEX,
        cli_command="codex",
        context_budget=80_000,
    )


@pytest.fixture
def gemini_spec():
    return AgentSpec(
        name="gemini",
        provider=Provider.GEMINI_CLI,
        cli_command="gemini",
        context_budget=200_000,
    )


@pytest.fixture
def mock_pane():
    return MagicMock()


@pytest.fixture
def mock_detector():
    return MagicMock()


@pytest.fixture
def signal_path(tmp_path):
    return tmp_path / "signal.json"


# ===========================================================================
# Print mode creation
# ===========================================================================

class TestCreatePrintMode:
    """AgentFactory.create() with mode='print'."""

    def test_claude_print(self, claude_spec):
        agent = AgentFactory.create(claude_spec, mode="print")
        assert isinstance(agent, PrintModeClaudeAgent)
        assert agent.name == "claude"

    def test_codex_print(self, codex_spec):
        agent = AgentFactory.create(codex_spec, mode="print")
        assert isinstance(agent, CodexAgent)
        assert agent.name == "codex"

    def test_gemini_print(self, gemini_spec):
        agent = AgentFactory.create(gemini_spec, mode="print")
        assert isinstance(agent, GeminiAgent)
        assert agent.name == "gemini"

    def test_print_is_default_mode(self, claude_spec):
        """mode 파라미터 생략 시 print 모드가 기본."""
        agent = AgentFactory.create(claude_spec)
        assert isinstance(agent, PrintModeClaudeAgent)

    def test_unknown_provider_raises(self):
        unknown_spec = AgentSpec(
            name="unknown",
            provider="unknown-provider",
            cli_command="fake",
        )
        with pytest.raises(ValueError, match="Unknown provider"):
            AgentFactory.create(unknown_spec, mode="print")


# ===========================================================================
# Interactive mode creation
# ===========================================================================

class TestCreateInteractiveMode:
    """AgentFactory.create() with mode='interactive'."""

    def test_claude_interactive(self, claude_spec, mock_pane, mock_detector, signal_path):
        agent = AgentFactory.create(
            claude_spec,
            mode="interactive",
            pane=mock_pane,
            detector=mock_detector,
            signal_path=signal_path,
        )
        assert isinstance(agent, InteractiveClaudeAgent)
        assert agent.name == "claude"

    def test_codex_interactive(self, codex_spec, mock_pane, mock_detector, signal_path):
        agent = AgentFactory.create(
            codex_spec,
            mode="interactive",
            pane=mock_pane,
            detector=mock_detector,
            signal_path=signal_path,
        )
        assert isinstance(agent, CodexAgent)
        assert agent.name == "codex"

    def test_gemini_interactive(self, gemini_spec, mock_pane, mock_detector, signal_path):
        agent = AgentFactory.create(
            gemini_spec,
            mode="interactive",
            pane=mock_pane,
            detector=mock_detector,
            signal_path=signal_path,
        )
        assert isinstance(agent, GeminiAgent)
        assert agent.name == "gemini"

    def test_interactive_without_pane_raises(self, claude_spec, mock_detector, signal_path):
        """interactive 모드에서 pane이 없으면 ValueError."""
        with pytest.raises(ValueError, match="requires pane and detector"):
            AgentFactory.create(
                claude_spec,
                mode="interactive",
                pane=None,
                detector=mock_detector,
                signal_path=signal_path,
            )

    def test_interactive_without_detector_raises(self, claude_spec, mock_pane, signal_path):
        """interactive 모드에서 detector가 없으면 ValueError."""
        with pytest.raises(ValueError, match="requires pane and detector"):
            AgentFactory.create(
                claude_spec,
                mode="interactive",
                pane=mock_pane,
                detector=None,
                signal_path=signal_path,
            )

    def test_interactive_unknown_provider_raises(self, mock_pane, mock_detector, signal_path):
        unknown_spec = AgentSpec(
            name="unknown",
            provider="unknown-provider",
            cli_command="fake",
        )
        with pytest.raises(ValueError, match="Unknown provider"):
            AgentFactory.create(
                unknown_spec,
                mode="interactive",
                pane=mock_pane,
                detector=mock_detector,
                signal_path=signal_path,
            )


# ===========================================================================
# Detector chain creation
# ===========================================================================

class TestCreateDetectorChain:
    """AgentFactory.create_detector_chain() — provider별 detector 체인."""

    def test_claude_chain_structure(self, signal_path):
        """Claude: Hook → PromptReturn → IdleDetector."""
        chain = AgentFactory.create_detector_chain(signal_path, Provider.CLAUDE_CODE)
        assert len(chain.detectors) == 3
        assert isinstance(chain.detectors[0], HookDetector)
        assert isinstance(chain.detectors[1], PromptReturnDetector)

    def test_codex_chain_structure(self, signal_path):
        """Codex: PromptReturn(custom patterns) → IdleDetector."""
        chain = AgentFactory.create_detector_chain(signal_path, Provider.CODEX)
        assert len(chain.detectors) == 2
        assert isinstance(chain.detectors[0], PromptReturnDetector)

    def test_gemini_chain_structure(self, signal_path):
        """Gemini: Marker → PromptReturn → IdleDetector."""
        chain = AgentFactory.create_detector_chain(signal_path, Provider.GEMINI_CLI)
        assert len(chain.detectors) == 3
        assert isinstance(chain.detectors[0], MarkerDetector)
        assert isinstance(chain.detectors[1], PromptReturnDetector)

    def test_unknown_provider_default_chain(self, signal_path):
        """알 수 없는 provider는 기본 PromptReturn → IdleDetector 체인."""
        chain = AgentFactory.create_detector_chain(signal_path, "unknown")
        assert len(chain.detectors) == 2
        assert isinstance(chain.detectors[0], PromptReturnDetector)

    def test_claude_hook_signal_path(self, signal_path):
        """Claude 체인의 HookDetector가 signal_path를 정확히 사용."""
        chain = AgentFactory.create_detector_chain(signal_path, Provider.CLAUDE_CODE)
        hook = chain.detectors[0]
        assert isinstance(hook, HookDetector)
        assert hook.signal_path == signal_path


def test_claude_chain_includes_idle_detector():
    from pathlib import Path
    chain = AgentFactory.create_detector_chain(Path("/tmp/signal.json"), Provider.CLAUDE_CODE)
    names = [d.name for d in chain.detectors]
    assert any("IdleDetector" in n for n in names)


def test_gemini_chain_includes_idle_detector():
    from pathlib import Path
    chain = AgentFactory.create_detector_chain(Path("/tmp/signal.json"), Provider.GEMINI_CLI)
    names = [d.name for d in chain.detectors]
    assert any("IdleDetector" in n for n in names)


def test_codex_chain_includes_idle_detector():
    from pathlib import Path
    chain = AgentFactory.create_detector_chain(Path("/tmp/signal.json"), Provider.CODEX)
    names = [d.name for d in chain.detectors]
    assert any("IdleDetector" in n for n in names)


def test_idle_timeouts_differ_by_provider():
    from pathlib import Path
    from trinity.completion.idle import IdleDetector

    claude_chain = AgentFactory.create_detector_chain(Path("/tmp/s.json"), Provider.CLAUDE_CODE)
    codex_chain = AgentFactory.create_detector_chain(Path("/tmp/s.json"), Provider.CODEX)
    gemini_chain = AgentFactory.create_detector_chain(Path("/tmp/s.json"), Provider.GEMINI_CLI)

    def get_idle_timeout(chain):
        for d in chain.detectors:
            if isinstance(d, IdleDetector):
                return d.idle_timeout
        return None

    assert get_idle_timeout(claude_chain) == 15.0
    assert get_idle_timeout(codex_chain) == 20.0
    assert get_idle_timeout(gemini_chain) == 25.0
