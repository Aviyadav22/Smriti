"""[S8] Multi-layer research caching for the Research Agent V2 pipeline.

5-layer Redis cache (best-effort — failures fall through to live query):
  L1: Full research memo    — research:memo:{hash}       TTL 24h
  L2: Search result cache   — search:hybrid:{hash}       TTL 1h
  L3: IK API result cache   — ik:search:{hash}           TTL 24h
                               ik:fragment:{doc_id}:{hash}
  L4: Embedding cache        — embed:{hash}               TTL 7d
  L5: Community summary      — community:{id}             TTL 7d
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTLs (seconds)
# ---------------------------------------------------------------------------
MEMO_TTL = 86400        # 24 hours
SEARCH_TTL = 3600       # 1 hour
IK_TTL = 86400          # 24 hours
EMBEDDING_TTL = 604800  # 7 days
COMMUNITY_TTL = 604800  # 7 days


# ---------------------------------------------------------------------------
# Key normalization
# ---------------------------------------------------------------------------

def normalize_cache_key(query: str, **filters: Any) -> str:
    """Normalize query for cache key: lowercase, strip whitespace, sort filters."""
    normalized = query.lower().strip()
    # Sort filter keys for deterministic hashing
    sorted_filters = json.dumps(filters, sort_keys=True, default=str) if filters else ""
    raw = f"{normalized}:{sorted_filters}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# L1: Full research memo cache
# ---------------------------------------------------------------------------

async def get_cached_memo(redis: aioredis.Redis | None, query: str) -> dict | None:
    """[S8-L1] Check for a cached research memo."""
    if redis is None:
        return None
    try:
        key = f"research:memo:{normalize_cache_key(query)}"
        data = await redis.get(key)
        if data is not None:
            logger.debug("Research memo cache hit: %s", key)
            result = json.loads(data)
            result["cache_type"] = "exact"
            return result
    except Exception as exc:
        logger.warning("Memo cache read failed: %s", exc)
    return None


async def set_cached_memo(redis: aioredis.Redis | None, query: str, memo: dict) -> None:
    """[S8-L1] Cache a complete research memo."""
    if redis is None:
        return
    try:
        key = f"research:memo:{normalize_cache_key(query)}"
        payload = {**memo, "cached_at": time.time()}
        await redis.setex(key, MEMO_TTL, json.dumps(payload, default=str))
        logger.debug("Research memo cached: %s", key)
    except Exception as exc:
        logger.warning("Memo cache write failed: %s", exc)


def get_memo_cache_hash(query: str) -> str:
    """Return the hash portion of a memo cache key (for semantic cache cross-ref)."""
    return normalize_cache_key(query)


# ---------------------------------------------------------------------------
# L2: Search result cache (for parallel_hybrid_search in agent pipeline)
# ---------------------------------------------------------------------------

async def get_cached_search(
    redis: aioredis.Redis | None, query: str, **filters: Any
) -> list[dict] | None:
    """[S8-L2] Check for cached hybrid search results."""
    if redis is None:
        return None
    try:
        key = f"search:hybrid:{normalize_cache_key(query, **filters)}"
        data = await redis.get(key)
        if data is not None:
            logger.debug("Search cache hit: %s", key)
            return json.loads(data)
    except Exception as exc:
        logger.warning("Search cache read failed: %s", exc)
    return None


async def set_cached_search(
    redis: aioredis.Redis | None, query: str, results: list[dict], **filters: Any
) -> None:
    """[S8-L2] Cache hybrid search results."""
    if redis is None:
        return
    try:
        key = f"search:hybrid:{normalize_cache_key(query, **filters)}"
        await redis.setex(key, SEARCH_TTL, json.dumps(results, default=str))
    except Exception as exc:
        logger.warning("Search cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# L3: Indian Kanoon API result cache
# ---------------------------------------------------------------------------

async def get_cached_ik_search(
    redis: aioredis.Redis | None, query: str, **filters: Any,
) -> list[dict] | None:
    """[S8-L3] Check for cached IK search results.

    Cache key includes filters (court, dates, boolean_query) so that
    the same NL query with different filters gets distinct cache entries.
    """
    if redis is None:
        return None
    try:
        key = f"ik:search:{normalize_cache_key(query, **filters)}"
        data = await redis.get(key)
        if data is not None:
            logger.debug("IK search cache hit: %s", key)
            return json.loads(data)
    except Exception as exc:
        logger.warning("IK cache read failed: %s", exc)
    return None


async def set_cached_ik_search(
    redis: aioredis.Redis | None, query: str, results: list[dict],
    **filters: Any,
) -> None:
    """[S8-L3] Cache IK search results. Skip caching empty results to allow
    fallback logic to run on next attempt."""
    if redis is None or not results:
        return
    try:
        key = f"ik:search:{normalize_cache_key(query, **filters)}"
        await redis.setex(key, IK_TTL, json.dumps(results, default=str))
    except Exception as exc:
        logger.warning("IK cache write failed: %s", exc)


async def get_cached_ik_fragment(
    redis: aioredis.Redis | None, doc_id: str, query: str
) -> dict | None:
    """[S8-L3] Check for cached IK document fragment."""
    if redis is None:
        return None
    try:
        key = f"ik:fragment:{doc_id}:{normalize_cache_key(query)}"
        data = await redis.get(key)
        if data is not None:
            logger.debug("IK fragment cache hit: %s", key)
            return json.loads(data)
    except Exception as exc:
        logger.warning("IK fragment cache read failed: %s", exc)
    return None


async def set_cached_ik_fragment(
    redis: aioredis.Redis | None, doc_id: str, query: str, fragment: dict
) -> None:
    """[S8-L3] Cache IK document fragment."""
    if redis is None:
        return
    try:
        key = f"ik:fragment:{doc_id}:{normalize_cache_key(query)}"
        await redis.setex(key, IK_TTL, json.dumps(fragment, default=str))
    except Exception as exc:
        logger.warning("IK fragment cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# L4: Embedding cache
# ---------------------------------------------------------------------------

async def get_cached_embedding(
    redis: aioredis.Redis | None, text: str
) -> list[float] | None:
    """[S8-L4] Check for a cached embedding vector."""
    if redis is None:
        return None
    try:
        key = f"embed:{normalize_cache_key(text)}"
        data = await redis.get(key)
        if data is not None:
            logger.debug("Embedding cache hit: %s", key)
            return json.loads(data)
    except Exception as exc:
        logger.warning("Embedding cache read failed: %s", exc)
    return None


async def set_cached_embedding(
    redis: aioredis.Redis | None, text: str, vector: list[float]
) -> None:
    """[S8-L4] Cache an embedding vector."""
    if redis is None:
        return
    try:
        key = f"embed:{normalize_cache_key(text)}"
        await redis.setex(key, EMBEDDING_TTL, json.dumps(vector))
    except Exception as exc:
        logger.warning("Embedding cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# L5: Community summary cache
# ---------------------------------------------------------------------------

async def get_cached_community(
    redis: aioredis.Redis | None, community_id: str
) -> dict | None:
    """[S8-L5] Check for a cached community summary."""
    if redis is None:
        return None
    try:
        key = f"community:{community_id}"
        data = await redis.get(key)
        if data is not None:
            logger.debug("Community cache hit: %s", key)
            return json.loads(data)
    except Exception as exc:
        logger.warning("Community cache read failed: %s", exc)
    return None


async def set_cached_community(
    redis: aioredis.Redis | None, community_id: str, summary: dict
) -> None:
    """[S8-L5] Cache a community summary."""
    if redis is None:
        return
    try:
        key = f"community:{community_id}"
        await redis.setex(key, COMMUNITY_TTL, json.dumps(summary, default=str))
    except Exception as exc:
        logger.warning("Community cache write failed: %s", exc)
