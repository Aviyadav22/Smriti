"""Pinecone vector store provider implementation."""

from __future__ import annotations

import asyncio
import logging

from pinecone import Pinecone
from pinecone.exceptions import PineconeException
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.interfaces.vector_store import SearchResult

logger = logging.getLogger(__name__)

_pinecone_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((PineconeException, ConnectionError, OSError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class PineconeStore:
    """Pinecone vector store implementing VectorStore protocol.

    Pinecone's Python SDK is synchronous, so all calls are wrapped in
    ``asyncio.to_thread()`` to avoid blocking the event loop.
    """

    def __init__(self) -> None:
        if not settings.pinecone_api_key or not settings.pinecone_api_key.strip():
            raise ValueError(
                "Pinecone API key is required. Set PINECONE_API_KEY environment variable."
            )
        self._client = Pinecone(api_key=settings.pinecone_api_key)
        host = settings.pinecone_host
        if host:
            self._index = self._client.Index(host=host)
        else:
            self._index = self._client.Index(settings.pinecone_index_name)

    @_pinecone_retry
    async def upsert(self, vectors: list[dict]) -> None:
        """Insert or update vectors.

        Each dict must contain: id, values, metadata.
        """
        try:
            await asyncio.to_thread(self._index.upsert, vectors=vectors)
        except PineconeException as exc:
            logger.error("Pinecone upsert failed (%d vectors): %s", len(vectors), exc)
            raise RuntimeError(f"Pinecone upsert failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during Pinecone upsert: %s", exc)
            raise RuntimeError(f"Pinecone upsert failed unexpectedly: {exc}") from exc

    @_pinecone_retry
    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        try:
            results = await asyncio.to_thread(
                self._index.query,
                vector=query_vector,
                top_k=top_k,
                filter=filters,
                include_metadata=True,
            )
            return [
                SearchResult(id=m.id, score=m.score, metadata=m.metadata or {})
                for m in results.matches
            ]
        except PineconeException as exc:
            logger.error("Pinecone search failed (top_k=%d): %s", top_k, exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error during Pinecone search: %s", exc)
            return []

    @_pinecone_retry
    async def delete(self, ids: list[str]) -> None:
        """Delete vectors by their IDs."""
        try:
            await asyncio.to_thread(self._index.delete, ids=ids)
        except PineconeException as exc:
            logger.error("Pinecone delete failed (%d ids): %s", len(ids), exc)
            raise RuntimeError(f"Pinecone delete failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during Pinecone delete: %s", exc)
            raise RuntimeError(f"Pinecone delete failed unexpectedly: {exc}") from exc
