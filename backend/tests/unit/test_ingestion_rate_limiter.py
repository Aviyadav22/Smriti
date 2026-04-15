"""Tests for the ingestion rate limiter.

Covers AsyncRateLimiter token-bucket behavior (fast acquire, blocking
when limit reached, window expiry) and RateLimiterPool per-key isolation.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.core.ingestion.rate_limiter import AsyncRateLimiter, RateLimiterPool

# ---------------------------------------------------------------------------
# AsyncRateLimiter
# ---------------------------------------------------------------------------


class TestAsyncRateLimiter:
    """Tests for the token-bucket AsyncRateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_under_limit(self) -> None:
        """Requests under the limit should acquire immediately."""
        limiter = AsyncRateLimiter(max_per_minute=10)
        start = time.monotonic()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.monotonic() - start
        # All 10 should complete near-instantly (well under 1s)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_acquire_blocks_at_limit(self) -> None:
        """Once the limit is reached, acquire should block until the window moves."""
        # Use a tiny window via internal override for faster testing
        limiter = AsyncRateLimiter(max_per_minute=3)
        limiter._window = 1.0  # 1-second window instead of 60s

        # Exhaust the limit
        for _ in range(3):
            await limiter.acquire()

        # The 4th call should block until the window expires (~1s)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.9, f"Expected ~1s wait, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """The async context manager should work identically to acquire."""
        limiter = AsyncRateLimiter(max_per_minute=5)
        async with limiter:
            pass  # Should not raise

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self) -> None:
        """Multiple concurrent acquires should not exceed the limit."""
        limiter = AsyncRateLimiter(max_per_minute=5)
        limiter._window = 1.0

        acquired_count = 0

        async def _acquire_one() -> None:
            nonlocal acquired_count
            await limiter.acquire()
            acquired_count += 1

        # Launch 10 concurrent tasks -- only 5 should complete quickly
        tasks = [asyncio.create_task(_acquire_one()) for _ in range(10)]

        # Wait briefly for the fast ones to complete
        await asyncio.sleep(0.2)

        # At most 5 should have acquired within the first window
        assert acquired_count <= 5

        # Clean up: let all tasks finish
        await asyncio.gather(*tasks)
        assert acquired_count == 10

    def test_invalid_max_per_minute(self) -> None:
        """Zero or negative max_per_minute should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            AsyncRateLimiter(max_per_minute=0)
        with pytest.raises(ValueError, match="must be positive"):
            AsyncRateLimiter(max_per_minute=-5)

    @pytest.mark.asyncio
    async def test_release_is_noop(self) -> None:
        """release() should be a no-op (slots expire by time)."""
        limiter = AsyncRateLimiter(max_per_minute=5)
        await limiter.acquire()
        limiter.release()  # Should not raise

    def test_max_per_minute_property(self) -> None:
        """max_per_minute property should return the configured value."""
        limiter = AsyncRateLimiter(max_per_minute=42)
        assert limiter.max_per_minute == 42


# ---------------------------------------------------------------------------
# RateLimiterPool
# ---------------------------------------------------------------------------


class TestRateLimiterPool:
    """Tests for the per-key RateLimiterPool."""

    def test_get_creates_limiter(self) -> None:
        """get() should create a new limiter for an unseen key."""
        pool = RateLimiterPool(rpm_per_key=20)
        limiter = pool.get("key-1")
        assert isinstance(limiter, AsyncRateLimiter)
        assert limiter.max_per_minute == 20

    def test_get_returns_same_limiter(self) -> None:
        """get() with the same key should return the same instance."""
        pool = RateLimiterPool(rpm_per_key=20)
        limiter1 = pool.get("key-1")
        limiter2 = pool.get("key-1")
        assert limiter1 is limiter2

    def test_different_keys_get_different_limiters(self) -> None:
        """Different keys should get independent limiters."""
        pool = RateLimiterPool(rpm_per_key=20)
        limiter1 = pool.get("key-1")
        limiter2 = pool.get("key-2")
        assert limiter1 is not limiter2

    @pytest.mark.asyncio
    async def test_per_key_isolation(self) -> None:
        """Exhausting one key's limit should not affect another key."""
        pool = RateLimiterPool(rpm_per_key=3)
        limiter1 = pool.get("key-1")
        limiter1._window = 1.0
        limiter2 = pool.get("key-2")
        limiter2._window = 1.0

        # Exhaust key-1
        for _ in range(3):
            await limiter1.acquire()

        # key-2 should still be available
        start = time.monotonic()
        await limiter2.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, "key-2 should not be blocked by key-1"

    def test_invalid_rpm(self) -> None:
        """Zero or negative rpm should raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            RateLimiterPool(rpm_per_key=0)

    def test_rpm_per_key_property(self) -> None:
        """rpm_per_key property should return the configured value."""
        pool = RateLimiterPool(rpm_per_key=42)
        assert pool.rpm_per_key == 42
