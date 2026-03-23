"""Async Redis client singleton."""

import logging

import redis.asyncio as aioredis
from redis.exceptions import AuthenticationError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    global _redis_client
    if not settings.redis_url:
        return None
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.redis_url, decode_responses=True
            )
            # Verify connection works (fail fast instead of crashing on first use)
            await _redis_client.ping()
        except (RedisConnectionError, RedisTimeoutError, AuthenticationError, OSError) as exc:
            logger.error("Redis connection failed: %s", exc)
            _redis_client = None
            return None
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
