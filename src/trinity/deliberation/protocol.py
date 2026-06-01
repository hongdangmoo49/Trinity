"""Deliberation protocol — round-based deliberation loop."""

from __future__ import annotations

import asyncio
import logging
import time

from trinity.agents.base import AgentWrapper
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

logger = logging.getLogger(__name__)


class DeliberationProtocol:
    """Round-based deliberation: opinions → counter → consensus → tasks.

    Each round:
    1. Build a round-specific prompt for all agents
    2. Send to all agents in parallel (asyncio.gather)
    3. Collect responses → write to shared.md
    4. Check for consensus
    5. If reached, distribute tasks. Otherwise, next round.
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
    ):
        self.agents = agents
        self.shared = shared
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.distributor = distributor or TaskDistributor()
        self.max_rounds = max_rounds
        self.round_timeout = round_timeout
        self.tmux_manager = tmux_manager

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

            # Update tmux pane titles to show round progress
            self._update_pane_titles(f"Round {round_num}/{self.max_rounds}")

            # Build prompt for this round
            round_prompt = self._build_round_prompt(round_num, user_prompt)

            # Collect opinions from all agents in parallel
            opinions = await self._collect_opinions(round_num, round_prompt)

            # Write opinions to shared.md
            for name, msg in opinions.items():
                self.shared.append_opinion(name, round_num, msg.content)

            # Update message round_num (it was set to 0 in agent)
            for name, msg in opinions.items():
                msg.round_num = round_num

            # Check consensus
            opinion_texts = {name: msg.content for name, msg in opinions.items()}
            consensus = self.consensus_engine.evaluate(opinion_texts)

            if consensus.reached:
                logger.info(f"Consensus reached at round {round_num}!")
                self.shared.update_consensus(consensus.summary)
                self._update_pane_titles("✓ Consensus!")
                break

            logger.info(f"No consensus yet. Continuing to round {round_num + 1}.")

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
        """Send prompt to all agents in parallel and collect responses."""
        tasks = {
            name: agent.send_and_wait(prompt, timeout=self.round_timeout)
            for name, agent in self.agents.items()
        }

        results = await asyncio.gather(
            *tasks.values(), return_exceptions=True
        )

        opinions: dict[str, DeliberationMessage] = {}
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"[{name}] Error in round {round_num}: {result}")
                opinions[name] = DeliberationMessage(
                    source=name,
                    target="all",
                    round_num=round_num,
                    role=MessageRole.OPINION,
                    content=f"[Error: {result}]",
                )
            elif isinstance(result, DeliberationMessage):
                result.round_num = round_num
                opinions[name] = result
            else:
                logger.warning(f"[{name}] Unexpected result type: {type(result)}")

        return opinions

    def _build_round_prompt(self, round_num: int, user_prompt: str) -> str:
        """Build the prompt for a specific deliberation round."""
        if round_num == 1:
            return (
                f"Read the shared context below for background.\n\n"
                f"User's request: {user_prompt}\n\n"
                f"Share your initial opinion. Be specific and concise.\n"
                f"State your recommendation and key reasoning.\n"
                f"Keep your response under 500 words."
            )
        else:
            # Read previous round opinions from shared.md
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
