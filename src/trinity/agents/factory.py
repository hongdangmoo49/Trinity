"""Agent factory — create provider-specific agent instances from config."""

from __future__ import annotations

import logging
from pathlib import Path

from trinity.agents.antigravity_agent import AntigravityPrintAgent
from trinity.agents.base import AgentWrapper
from trinity.agents.claude_agent import InteractiveClaudeAgent, PrintModeClaudeAgent
from trinity.agents.codex_agent import CodexAgent
from trinity.agents.gemini_agent import GeminiAgent
from trinity.completion.base import CompletionDetector, FallbackChainDetector
from trinity.completion.hook import HookDetector
from trinity.completion.idle import IdleDetector
from trinity.completion.marker import MarkerDetector
from trinity.completion.prompt import PromptReturnDetector
from trinity.legacy.tmux.pane import TmuxPane
from trinity.models import AgentSpec, Provider

logger = logging.getLogger(__name__)


class AgentFactory:
    """Creates provider-specific agent instances.

    Separates agent creation logic from the orchestrator.
    Supports both print-mode (subprocess) and interactive (tmux) modes.
    """

    @staticmethod
    def create(
        spec: AgentSpec,
        mode: str = "print",
        pane: TmuxPane | None = None,
        detector: CompletionDetector | None = None,
        signal_path: Path | None = None,
    ) -> AgentWrapper:
        """Create an agent instance based on provider and mode.

        Args:
            spec: Agent configuration.
            mode: "print" for subprocess mode, "interactive" for tmux mode.
            pane: TmuxPane for interactive mode.
            detector: Completion detector for interactive mode.
            signal_path: Path for hook signal file.

        Returns:
            AgentWrapper subclass for the provider.
        """
        if mode == "interactive":
            return AgentFactory._create_interactive(spec, pane, detector, signal_path)
        else:
            return AgentFactory._create_print(spec)

    @staticmethod
    def _create_print(spec: AgentSpec) -> AgentWrapper:
        """Create a print-mode (subprocess) agent."""
        if spec.provider == Provider.CLAUDE_CODE:
            return PrintModeClaudeAgent(spec)
        elif spec.provider == Provider.CODEX:
            return CodexAgent(spec)
        elif spec.provider == Provider.ANTIGRAVITY_CLI:
            return AntigravityPrintAgent(spec)
        elif spec.provider == Provider.GEMINI_CLI:
            return GeminiAgent(spec)
        else:
            raise ValueError(f"Unknown provider: {spec.provider}")

    @staticmethod
    def _create_interactive(
        spec: AgentSpec,
        pane: TmuxPane | None,
        detector: CompletionDetector | None,
        signal_path: Path | None,
    ) -> AgentWrapper:
        """Create an interactive (tmux) agent."""
        if spec.provider == Provider.CLAUDE_CODE:
            if not pane or not detector:
                raise ValueError(
                    f"Interactive mode requires pane and detector for '{spec.name}'"
                )
            return InteractiveClaudeAgent(
                spec=spec, pane=pane, detector=detector, signal_path=signal_path,
            )
        elif spec.provider == Provider.CODEX:
            if not pane or not detector:
                raise ValueError(
                    f"Interactive mode requires pane and detector for '{spec.name}'"
                )
            return CodexAgent(spec, pane=pane, detector=detector)
        elif spec.provider == Provider.ANTIGRAVITY_CLI:
            raise ValueError(
                "Antigravity CLI provider is experimental: interactive tmux "
                "transport is not enabled by default."
            )
        elif spec.provider == Provider.GEMINI_CLI:
            if not pane or not detector:
                raise ValueError(
                    f"Interactive mode requires pane and detector for '{spec.name}'"
                )
            return GeminiAgent(spec, pane=pane, detector=detector)
        else:
            raise ValueError(f"Unknown provider: {spec.provider}")

    @staticmethod
    def create_detector_chain(signal_path: Path, provider: Provider) -> FallbackChainDetector:
        """Create a provider-appropriate completion detector chain.

        Claude: Hook → PromptReturn → IdleDetector(15s)
        Codex: PromptReturn → IdleDetector(20s)
        Gemini: Marker → PromptReturn → IdleDetector(25s)
        Default: PromptReturn → IdleDetector(20s)
        """
        if provider == Provider.CLAUDE_CODE:
            return FallbackChainDetector([
                HookDetector(signal_path=signal_path),
                PromptReturnDetector(),
                IdleDetector(15.0),
            ])
        elif provider == Provider.CODEX:
            return FallbackChainDetector([
                PromptReturnDetector(
                    prompt_patterns=[r"^\s*\$\s*$", r"^\s*>\s*$", r"^\s*›\s*$"]
                ),
                IdleDetector(20.0),
            ])
        elif provider == Provider.GEMINI_CLI:
            from trinity.agents.gemini_agent import COMPLETION_MARKER

            return FallbackChainDetector([
                MarkerDetector(COMPLETION_MARKER),
                PromptReturnDetector(),
                IdleDetector(25.0),
            ])
        else:
            # Default: wait for an explicit prompt return, then idle fallback.
            return FallbackChainDetector([
                PromptReturnDetector(),
                IdleDetector(20.0),
            ])
