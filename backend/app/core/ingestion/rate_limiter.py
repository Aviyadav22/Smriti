"""Token-bucket rate limiter for API calls during bulk ingestion.

Prevents exceeding Gemini API quotas (e.g. 60 RPM on free tier) when
running multiple concurrent ingestion workers. Supports per-key tracking
so that each API key gets its own independent rate limit.

Usage:
    limiter = AsyncRateLimiter(max_per_minute=30)
    async with limiter:
        await call_gemini_api(...)

    # Or with explicit acquire/release:
    await limiter.acquire()
    try:
        await call_gemini_api(...)
    finally:
        limiter.release()

    # Per-key limiters for key rotation:
    pool = RateLimiterPool(rpm_per_key=30)
    async with pool.get("api-key-1"):
        await call_gemini_api(...)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

logger = logging.getLogger(__name__)


class AsyncRateLimiter:
    """Token-bucket style async rate limiter.

    Tracks timestamps of recent calls and blocks ``acquire()`` until
    a request slot is available within the configured window.

    Thread-safe for asyncio (single event loop) via asyncio.Lock.
    """

    def __init__(self, max_per_minute: int = 30) -> None:
        if max_per_minute <= 0:
            raise ValueError("max_per_minute must be positive")
        self._max_per_minute = max_per_minute
        self._window: float = 60.0  # seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    @property
    def max_per_minute(self) -> int:
        return self._max_per_minute

    async def acquire(self) -> None:
        """Wait until a request slot is available within the rate window.

        This method blocks (via asyncio.sleep) until enough time has passed
        for a new request to fit within the max_per_minute limit.
        """
        while True:
            async with self._lock:
                now = time.monotonic()
                # Purge timestamps outside the window
                while self._timestamps and (now - self._timestamps[0]) >= self._window:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._max_per_minute:
                    self._timestamps.append(now)
                    return

                # Calculate how long to wait for the oldest request to expire
                oldest = self._timestamps[0]
                wait_time = self._window - (now - oldest) + 0.01  # small buffer

            logger.debug(
                "Rate limit reached (%d/%d RPM), waiting %.1fs",
                len(self._timestamps),
                self._max_per_minute,
                wait_time,
            )
            await asyncio.sleep(wait_time)

    def release(self) -> None:
        """No-op for compatibility; slots expire automatically by time."""

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: type | None, exc: BaseException | None, tb: object) -> None:
        self.release()


class RateLimiterPool:
    """Manages per-key rate limiters for API key rotation.

    Each API key gets its own ``AsyncRateLimiter`` instance so that
    multiple keys can operate at their individual rate limits.

    Usage:
        pool = RateLimiterPool(rpm_per_key=30)
        async with pool.get(api_key):
            await call_api(...)
    """

    def __init__(self, rpm_per_key: int = 30) -> None:
        if rpm_per_key <= 0:
            raise ValueError("rpm_per_key must be positive")
        self._rpm_per_key = rpm_per_key
        self._limiters: dict[str, AsyncRateLimiter] = {}

    def get(self, key: str) -> AsyncRateLimiter:
        """Get or create a rate limiter for the given API key."""
        if key not in self._limiters:
            self._limiters[key] = AsyncRateLimiter(max_per_minute=self._rpm_per_key)
            logger.info(
                "Created rate limiter for key ...%s (%d RPM)",
                key[-4:] if len(key) >= 4 else "****",
                self._rpm_per_key,
            )
        return self._limiters[key]

    @property
    def rpm_per_key(self) -> int:
        return self._rpm_per_key
