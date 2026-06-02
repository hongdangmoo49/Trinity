"""Token budget checker — pre-send token estimation."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from trinity.models import AgentSpec, ContextUsage

logger = logging.getLogger(__name__)


@dataclass
class BudgetCheckResult:
    estimated_prompt_tokens: int
    projected_total: int
    projected_ratio: float
    safe: bool
    recommendation: str  # "proceed" | "proceed_with_caution" | "rotate_first"


class TokenBudgetChecker:
    def __init__(self, threshold: float = 0.60, safety_margin: float = 0.05):
        self.threshold = threshold
        self.safety_margin = safety_margin

    # Tokens-per-character ratio.  Conservative upper bound:
    # real English is ~0.25 tok/char, but budget checks should over-estimate
    # to account for system-prompt wrapping, formatting markers, and
    # conversation history that the host may inject.
    _TOK_PER_CHAR: float = 1.6

    def estimate_prompt_tokens(self, prompt: str) -> int:
        """Conservative token estimate for a prompt string.

        Uses a generous per-character ratio so that budget checks err on
        the side of caution — over-estimating is always safer than
        under-estimating when guarding against context overflow.
        """
        if not prompt:
            return 0
        return int(len(prompt) * self._TOK_PER_CHAR)

    def check(
        self, prompt: str, current_usage: ContextUsage, agent_spec: AgentSpec
    ) -> BudgetCheckResult:
        est = self.estimate_prompt_tokens(prompt)
        projected = current_usage.used + est
        ratio = projected / current_usage.total if current_usage.total > 0 else 0.0
        warn = self.threshold - self.safety_margin

        if ratio >= self.threshold:
            safe, rec = False, "rotate_first"
        elif ratio >= warn:
            safe, rec = True, "proceed_with_caution"
        else:
            safe, rec = True, "proceed"

        if not safe:
            logger.warning(
                f"[{agent_spec.name}] Budget check FAILED: projected {ratio:.0%}"
            )

        return BudgetCheckResult(est, projected, ratio, safe, rec)
