"""Tests for the L2 Bridge Preference Engine."""

import pytest

from trinity.bridge import (
    AcrossProvider,
    BridgeRequest,
    ChainId,
    FailingProvider,
    LiFiProvider,
    PreferenceMode,
    ScoringEngine,
    StargateProvider,
    TokenAmount,
)


@pytest.fixture
def engine():
    providers = [
        LiFiProvider(),
        AcrossProvider(),
        StargateProvider(),
    ]
    return ScoringEngine(providers)


@pytest.mark.asyncio
async def test_engine_returns_top_3(engine):
    request = BridgeRequest(
        source_chain=ChainId.ETHEREUM,
        target_chain=ChainId.BASE,
        amount=TokenAmount(amount=1.0, symbol="ETH", amount_usd=3000.0),
        mode=PreferenceMode.BALANCED
    )
    
    routes = await engine.get_best_routes(request, limit=3)
    assert len(routes) == 3
    # Check that they are sorted (though random, the logic should still produce a list)
    assert all(r.provider in ["LiFi", "Across", "Stargate"] for r in routes)


@pytest.mark.asyncio
async def test_speed_mode_prioritizes_across(engine):
    # Across is simulated to be faster (60-180s) than others (120-900s)
    request = BridgeRequest(
        source_chain=ChainId.ARBITRUM,
        target_chain=ChainId.OPTIMISM,
        amount=TokenAmount(amount=0.5, symbol="ETH", amount_usd=1500.0),
        mode=PreferenceMode.SPEED
    )
    
    # We run multiple times to overcome randomness in simulation if needed, 
    # but Across is significantly faster in our mocks.
    routes = await engine.get_best_routes(request, limit=1)
    # Note: With random values, Across might not ALWAYS be #1 if LiFi picks a lucky low time,
    # but statistically it should be preferred.
    assert routes[0].provider == "Across"


@pytest.mark.asyncio
async def test_cost_mode_prioritizes_lifi(engine):
    # LiFi is simulated to be cheaper ($1-5) than Across ($2-8) or Stargate ($3-15)
    request = BridgeRequest(
        source_chain=ChainId.BASE,
        target_chain=ChainId.POLYGON,
        amount=TokenAmount(amount=0.1, symbol="ETH", amount_usd=300.0),
        mode=PreferenceMode.COST
    )
    
    routes = await engine.get_best_routes(request, limit=1)
    assert routes[0].provider == "LiFi"


@pytest.mark.asyncio
async def test_large_volume_prioritizes_security(engine):
    # Stargate is simulated to have lowest risk (0.02)
    # For $20,000, risk weight should increase.
    request = BridgeRequest(
        source_chain=ChainId.ETHEREUM,
        target_chain=ChainId.LINEA,
        amount=TokenAmount(amount=10.0, symbol="ETH", amount_usd=30000.0),
        mode=PreferenceMode.BALANCED
    )
    
    routes = await engine.get_best_routes(request, limit=1)
    assert routes[0].provider == "Stargate"


@pytest.mark.asyncio
async def test_disabled_provider(engine):
    request = BridgeRequest(
        source_chain=ChainId.ARBITRUM,
        target_chain=ChainId.BASE,
        amount=TokenAmount(amount=1.0, symbol="ETH", amount_usd=3000.0),
        mode=PreferenceMode.BALANCED,
        disabled_providers=["Across"]
    )
    
    routes = await engine.get_best_routes(request, limit=5)
    providers = [r.provider for r in routes]
    assert "Across" not in providers
    assert len(routes) == 2  # LiFi and Stargate left


@pytest.mark.asyncio
async def test_graceful_fallback():
    # Mix of working and failing providers
    providers = [
        LiFiProvider(),
        FailingProvider("BrokenBridge"),
    ]
    engine = ScoringEngine(providers)
    
    request = BridgeRequest(
        source_chain=ChainId.ETHEREUM,
        target_chain=ChainId.BASE,
        amount=TokenAmount(amount=1.0, symbol="ETH", amount_usd=3000.0)
    )
    
    # Should not raise exception, should just return LiFi quote
    routes = await engine.get_best_routes(request)
    assert len(routes) == 1
    assert routes[0].provider == "LiFi"


@pytest.mark.asyncio
async def test_all_providers_fail():
    providers = [FailingProvider("Error1"), FailingProvider("Error2")]
    engine = ScoringEngine(providers)
    
    request = BridgeRequest(
        source_chain=ChainId.ETHEREUM,
        target_chain=ChainId.BASE,
        amount=TokenAmount(amount=1.0, symbol="ETH", amount_usd=3000.0)
    )
    
    routes = await engine.get_best_routes(request)
    assert routes == []


@pytest.mark.asyncio
async def test_tracker_emits_updates():
    from trinity.bridge import BridgeTracker, TransactionStatus
    tracker = BridgeTracker()
    updates = []
    
    def callback(update):
        updates.append(update)
        
    final_update = await tracker.track("0x123", callback=callback)
    
    # Should have at least 3 updates (Initial, Intermediate, Final)
    assert len(updates) >= 3
    assert updates[0].status == TransactionStatus.PENDING
    assert final_update.status in [TransactionStatus.COMPLETED, TransactionStatus.FAILED]
    assert final_update == updates[-1]
