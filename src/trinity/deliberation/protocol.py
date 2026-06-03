"""Deliberation protocol — round-based deliberation loop."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from trinity.agents.base import AgentWrapper
from trinity.context.analytics import TokenAnalytics, RoundRecord
from trinity.context.budget import BudgetCheckResult, TokenBudgetChecker
from trinity.context.compressor import PromptCompressor
from trinity.context.shared import SharedContextEngine
from trinity.deliberation.consensus import ConsensusEngine
from trinity.deliberation.distributor import TaskDistributor
from trinity.models import (
    AgentResponse,
    ConsensusResult,
    ContextUsage,
    DeliberationMessage,
    DeliberationResult,
    MessageRole,
    ResponseStatus,
)
from trinity.tui.events import TUIEvent, TUIEventType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoundBudgetWarning:
    """Structured budget readiness warning captured before a round prompt is sent."""

    agent_name: str
    round_num: int
    estimated_prompt_tokens: int
    current_used: int
    context_total: int
    projected_total: int
    projected_ratio: float
    safe: bool
    recommendation: str


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
        caveman_mode: bool = True,
        caveman_intensity: str = "full",
        lang: str = "en",
        analytics_path: Path | None = None,
        response_artifact_dir: Path | None = None,
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
        self.caveman_mode = caveman_mode
        self.caveman_intensity = caveman_intensity
        self.lang = lang
        if compression_enabled:
            self.compressor = PromptCompressor(
                max_summary_tokens=compression_max_summary_tokens,
            )
        self.compression_round_threshold = compression_round_threshold
        self.budget_checker = TokenBudgetChecker()
        self.budget_warnings: list[RoundBudgetWarning] = []
        self.last_round_budget_warnings: list[RoundBudgetWarning] = []
        self.rotation_candidates: list[RoundBudgetWarning] = []
        self.last_round_rotation_candidates: list[RoundBudgetWarning] = []

        # Token usage analytics
        self.analytics = TokenAnalytics(history_path=analytics_path)
        self.response_artifact_dir = response_artifact_dir or (
            shared.path.parent / "responses"
        )

    def _emit(self, event_type: TUIEventType, **kwargs) -> None:
        """Emit a TUI event if callback is registered."""
        if self._event_callback:
            self._event_callback(TUIEvent(type=event_type, data=kwargs))

    def get_rotation_candidates(self) -> list[RoundBudgetWarning]:
        """Return agents whose pre-send budget check recommended rotation."""
        return list(self.rotation_candidates)

    def get_agents_needing_rotation(self) -> list[RoundBudgetWarning]:
        """Return latest round agents that should rotate before another prompt."""
        return list(self.last_round_rotation_candidates)

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
            await self._update_pane_titles(f"Round {round_num}/{self.max_rounds}")

            # Build prompt for this round
            round_prompt = self._build_round_prompt(round_num, user_prompt)

            # Collect opinions from all agents (with per-agent streaming)
            opinions = await self._collect_opinions(round_num, round_prompt)

            # Write opinions to shared.md
            for name, msg in opinions.items():
                if self._is_unusable_agent_response(msg):
                    continue
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

            opinion_texts = {
                name: msg.content
                for name, msg in opinions.items()
                if not self._is_unusable_agent_response(msg)
            }
            consensus = self.consensus_engine.evaluate(opinion_texts)

            if consensus.reached:
                logger.info(f"Consensus reached at round {round_num}!")
                self.shared.update_consensus(consensus.summary)
                await self._update_pane_titles("✓ Consensus!")

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
                summary=consensus.summary,
                round_num=round_num,
            )

        # Update pane titles for task distribution phase
        await self._update_pane_titles("Distributing tasks...")

        # If no consensus after all rounds, keep that semantic state explicit.
        if consensus and not consensus.reached:
            logger.warning(
                f"Max rounds ({self.max_rounds}) reached without consensus."
            )
            if consensus.total_agents == 0:
                summary = (
                    f"No usable consensus after {self.max_rounds} rounds. "
                    "All agent responses were invalid, empty, timed out, or unavailable."
                )
            else:
                summary = (
                    f"Consensus not reached after {self.max_rounds} rounds "
                    f"({consensus.agreement_count}/{consensus.total_agents} usable "
                    "opinions agreed). No majority consensus was selected."
                )
            consensus = ConsensusResult(
                reached=False,
                agreement_count=consensus.agreement_count,
                total_agents=consensus.total_agents,
                opinions=consensus.opinions,
                summary=summary,
            )

        # Distribute tasks only when there is an actual agreed conclusion.
        tasks = []
        if consensus and consensus.reached:
            tasks = self.distributor.distribute(
                consensus_text=consensus.summary,
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
        self._check_round_budgets(round_num, prompt)

        # Create tasks with agent names attached
        pending: set[asyncio.Task] = set()
        task_to_name: dict[asyncio.Task, str] = {}
        task_to_request_id: dict[asyncio.Task, str] = {}

        for name, agent in self.agents.items():
            request_id = self._new_request_id(round_num, name)
            request_prompt = self._wrap_request_prompt(prompt, request_id)
            coro = agent.send_and_wait(request_prompt, timeout=self.round_timeout)
            task = asyncio.ensure_future(coro)
            task_to_name[task] = name
            task_to_request_id[task] = request_id
            pending.add(task)
            self._emit(TUIEventType.AGENT_THINKING, agent=name, round_num=round_num)

        opinions: dict[str, DeliberationMessage] = {}

        try:
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )

                for task in done:
                    name = task_to_name[task]
                    request_id = task_to_request_id.get(
                        task,
                        self._new_request_id(round_num, name),
                    )
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
                            metadata={
                                "invalid_response": True,
                                "response_validation": {
                                    "usable": False,
                                    "classification": "agent_error",
                                    "reasons": [str(exc)],
                                },
                            },
                        )
                        opinions[name].metadata["request_id"] = request_id
                        self._attach_agent_response_contract(
                            agent_name=name,
                            round_num=round_num,
                            msg=opinions[name],
                            status=ResponseStatus.INVALID,
                            clean_content=opinions[name].content,
                            diagnostics=[str(exc)],
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
                        result.metadata["request_id"] = request_id
                        result = self._validate_agent_response(name, round_num, result)
                        opinions[name] = result
                        self._emit(
                            TUIEventType.AGENT_RESPONDED,
                            agent=name,
                            content=result.content,
                            metadata=dict(result.metadata),
                            response_status=self._response_status(result),
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
        except asyncio.CancelledError:
            # Clean up pending tasks to prevent leaks
            all_tasks = set(task_to_name.keys())
            for t in pending | all_tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(
                *(t for t in all_tasks if not t.done()),
                return_exceptions=True,
            )
            raise

        return opinions

    @staticmethod
    def _new_request_id(round_num: int, agent_name: str) -> str:
        """Create a request id that is stable enough for artifact lookup."""
        safe_agent = re.sub(r"[^A-Za-z0-9_.-]+", "-", agent_name).strip("-")
        return f"round-{round_num}-{safe_agent}-{uuid4().hex[:12]}"

    @staticmethod
    def _wrap_request_prompt(prompt: str, request_id: str) -> str:
        """Wrap a prompt with explicit request boundary markers."""
        return (
            f"TRINITY_REQUEST_START {request_id}\n"
            f"{prompt}\n"
            f"TRINITY_REQUEST_END {request_id}"
        )

    def _validate_agent_response(
        self, agent_name: str, round_num: int, msg: DeliberationMessage
    ) -> DeliberationMessage:
        """Clean and validate a response before TUI/shared-context use."""
        from trinity.agents.response_cleaner import ResponseCleaner

        validation = ResponseCleaner.validate_opinion(msg.content)
        status = self._status_from_validation(msg, validation.classification)
        diagnostics = list(validation.reasons)
        if not diagnostics and not validation.usable:
            diagnostics.append(validation.classification)

        self._attach_agent_response_contract(
            agent_name=agent_name,
            round_num=round_num,
            msg=msg,
            status=status,
            clean_content=validation.cleaned_text,
            diagnostics=diagnostics,
        )
        msg.metadata["response_validation"] = {
            "usable": validation.usable,
            "classification": validation.classification,
            "reasons": list(validation.reasons),
        }
        msg.metadata["response_status"] = status.value

        if validation.usable:
            msg.content = validation.cleaned_text
            return msg

        self.shared.append_invalid_response_diagnostic(
            agent=agent_name,
            round_num=round_num,
            classification=validation.classification,
            reasons=validation.reasons,
            excerpt=validation.raw_excerpt or msg.content,
        )
        msg.metadata["invalid_response"] = True
        msg.content = f"[Invalid response omitted: {validation.classification}]"
        return msg

    def _attach_agent_response_contract(
        self,
        agent_name: str,
        round_num: int,
        msg: DeliberationMessage,
        status: ResponseStatus,
        clean_content: str,
        diagnostics: list[str] | None = None,
    ) -> AgentResponse:
        """Persist raw/clean outputs and attach AgentResponse metadata."""
        request_id = str(
            msg.metadata.get("request_id") or self._new_request_id(round_num, agent_name)
        )
        msg.metadata["request_id"] = request_id

        raw_content = str(msg.metadata.get("raw_output") or msg.content or "")
        raw_path, clean_path = self._write_response_artifacts(
            agent_name=agent_name,
            round_num=round_num,
            request_id=request_id,
            raw_content=raw_content,
            clean_content=clean_content,
        )

        token_usage = self._response_token_usage(agent_name, msg)
        response = AgentResponse(
            agent_name=agent_name,
            request_id=request_id,
            content=clean_content,
            raw_output_path=raw_path,
            clean_output_path=clean_path,
            status=status,
            confidence=self._response_confidence(status),
            token_usage=token_usage,
            diagnostics=list(diagnostics or []),
        )
        msg.metadata["agent_response"] = response.to_metadata()
        msg.metadata["response_status"] = status.value
        return response

    def _write_response_artifacts(
        self,
        agent_name: str,
        round_num: int,
        request_id: str,
        raw_content: str,
        clean_content: str,
    ) -> tuple[Path, Path]:
        safe_agent = re.sub(r"[^A-Za-z0-9_.-]+", "-", agent_name).strip("-")
        safe_request = re.sub(r"[^A-Za-z0-9_.-]+", "-", request_id).strip("-")
        round_dir = self.response_artifact_dir / f"round-{round_num:02d}"
        round_dir.mkdir(parents=True, exist_ok=True)

        raw_path = round_dir / f"{safe_agent}-{safe_request}.raw.txt"
        clean_path = round_dir / f"{safe_agent}-{safe_request}.clean.txt"
        raw_path.write_text(self._safe_artifact_text(raw_content), encoding="utf-8")
        clean_path.write_text(self._safe_artifact_text(clean_content), encoding="utf-8")
        return raw_path, clean_path

    @staticmethod
    def _safe_artifact_text(text: str) -> str:
        return str(text).encode("utf-8", errors="replace").decode("utf-8")

    def _response_token_usage(
        self,
        agent_name: str,
        msg: DeliberationMessage,
    ) -> ContextUsage | None:
        token_count = int(msg.metadata.get("token_count") or 0)
        if token_count <= 0:
            return None
        agent = self.agents.get(agent_name)
        total = agent.context_usage.total if agent else 0
        return ContextUsage(used=token_count, total=total)

    @staticmethod
    def _response_confidence(status: ResponseStatus) -> float:
        if status == ResponseStatus.OK:
            return 1.0
        if status in {
            ResponseStatus.AUTH_REQUIRED,
            ResponseStatus.MODEL_LOADING,
            ResponseStatus.TIMEOUT,
            ResponseStatus.EMPTY,
            ResponseStatus.PROCESS_DEAD,
        }:
            return 0.0
        if status in {ResponseStatus.PROMPT_ECHO, ResponseStatus.CLI_NOISE}:
            return 0.1
        return 0.2

    @staticmethod
    def _status_from_validation(
        msg: DeliberationMessage,
        classification: str,
    ) -> ResponseStatus:
        metadata = msg.metadata
        if metadata.get("error") == "timeout":
            return ResponseStatus.TIMEOUT
        if metadata.get("completed") is False or metadata.get("completion_timeout"):
            return ResponseStatus.TIMEOUT

        status_by_classification = {
            "usable_opinion": ResponseStatus.OK,
            "auth_wait": ResponseStatus.AUTH_REQUIRED,
            "model_loading": ResponseStatus.MODEL_LOADING,
            "empty": ResponseStatus.EMPTY,
            "prompt_echo": ResponseStatus.PROMPT_ECHO,
            "shared_context_echo": ResponseStatus.PROMPT_ECHO,
            "cli_noise": ResponseStatus.CLI_NOISE,
            "thinking_ui": ResponseStatus.CLI_NOISE,
        }
        return status_by_classification.get(classification, ResponseStatus.INVALID)

    @classmethod
    def _is_unusable_agent_response(cls, msg: DeliberationMessage) -> bool:
        """Return whether a message should be excluded from consensus input."""
        return cls._response_status(msg) != "ok"

    @staticmethod
    def _response_status(msg: DeliberationMessage) -> str:
        """Classify response quality for consensus and TUI display."""
        metadata = msg.metadata
        explicit_status = metadata.get("response_status")
        if explicit_status:
            return str(explicit_status)

        if metadata.get("invalid_response"):
            return "invalid_response"

        validation = metadata.get("response_validation")
        if isinstance(validation, dict) and validation.get("usable") is False:
            return str(validation.get("classification") or "invalid_response")

        if metadata.get("error") == "timeout":
            return "timeout"

        if metadata.get("completed") is False:
            return "completion_timeout"

        detector = str(metadata.get("detector", "")).lower()
        if detector == "fallback" or detector.startswith("fallbackchain("):
            return "captured_fallback"

        if not msg.content or not msg.content.strip():
            return "empty"

        return "ok"

    def _check_round_budgets(
        self, round_num: int, prompt: str
    ) -> list[RoundBudgetWarning]:
        """Evaluate all agents' projected context use before sending a round prompt."""
        warnings: list[RoundBudgetWarning] = []
        rotation_candidates: list[RoundBudgetWarning] = []

        for name, agent in self.agents.items():
            usage = agent.context_usage
            result = self.budget_checker.check(
                prompt=prompt,
                current_usage=usage,
                agent_spec=agent.spec,
            )
            warning = self._budget_warning_from_result(
                agent_name=name,
                round_num=round_num,
                result=result,
                current_used=usage.used,
                context_total=usage.total,
            )

            if result.recommendation != "proceed":
                warnings.append(warning)

            if not result.safe:
                rotation_candidates.append(warning)
                logger.warning(
                    "[%s] Round %s prompt projected context at %.0f%% "
                    "(%s/%s tokens; +%s prompt tokens). Rotation should run before "
                    "the next prompt.",
                    name,
                    round_num,
                    result.projected_ratio * 100,
                    result.projected_total,
                    usage.total,
                    result.estimated_prompt_tokens,
                )

        self.last_round_budget_warnings = warnings
        self.budget_warnings.extend(warnings)
        self.last_round_rotation_candidates = rotation_candidates
        self.rotation_candidates.extend(rotation_candidates)
        return rotation_candidates

    @staticmethod
    def _budget_warning_from_result(
        agent_name: str,
        round_num: int,
        result: BudgetCheckResult,
        current_used: int,
        context_total: int,
    ) -> RoundBudgetWarning:
        return RoundBudgetWarning(
            agent_name=agent_name,
            round_num=round_num,
            estimated_prompt_tokens=result.estimated_prompt_tokens,
            current_used=current_used,
            context_total=context_total,
            projected_total=result.projected_total,
            projected_ratio=result.projected_ratio,
            safe=result.safe,
            recommendation=result.recommendation,
        )

    def _build_round_prompt(self, round_num: int, user_prompt: str) -> str:
        """Build the prompt for a specific deliberation round.

        Uses localized templates from i18n.ROUND_PROMPTS when lang is set.
        For rounds >= compression_round_threshold, old rounds are compressed.
        When caveman_mode is active, appends per-turn compression reinforcement.
        """
        from trinity.i18n import get_round_prompt

        if round_num == 1:
            prompt = get_round_prompt("round1_prefix", self.lang, prompt=user_prompt)
            return self._append_caveman(prompt)

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

        round2_prefix = get_round_prompt("round2_plus_prefix", self.lang)

        return self._append_caveman(
            f"Previous round opinions:\n\n"
            f"{prev_context}\n\n"
            f"---\n\n"
            f"{round2_prefix}"
        )

    def _append_caveman(self, prompt: str) -> str:
        """Append caveman compression reinforcement to a prompt."""
        if not self.caveman_mode:
            return prompt
        from trinity.i18n import CAVEMAN_REINFORCEMENT
        reinforcement = CAVEMAN_REINFORCEMENT.get(self.caveman_intensity, "")
        if reinforcement:
            return f"{prompt}\n\n{reinforcement}"
        return prompt

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

    async def _update_pane_titles(self, status_text: str) -> None:
        """Update tmux pane titles to show round progress (Phase 2 feature)."""
        if not self.tmux_manager:
            return

        for name in self.agents:
            pane = self.tmux_manager.get_pane(name)
            if pane:
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "tmux", "select-pane", "-t", pane.pane_id,
                        "-T", f"{name}: {status_text}",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except Exception:
                    pass  # Non-critical — don't fail deliberation for title update
