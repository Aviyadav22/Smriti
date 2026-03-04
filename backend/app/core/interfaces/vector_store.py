"""Vector store interface for similarity search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single result from a vector similarity search."""

    id: str
    score: float
    metadata: dict


@runtime_checkable
class VectorStore(Protocol):
    """Contract for vector database providers."""

    async def upsert(self, vectors: list[dict]) -> None:
        """Insert or update vectors. Each dict must contain: id, values, metadata."""
        ...

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[SearchResult]: ...

    async def delete(self, ids: list[str]) -> None: ...
