"""Pinecone vector store provider implementation."""

from __future__ import annotations

from pinecone import Pinecone

from app.core.config import settings
from app.core.interfaces.vector_store import SearchResult


class PineconeStore:
    """Pinecone vector store implementing VectorStore protocol."""

    def __init__(self) -> None:
        self._client = Pinecone(api_key=settings.pinecone_api_key)
        self._index = self._client.Index(settings.pinecone_index_name)

    async def upsert(self, vectors: list[dict]) -> None:
        """Insert or update vectors.

        Each dict must contain: id, values, metadata.
        """
        self._index.upsert(vectors=vectors)

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        results = self._index.query(
            vector=query_vector,
            top_k=top_k,
            filter=filters,
            include_metadata=True,
        )
        return [
            SearchResult(id=m.id, score=m.score, metadata=m.metadata or {})
            for m in results.matches
        ]

    async def delete(self, ids: list[str]) -> None:
        self._index.delete(ids=ids)
