"""Redis-backed rate limiting for FastAPI endpoints.

Provides a sliding-window rate limiter using Redis and a FastAPI dependency
factory that parses human-readable rate limit strings (e.g., "100/minute").
"""

import logging
from collections.abc import Callable, Coroutine
from typing import Any

import redis.asyncio as aioredis
from fastapi import Request

from app.security.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Time unit mappings
# ---------------------------------------------------------------------------

_TIME_UNITS: dict[str, int] = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 3600,
    "hours": 3600,
    "day": 86400,
    "days": 86400,
}


# ---------------------------------------------------------------------------
# Rate limiter class
# ---------------------------------------------------------------------------


class RateLimiter:
    """Sliding-window rate limiter backed by Redis sorted sets.

    Uses a sorted-set-based sliding window algorithm:
    1. Remove expired entries outside the current window.
    2. Count remaining entries.
    3. If under the limit, add the current request timestamp.
    4. Set a TTL on the key equal to the window size.
    """

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        """Check whether a request is within the rate limit.

        Args:
            key: Unique identifier for the rate limit bucket
                (e.g., ``"rate:user:123:search"``).
            limit: Maximum number of requests allowed in the window.
            window_seconds: Size of the sliding window in seconds.

        Returns:
            True if the request is allowed, False if the rate limit
            has been exceeded.
        """
        import time

        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()

        # Remove entries outside the current window
        pipe.zremrangebyscore(key, 0, window_start)

        # Count remaining entries in the window
        pipe.zcard(key)

        # Add the current request
        pipe.zadd(key, {f"{now}": now})

        # Set TTL to auto-expire the key
        pipe.expire(key, window_seconds)

        results: list[int] = await pipe.execute()
        current_count: int = results[1]

        # If current count (before adding this request) >= limit, deny
        if current_count >= limit:
            # Remove the entry we just added since we're denying
            await self._redis.zrem(key, f"{now}")
            return False

        return True


# ---------------------------------------------------------------------------
# Singleton Redis client and rate limiter
# ---------------------------------------------------------------------------

_rate_limiter: RateLimiter | None = None


async def _get_rate_limiter() -> RateLimiter:
    """Get or create the singleton rate limiter instance using shared Redis."""
    global _rate_limiter

    if _rate_limiter is None:
        from app.db.redis_client import get_redis
        redis_client = await get_redis()
        if redis_client is None:
            raise RuntimeError("Redis is not available for rate limiting")
        _rate_limiter = RateLimiter(redis_client)

    return _rate_limiter


# ---------------------------------------------------------------------------
# In-memory fallback for when Redis is unavailable
# ---------------------------------------------------------------------------

import threading
import time as _time

_mem_lock = threading.Lock()
_mem_buckets: dict[str, list[float]] = {}


def _in_memory_check(key: str, limit: int, window_seconds: int) -> bool:
    """Simple in-memory sliding window fallback when Redis is down."""
    now = _time.time()
    with _mem_lock:
        if len(_mem_buckets) > 10000:
            _mem_buckets.clear()
        entries = _mem_buckets.get(key, [])
        # Prune expired entries
        entries = [t for t in entries if t > now - window_seconds]
        if len(entries) >= limit:
            _mem_buckets[key] = entries
            return False
        entries.append(now)
        _mem_buckets[key] = entries
        return True


# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------


def _parse_rate_limit(limit_str: str) -> tuple[int, int]:
    """Parse a rate limit string like ``"100/minute"`` into (count, seconds).

    Args:
        limit_str: Human-readable rate limit (e.g., ``"60/minute"``,
            ``"5/hour"``).

    Returns:
        Tuple of (max_requests, window_seconds).

    Raises:
        ValueError: If the format is invalid.
    """
    parts = limit_str.strip().split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid rate limit format: '{limit_str}'. "
            "Expected format: '<count>/<unit>' (e.g., '100/minute')"
        )

    count_str, unit = parts[0].strip(), parts[1].strip().lower()

    try:
        count = int(count_str)
    except ValueError:
        raise ValueError(
            f"Invalid request count in rate limit: '{count_str}'"
        )

    if unit not in _TIME_UNITS:
        raise ValueError(
            f"Unknown time unit '{unit}'. "
            f"Valid units: {', '.join(_TIME_UNITS.keys())}"
        )

    return count, _TIME_UNITS[unit]


def rate_limit_dependency(
    limit: str,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Create a FastAPI dependency that enforces a rate limit.

    Usage::

        @router.get("/search", dependencies=[Depends(rate_limit_dependency("60/minute"))])
        async def search(...):
            ...

    Args:
        limit: Human-readable rate limit string (e.g., ``"100/minute"``).

    Returns:
        An async FastAPI dependency function.
    """
    max_requests, window_seconds = _parse_rate_limit(limit)

    async def _check_rate(request: Request) -> None:
        # Build key before try block so it's available in the except fallback
        # Read X-Forwarded-For for real client IP behind Cloud Run / nginx proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        key = f"rate:{client_ip}:{endpoint}"

        try:
            limiter = await _get_rate_limiter()
            allowed = await limiter.check_rate_limit(key, max_requests, window_seconds)
            if not allowed:
                raise RateLimitExceededError(
                    detail=f"Rate limit exceeded: {limit}",
                    retry_after=window_seconds,
                )
        except RateLimitExceededError:
            raise
        except Exception as exc:
            # Redis unavailable — fall back to in-memory rate limiting.
            # Per-instance limits are imperfect but better than dropping all traffic.
            logger.warning("Rate limiter Redis unavailable, using in-memory fallback: %s", exc)
            if not _in_memory_check(key, max_requests, window_seconds):
                raise RateLimitExceededError(
                    detail=f"Rate limit exceeded: {limit}",
                    retry_after=window_seconds,
                )

    return _check_rate
