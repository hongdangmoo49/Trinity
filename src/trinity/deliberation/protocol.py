"""Deliberation protocol — round-based deliberation loop."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from trinity.agents.base import AgentWrapper
from trinity.context.analytics import TokenAnalytics, RoundRecord
from trinity.context.budget import TokenBudgetChecker
from trinity.context.compressor import PromptCompressor
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.models import (
    ConsensusResult,
    DeliberationMessage,
    DeliberationResult,
    MessageRole,
    TaskAssignment,
)
from trinity.tui.events import TUIEvent, TUIEventType

logger = logging.getLogger(__name__)


class DeliberationProtocol:
    """Round-based deliberation: opinions → counter → consensus → tasks.

    Each round:
    1. Build a round-specific prompt for all agents
    2. Send to all agents in parallel (with per-agent completion streaming)
    3. Collect responses → write to shared.md
    4. Check for consensus
    5. If reached, distribute tasks. Otherwise, next round.

    When an event_callback is provided, events are emitted for each
    agent completion, round transition, and consensus evaluation,
    enabling real-time TUI updates.
    """

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        shared: SharedContextEngine,
        consensus_engine: ConsensusEngine | None = None,
        distributor: TaskDistributor | None = None,
        max_rounds: int = 5,
        round_timeout: float = 120.0,
        tmux_manager=None,
        event_callback: Callable[[TUIEvent], None] | None = None,
        compression_enabled: bool = True,
        compression_round_threshold: int = 2,
        compression_max_summary_tokens: int = 200,
    ):
        self.agents = agents
        self.shared = shared
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.distributor = distributor or TaskDistributor()
        self.max_rounds = max_rounds
        self.round_timeout = round_timeout
        self.tmux_manager = tmux_manager
        self._event_callback = event_callback
        self.compressor: PromptCompressor | None = None
        self.compression_enabled = compression_enabled
        if compression_enabled:
            self.compressor = PromptCompressor(
                max_summary_tokens=compression_max_summary_tokens,
            )
        self.compression_round_threshold = compression_round_threshold
        self.budget_checker = TokenBudgetChecker()

        # Token usage analytics
        self.analytics = TokenAnalytics()

    def _emit(self, event_type: TUIEventType, **kwargs) -> None:
        """Emit a TUI event if callback is registered."""
        if self._event_callback:
            self._event_callback(TUIEvent(type=event_type, data=kwargs))

    async def run(self, user_prompt: str) -> DeliberationResult:
        """Execute full deliberation loop."""
        start_time = time.time()
        agent_names = list(self.agents.keys())

        # Initialize shared.md
        self.shared.initialize(goal=user_prompt, agent_names=agent_names)

        consensus: ConsensusResult | None = None
        round_num = 0

        for round_num in range(1, self.max_rounds + 1):
            logger.info(f"=== Round {round_num}/{self.max_rounds} ===")

            # Emit round start
            self._emit(TUIEventType.ROUND_START, round_num=round_num)

            # Update tmux pane titles to show round progress
            self._update_pane_titles(f"Round {round_num}/{self.max_rounds}")

            # Build prompt for this round
            round_prompt = self._build_round_prompt(round_num, user_prompt)

            # Collect opinions from all agents (with per-agent streaming)
            opinions = await self._collect_opinions(round_num, round_prompt)

            # Write opinions to shared.md
            for name, msg in opinions.items():
                self.shared.append_opinion(name, round_num, msg.content)

            # Record token analytics for this round
            round_agent_tokens = {name: msg.token_count for name, msg in opinions.items()}
            round_prompt_tokens = (
                self.compressor.estimate_tokens(round_prompt) if self.compressor
                else len(round_prompt.split())
            )
            self.analytics.record(RoundRecord(
                round_num=round_num,
                agent_tokens=round_agent_tokens,
                prompt_tokens=round_prompt_tokens,
                duration_seconds=0.0,  # Per-round timing not critical here
            ))

            # Update message round_num (it was set to 0 in agent)
            for name, msg in opinions.items():
                msg.round_num = round_num

            # Check consensus
            self._emit(TUIEventType.CONSENSUS_CHECKING, round_num=round_num)

            opinion_texts = {name: msg.content for name, msg in opinions.items()}
            consensus = self.consensus_engine.evaluate(opinion_texts)

            if consensus.reached:
                logger.info(f"Consensus reached at round {round_num}!")
                self.shared.update_consensus(consensus.summary)
                self._update_pane_titles("✓ Consensus!")

                self._emit(
                    TUIEventType.CONSENSUS_RESULT,
                    reached=True,
                    agreement_count=consensus.agreement_count,
                    total_agents=consensus.total_agents,
                    summary=consensus.summary,
                    round_num=round_num,
                )
                break

            logger.info(f"No consensus yet. Continuing to round {round_num + 1}.")

            self._emit(
                TUIEventType.CONSENSUS_RESULT,
                reached=False,
                agreement_count=consensus.agreement_count,
                total_agents=consensus.total_agents,
                summary="",
                round_num=round_num,
            )

        # Update pane titles for task distribution phase
        self._update_pane_titles("Distributing tasks...")

        # If no consensus after all rounds, force conclusion
        if consensus and not consensus.reached:
            logger.warning(f"Max rounds ({self.max_rounds}) reached. Forcing conclusion.")
            consensus = ConsensusResult(
                reached=True,  # Force it
                agreement_count=consensus.agreement_count,
                total_agents=consensus.total_agents,
                opinions=consensus.opinions,
                summary=f"Forced conclusion after {self.max_rounds} rounds. "
                f"Majority opinion selected.",
            )
            self.shared.update_consensus(consensus.summary)

        # Distribute tasks
        tasks = self.distributor.distribute(
            consensus_text=consensus.summary if consensus else user_prompt,
            agents={name: ag.spec for name, ag in self.agents.items()},
        )

        # Write tasks to shared.md
        task_dict = {t.agent_name: t.task_description for t in tasks}
        self.shared.update_tasks(task_dict)

        # Calculate totals
        total_tokens = sum(
            ag.context_usage.used for ag in self.agents.values()
        )
        elapsed = time.time() - start_time

        self._emit(TUIEventType.DELIBERATION_DONE)

        return DeliberationResult(
            user_prompt=user_prompt,
            rounds_completed=round_num,
            consensus=consensus,
            tasks=tasks,
            total_tokens_used=total_tokens,
            duration_seconds=elapsed,
        )

    async def _collect_opinions(
        self, round_num: int, prompt: str
    ) -> dict[str, DeliberationMessage]:
        """Send prompt to all agents in parallel and collect responses.

        Uses asyncio.wait(FIRST_COMPLETED) instead of asyncio.gather
        to enable per-agent completion streaming via events.
        """
        # Create tasks with agent names attached
        pending: set[asyncio.Task] = set()
        task_to_name: dict[asyncio.Task, str] = {}

        for name, agent in self.agents.items():
            coro = agent.send_and_wait(prompt, timeout=self.round_timeout)
            task = asyncio.ensure_future(coro)
            task_to_name[task] = name
            pending.add(task)
            self._emit(TUIEventType.AGENT_THINKING, agent=name, round_num=round_num)

        opinions: dict[str, DeliberationMessage] = {}

        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                name = task_to_name[task]
                try:
                    result = task.result()
                except Exception as exc:
                    logger.error(f"[{name}] Error in round {round_num}: {exc}")
                    opinions[name] = DeliberationMessage(
                        source=name,
                        target="all",
                        round_num=round_num,
                        role=MessageRole.OPINION,
                        content=f"[Error: {exc}]",
                    )
                    self._emit(
                        TUIEventType.AGENT_ERROR,
                        agent=name,
                        error=str(exc),
                        round_num=round_num,
                    )
                    continue

                if isinstance(result, DeliberationMessage):
                    result.round_num = round_num
                    opinions[name] = result
                    self._emit(
                        TUIEventType.AGENT_RESPONDED,
                        agent=name,
                        content=result.content,
                        round_num=round_num,
                    )
                else:
                    logger.warning(f"[{name}] Unexpected result type: {type(result)}")
                    self._emit(
                        TUIEventType.AGENT_ERROR,
                        agent=name,
                        error=f"Unexpected result type: {type(result)}",
                        round_num=round_num,
                    )

        return opinions

    def _build_round_prompt(self, round_num: int, user_prompt: str) -> str:
        """Build the prompt for a specific deliberation round.

        For rounds >= compression_round_threshold, old rounds are compressed.
        """
        if round_num == 1:
            return (
                f"Read the shared context below for background.\n\n"
                f"User's request: {user_prompt}\n\n"
                f"Share your initial opinion. Be specific and concise.\n"
                f"State your recommendation and key reasoning.\n"
                f"Keep your response under 500 words."
            )

        use_compression = (
            self.compression_enabled
            and self.compressor is not None
            and round_num >= self.compression_round_threshold
        )

        if use_compression:
            self._compress_old_rounds(round_num)
            prev_context = self.shared.get_rounds_for_prompt(
                current_round=round_num,
                verbatim_rounds=1,
            )
            if not prev_context.strip():
                prev_context = "(previous round opinions not available)"
        else:
            prev_section = self.shared.read_section(f"Round {round_num - 1} Opinions")
            prev_context = prev_section or "(previous round opinions not available)"

        return (
            f"Previous round opinions:\n\n"
            f"{prev_context}\n\n"
            f"---\n\n"
            f"For each other agent's opinion above, state whether you AGREE or DISAGREE "
            f"and explain why. If you disagree, propose an alternative.\n"
            f"End your response with either 'I AGREE with [name]' or your counter-proposal.\n"
            f"Keep your response under 300 words."
        )

    def _compress_old_rounds(self, current_round: int) -> None:
        """Compress rounds older than current_round - 1 if not already compressed."""
        if not self.compressor:
            return

        prev_round = current_round - 1
        round_to_compress = prev_round - 1

        if round_to_compress < 1:
            return

        # Check if already compressed
        existing = self.shared.read_section(f"Round {round_to_compress} Summary")
        if existing is not None:
            return

        round_section = self.shared.read_section(f"Round {round_to_compress} Opinions")
        if not round_section:
            return

        agent_opinions = self._extract_agent_opinions(round_section)

        if agent_opinions:
            compressed = self.compressor.compress_opinions_heuristic(agent_opinions)
        else:
            compressed = self.compressor.compress_heuristic(round_section)

        self.shared.write_compressed_summary(round_to_compress, compressed)
        logger.info(
            f"Compressed Round {round_to_compress}: "
            f"{len(round_section)} -> {len(compressed)} chars"
        )

        # Remove original opinions section to prevent shared.md unbounded growth
        self.shared.remove_section(f"Round {round_to_compress} Opinions")
        logger.info(f"Removed original Round {round_to_compress} Opinions from shared.md")

    @staticmethod
    def _extract_agent_opinions(round_section: str) -> dict[str, str]:
        """Extract ### agent_name blocks from round section markdown."""
        opinions: dict[str, str] = {}
        current_agent: str | None = None
        current_lines: list[str] = []

        for line in round_section.splitlines():
            if line.startswith("### "):
                if current_agent is not None:
                    opinions[current_agent] = "\n".join(current_lines).strip()
                current_agent = line[4:].strip()
                current_lines = []
            elif current_agent is not None:
                current_lines.append(line)

        if current_agent is not None:
            opinions[current_agent] = "\n".join(current_lines).strip()

        return opinions

    def _update_pane_titles(self, status_text: str) -> None:
        """Update tmux pane titles to show round progress (Phase 2 feature)."""
        if not self.tmux_manager:
            return

        import subprocess

        for name in self.agents:
            pane = self.tmux_manager.get_pane(name)
            if pane:
                try:
                    subprocess.run(
                        [
                            "tmux",
                            "select-pane",
                            "-t",
                            pane.pane_id,
                            "-T",
                            f"{name}: {status_text}",
                        ],
                        capture_output=True,
                        timeout=5,
                    )
                except Exception:
                    pass  # Non-critical — don't fail deliberation for title update
