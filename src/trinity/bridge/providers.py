"""Bridge provider adapters for quote aggregation."""

import abc
import asyncio
import random
from typing import Optional
from trinity.bridge.models import (
    BridgeRequest,
    BridgeRouteQuote,
    TokenAmount,
)


class BridgeProvider(abc.ABC):
    """Base class for bridge provider adapters."""

    def __init__(self, name: str):
        self.name = name

    @abc.abstractmethod
    async def get_quote(self, request: BridgeRequest) -> Optional[BridgeRouteQuote]:
        """Fetch a quote for the given request."""
        pass


class LiFiProvider(BridgeProvider):
    """LiFi bridge aggregator adapter."""

    def __init__(self):
        super().__init__("LiFi")

    async def get_quote(self, request: BridgeRequest) -> Optional[BridgeRouteQuote]:
        await asyncio.sleep(random.uniform(0.1, 0.2))

        # LiFi: Cheapest, Slow, Risky
        fee_usd = 1.0
        time_sec = 1000
        risk = 0.5

        output_amount = TokenAmount(
            amount=request.amount.amount * 0.998,
            symbol=request.amount.symbol,
            amount_usd=request.amount.amount_usd - fee_usd
        )

        return BridgeRouteQuote(
            provider=self.name,
            source_chain=request.source_chain,
            target_chain=request.target_chain,
            input_amount=request.amount,
            output_amount=output_amount,
            fee_usd=fee_usd,
            estimated_time_sec=time_sec,
            risk_score=risk
        )


class AcrossProvider(BridgeProvider):
    """Across protocol adapter — known for speed."""

    def __init__(self):
        super().__init__("Across")

    async def get_quote(self, request: BridgeRequest) -> Optional[BridgeRouteQuote]:
        await asyncio.sleep(random.uniform(0.05, 0.1))

        # Across: Moderate Cost, Fastest, Risky
        fee_usd = 10.0
        time_sec = 60
        risk = 0.5

        output_amount = TokenAmount(
            amount=request.amount.amount * 0.999,
            symbol=request.amount.symbol,
            amount_usd=request.amount.amount_usd - fee_usd
        )

        return BridgeRouteQuote(
            provider=self.name,
            source_chain=request.source_chain,
            target_chain=request.target_chain,
            input_amount=request.amount,
            output_amount=output_amount,
            fee_usd=fee_usd,
            estimated_time_sec=time_sec,
            risk_score=risk
        )


class StargateProvider(BridgeProvider):
    """Stargate protocol adapter — known for native assets and liquidity."""

    def __init__(self):
        super().__init__("Stargate")

    async def get_quote(self, request: BridgeRequest) -> Optional[BridgeRouteQuote]:
        await asyncio.sleep(random.uniform(0.1, 0.2))

        # Stargate: Most Expensive, Very Slow, Safest
        fee_usd = 50.0
        time_sec = 2000
        risk = 0.01

        output_amount = TokenAmount(
            amount=request.amount.amount * 0.997,
            symbol=request.amount.symbol,
            amount_usd=request.amount.amount_usd - fee_usd
        )

        return BridgeRouteQuote(
            provider=self.name,
            source_chain=request.source_chain,
            target_chain=request.target_chain,
            input_amount=request.amount,
            output_amount=output_amount,
            fee_usd=fee_usd,
            estimated_time_sec=time_sec,
            risk_score=risk
        )


class FailingProvider(BridgeProvider):
    """A provider that always fails, used for testing graceful fallback."""

    def __init__(self, name: str = "FailingBridge"):
        super().__init__(name)

    async def get_quote(self, request: BridgeRequest) -> Optional[BridgeRouteQuote]:
        await asyncio.sleep(0.1)
        raise RuntimeError(f"Provider {self.name} is currently unavailable")
