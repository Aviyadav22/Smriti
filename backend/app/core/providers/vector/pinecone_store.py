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
            await asyncio.wait_for(
                asyncio.to_thread(self._index.upsert, vectors=vectors),
                timeout=120,
            )
        except asyncio.TimeoutError as exc:
            logger.error("Pinecone upsert timed out after 120s (%d vectors)", len(vectors))
            raise RuntimeError(
                f"Pinecone upsert timed out after 120s ({len(vectors)} vectors)"
            ) from exc
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
        user_scope: str | None = None,
    ) -> list[SearchResult]:
        if user_scope:
            filters = dict(filters) if filters else {}
            filters["user_id"] = user_scope
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    self._index.query,
                    vector=query_vector,
                    top_k=top_k,
                    filter=filters,
                    include_metadata=True,
                ),
                timeout=10,
            )
            return [
                SearchResult(id=m.id, score=m.score, metadata=m.metadata or {})
                for m in results.matches
            ]
        except asyncio.TimeoutError:
            logger.warning("Pinecone search timed out after 10s (top_k=%d)", top_k)
            return []
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

    @_pinecone_retry
    async def delete_by_metadata(
        self,
        filter: dict,
        *,
        exclude_ids: list[str] | None = None,
    ) -> None:
        """Delete vectors matching a metadata filter (e.g. case_id).

        Args:
            filter: Pinecone metadata filter dict.
            exclude_ids: Optional list of vector IDs to keep (skip deletion).
        """
        try:
            if not exclude_ids:
                # Fast path: server-side filter delete
                await asyncio.to_thread(self._index.delete, filter=filter)
                return

            # When exclude_ids is provided, we must query for matching IDs first,
            # then delete only those NOT in the exclude set.
            # Use a zero vector query with high top_k to find matching vectors.
            # Dimension matches Gemini gemini-embedding-001 (1536-dim).
            exclude_set = set(exclude_ids)
            results = await asyncio.to_thread(
                self._index.query,
                vector=[0.0] * 1536,
                top_k=10_000,
                filter=filter,
                include_metadata=False,
            )
            ids_to_delete = [
                m.id for m in results.matches
                if m.id not in exclude_set
            ]
            if ids_to_delete:
                # Delete in batches of 1000 (Pinecone limit)
                for i in range(0, len(ids_to_delete), 1000):
                    await asyncio.to_thread(
                        self._index.delete, ids=ids_to_delete[i : i + 1000]
                    )
                logger.info(
                    "Deleted %d stale vectors (kept %d new), filter=%s",
                    len(ids_to_delete), len(exclude_ids), filter,
                )
        except PineconeException as exc:
            logger.error("Pinecone delete by metadata failed (filter=%s): %s", filter, exc)
            raise RuntimeError(f"Pinecone delete by metadata failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during Pinecone metadata delete: %s", exc)
            raise RuntimeError(f"Pinecone delete by metadata failed: {exc}") from exc
