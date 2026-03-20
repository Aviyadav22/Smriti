"""[S11] Semantic caching — vector-based query cache for near-duplicate detection.

Uses Redis Stack HNSW index to catch semantically similar queries that differ
in wording but have the same legal intent. Sits BEFORE the S8 hash-based cache
in the research pipeline.

Pipeline: embed query → search HNSW index → if cosine > 0.92 → return cached memo.

Threshold 0.92 is deliberately conservative:
  - "Section 302 IPC punishment" <-> "punishment under Section 302 IPC" → MATCH
  - "Section 302 IPC murder" <-> "Section 304 IPC culpable homicide" → NO MATCH
"""

from __future__ import annotations

import json
import logging
import struct
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.interfaces import EmbeddingProvider

logger = logging.getLogger(__name__)

SEMANTIC_CACHE_THRESHOLD = 0.92  # Conservative — only near-identical queries
SEMANTIC_CACHE_INDEX = "research:semantic_cache_idx"
SEMANTIC_CACHE_PREFIX = "research:sc:"
EMBEDDING_DIM = 1536


def _float_list_to_bytes(vec: list[float]) -> bytes:
    """Pack a float list into raw bytes for Redis vector storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def _bytes_to_float_list(raw: bytes) -> list[float]:
    """Unpack raw bytes back to float list."""
    count = len(raw) // 4
    return list(struct.unpack(f"{count}f", raw))


class SemanticCache:
    """[S11] Vector-based query cache using Redis Stack HNSW index."""

    def __init__(self, redis: aioredis.Redis, embedder: EmbeddingProvider) -> None:
        self.redis = redis
        self.embedder = embedder
        self._index_ready = False

    async def _ensure_index(self) -> bool:
        """Create the HNSW index if it doesn't exist. Returns True if available."""
        if self._index_ready:
            return True
        try:
            # Check if index already exists
            await self.redis.execute_command("FT.INFO", SEMANTIC_CACHE_INDEX)
            self._index_ready = True
            return True
        except Exception:
            pass

        try:
            # Create HNSW index on the semantic cache hash keys
            await self.redis.execute_command(
                "FT.CREATE", SEMANTIC_CACHE_INDEX,
                "ON", "HASH",
                "PREFIX", "1", SEMANTIC_CACHE_PREFIX,
                "SCHEMA",
                "query_text", "TEXT",
                "memo_hash", "TAG",
                "cached_at", "NUMERIC",
                "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(EMBEDDING_DIM),
                "DISTANCE_METRIC", "COSINE",
            )
            self._index_ready = True
            logger.info("[S11] Created semantic cache HNSW index")
            return True
        except Exception as exc:
            logger.warning("[S11] Failed to create HNSW index (Redis Stack required): %s", exc)
            return False

    async def get(self, query: str) -> dict | None:
        """Check if a semantically similar query has been cached.

        Returns the cached memo dict with cache_type='semantic' and
        original_query metadata, or None on miss.
        """
        try:
            if not await self._ensure_index():
                return None

            query_embedding = await self.embedder.embed_text(query)
            vec_bytes = _float_list_to_bytes(query_embedding)

            # KNN search — find the single nearest neighbor
            results = await self.redis.execute_command(
                "FT.SEARCH", SEMANTIC_CACHE_INDEX,
                f"*=>[KNN 1 @embedding $vec AS score]",
                "PARAMS", "2", "vec", vec_bytes,
                "RETURN", "3", "query_text", "memo_hash", "score",
                "DIALECT", "2",
            )

            # results format: [total_count, key1, [field1, val1, field2, val2, ...], ...]
            if not results or results[0] == 0:
                return None

            # Parse the result fields
            fields = results[2] if len(results) > 2 else []
            field_dict: dict[str, str] = {}
            for i in range(0, len(fields), 2):
                field_dict[fields[i].decode() if isinstance(fields[i], bytes) else fields[i]] = (
                    fields[i + 1].decode() if isinstance(fields[i + 1], bytes) else fields[i + 1]
                )

            score = float(field_dict.get("score", "0"))
            # Redis COSINE distance = 1 - cosine_similarity, so convert
            cosine_similarity = 1.0 - score

            if cosine_similarity < SEMANTIC_CACHE_THRESHOLD:
                logger.debug("[S11] Nearest neighbor score %.3f < threshold %.2f", cosine_similarity, SEMANTIC_CACHE_THRESHOLD)
                return None

            memo_hash = field_dict.get("memo_hash", "")
            original_query = field_dict.get("query_text", "")

            # Fetch the actual cached memo
            from app.core.agents.research_cache import get_cached_memo as _get_memo
            # Reconstruct the memo cache key from hash
            memo_key = f"research:memo:{memo_hash}"
            cached_data = await self.redis.get(memo_key)
            if cached_data is None:
                logger.debug("[S11] Semantic match but memo expired (hash=%s)", memo_hash)
                return None

            memo = json.loads(cached_data)
            memo["cache_type"] = "semantic"
            memo["original_query"] = original_query
            memo["semantic_similarity"] = cosine_similarity
            logger.info("[S11] Semantic cache hit: '%.60s' matched '%.60s' (sim=%.3f)", query, original_query, cosine_similarity)
            return memo

        except Exception as exc:
            logger.warning("[S11] Semantic cache get failed: %s", exc)
            return None

    async def put(self, query: str, memo_hash: str) -> None:
        """Store query embedding for future semantic matching."""
        try:
            if not await self._ensure_index():
                return

            embedding = await self.embedder.embed_text(query)
            vec_bytes = _float_list_to_bytes(embedding)
            key = f"{SEMANTIC_CACHE_PREFIX}{memo_hash}"

            await self.redis.hset(key, mapping={
                "query_text": query,
                "memo_hash": memo_hash,
                "cached_at": str(time.time()),
                "embedding": vec_bytes,
            })
            logger.debug("[S11] Stored semantic cache entry: %s", key)

        except Exception as exc:
            logger.warning("[S11] Semantic cache put failed: %s", exc)
