"""Tests for trinity.retry — RetryConfig."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock

from trinity.retry import RetryConfig


@pytest.fixture
def config():
    return RetryConfig(max_retries=3, base_delay=0.01, max_delay=0.1, jitter=False)


# ===========================================================================
# Delay calculation
# ===========================================================================

class TestGetDelay:
    def test_first_attempt(self, config):
        delay = config.get_delay(0)
        assert delay == pytest.approx(0.01, abs=0.001)

    def test_exponential_backoff(self, config):
        d0 = config.get_delay(0)
        d1 = config.get_delay(1)
        d2 = config.get_delay(2)
        assert d1 > d0
        assert d2 > d1

    def test_capped_at_max_delay(self):
        cfg = RetryConfig(base_delay=10.0, max_delay=5.0, backoff_factor=2.0)
        assert cfg.get_delay(10) <= 5.0

    def test_jitter_adds_variance(self):
        cfg = RetryConfig(base_delay=1.0, jitter=True)
        delays = [cfg.get_delay(0) for _ in range(100)]
        # With jitter, not all delays should be identical
        assert len(set(round(d, 4) for d in delays)) > 1


# ===========================================================================
# should_retry
# ===========================================================================

class TestShouldRetry:
    def test_retry_on_exit_code_429(self, config):
        assert config.should_retry(exit_code=429) is True

    def test_retry_on_exit_code_503(self, config):
        assert config.should_retry(exit_code=503) is True

    def test_no_retry_on_exit_code_0(self, config):
        assert config.should_retry(exit_code=0) is False

    def test_no_retry_on_exit_code_1(self, config):
        assert config.should_retry(exit_code=1) is False

    def test_retry_on_rate_limit_pattern(self, config):
        assert config.should_retry(output="Error: rate limit exceeded") is True

    def test_retry_on_timeout_pattern(self, config):
        assert config.should_retry(output="connection timeout after 30s") is True

    def test_no_retry_on_unrelated_output(self, config):
        assert config.should_retry(output="syntax error in function") is False

    def test_retry_on_connection_error(self, config):
        assert config.should_retry(exception=ConnectionError("refused")) is True

    def test_retry_on_timeout_error(self, config):
        assert config.should_retry(exception=TimeoutError("timed out")) is True

    def test_no_retry_on_value_error(self, config):
        assert config.should_retry(exception=ValueError("bad input")) is False

    def test_custom_exit_codes(self):
        cfg = RetryConfig(retry_on_exit_codes=[99])
        assert cfg.should_retry(exit_code=99) is True
        assert cfg.should_retry(exit_code=429) is False

    def test_custom_patterns(self):
        cfg = RetryConfig(retry_on_patterns=["custom error"])
        assert cfg.should_retry(output="custom error occurred") is True
        assert cfg.should_retry(output="rate limit") is False


# ===========================================================================
# run_with_retry (async)
# ===========================================================================

class TestRunWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self, config):
        fn = AsyncMock(return_value="ok")
        result = await config.run_with_retry(fn)
        assert result == "ok"
        assert fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_error(self, config):
        fn = AsyncMock(side_effect=[ConnectionError("fail"), "ok"])
        result = await config.run_with_retry(fn)
        assert result == "ok"
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_non_retryable(self, config):
        fn = AsyncMock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError, match="bad"):
            await config.run_with_retry(fn)

    @pytest.mark.asyncio
    async def test_exhausts_retries(self, config):
        fn = AsyncMock(side_effect=ConnectionError("down"))
        with pytest.raises(ConnectionError):
            await config.run_with_retry(fn)
        # max_retries=3 + 1 initial = 4 calls
        assert fn.call_count == 4

    @pytest.mark.asyncio
    async def test_passes_args(self, config):
        fn = AsyncMock(return_value="ok")
        await config.run_with_retry(fn, "arg1", key="val")
        fn.assert_called_with("arg1", key="val")


# ===========================================================================
# run_with_retry_sync
# ===========================================================================

class TestRunWithRetrySync:
    def test_succeeds_first_try(self, config):
        call_count = 0
        def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = config.run_with_retry_sync(fn)
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_retryable(self, config):
        attempts = []
        def fn():
            attempts.append(1)
            if len(attempts) < 2:
                raise ConnectionError("fail")
            return "ok"

        result = config.run_with_retry_sync(fn)
        assert result == "ok"
        assert len(attempts) == 2

    def test_raises_non_retryable(self, config):
        def fn():
            raise ValueError("bad")

        with pytest.raises(ValueError):
            config.run_with_retry_sync(fn)
