"""Vector store interface for similarity search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


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
        user_scope: str | None = None,
    ) -> list[SearchResult]: ...

    async def delete_by_metadata(
        self,
        filter: dict[str, Any],
        *,
        exclude_ids: list[str] | None = None,
    ) -> None:
        """Delete vectors matching the metadata filter.

        Args:
            filter: Metadata filter to match vectors for deletion.
            exclude_ids: Optional list of vector IDs to exclude from deletion.
        """
        ...
