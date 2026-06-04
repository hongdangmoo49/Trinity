"""Scoring engine for bridge route optimization."""

import asyncio
import logging
from typing import List, Dict, Optional
from trinity.bridge.models import (
    BridgeRequest,
    BridgeRouteQuote,
    PreferenceMode,
)
from trinity.bridge.providers import BridgeProvider

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Optimizes bridge routes based on user preference and transaction volume."""

    # Threshold for "large" transactions where security/liquidity matters more than cost
    LARGE_AMOUNT_THRESHOLD_USD = 10000.0

    def __init__(self, providers: List[BridgeProvider]):
        self.providers = providers

    async def get_best_routes(self, request: BridgeRequest, limit: int = 3) -> List[BridgeRouteQuote]:
        """Fetch, score, and rank bridge routes."""
        # 1. Fetch quotes concurrently
        tasks = []
        for provider in self.providers:
            if provider.name not in request.disabled_providers:
                tasks.append(self._safe_get_quote(provider, request))

        quotes = await asyncio.gather(*tasks)
        valid_quotes = [q for q in quotes if q is not None]

        if not valid_quotes:
            logger.warning("No valid bridge quotes found.")
            return []

        # 2. Score quotes
        scored_quotes = []
        weights = self._get_weights(request)

        for quote in valid_quotes:
            score = self._calculate_score(quote, weights)
            scored_quotes.append((score, quote))

        # 3. Sort (lower score is better) and return top N
        scored_quotes.sort(key=lambda x: x[0])
        return [q for _, q in scored_quotes[:limit]]

    async def _safe_get_quote(self, provider: BridgeProvider, request: BridgeRequest) -> Optional[BridgeRouteQuote]:
        """Fetch quote with error handling for graceful fallback."""
        try:
            return await provider.get_quote(request)
        except Exception as e:
            logger.error(f"Provider {provider.name} failed: {e}")
            return None

    def _get_weights(self, request: BridgeRequest) -> Dict[str, float]:
        """Determine scoring weights based on mode and amount."""
        # Base weights for modes
        if request.mode == PreferenceMode.SPEED:
            weights = {"fee": 0.2, "time": 0.7, "risk": 0.1}
        elif request.mode == PreferenceMode.COST:
            weights = {"fee": 0.7, "time": 0.2, "risk": 0.1}
        else:  # BALANCED
            weights = {"fee": 0.4, "time": 0.4, "risk": 0.2}

        # Volume-based adjustment
        if request.amount.amount_usd >= self.LARGE_AMOUNT_THRESHOLD_USD:
            # For large amounts, risk becomes the primary concern
            # liquidity is implicitly tied to risk/provider choice in this model
            weights["risk"] += 0.5
            weights["fee"] -= 0.25
            weights["time"] -= 0.25

            # Ensure no negative weights
            for k in weights:
                weights[k] = max(0.01, weights[k])

            # Re-normalize
            total = sum(weights.values())
            for k in weights:
                weights[k] /= total

        return weights

    def _calculate_score(self, quote: BridgeRouteQuote, weights: Dict[str, float]) -> float:
        """
        Calculate a heuristic score for a quote.
        Lower is better.
        Normalizes values roughly for comparison.
        """
        # Roughly normalize fee (expecting $1 - $50 range)
        norm_fee = quote.fee_usd / 10.0

        # Roughly normalize time (expecting 60s - 1800s range)
        # Use log or capped normalization to prevent extreme slowness from dominating too much
        norm_time = min(quote.estimated_time_sec / 300.0, 5.0)

        # Risk is 0.0 to 1.0. We multiply by a large factor so it can truly dominate.
        norm_risk = quote.risk_score * 50.0

        score = (
            norm_fee * weights["fee"] +
            norm_time * weights["time"] +
            norm_risk * weights["risk"]
        )
        return score
