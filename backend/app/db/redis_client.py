"""Async Redis client singleton."""

import asyncio
import logging

import redis.asyncio as aioredis
from redis.exceptions import AuthenticationError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None
_redis_lock = asyncio.Lock()


async def get_redis() -> aioredis.Redis | None:
    global _redis_client
    if not settings.redis_url:
        return None
    if _redis_client is not None:
        return _redis_client
    async with _redis_lock:
        # Double-check after acquiring lock
        if _redis_client is not None:
            return _redis_client
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            # Verify connection works (fail fast instead of crashing on first use)
            await client.ping()
            _redis_client = client
        except (RedisConnectionError, RedisTimeoutError, AuthenticationError, OSError) as exc:
            logger.error("Redis connection failed: %s", exc)
            return None
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
