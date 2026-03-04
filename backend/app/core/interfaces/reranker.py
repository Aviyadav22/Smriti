"""Reranker interface for result relevance scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RerankResult:
    """A single result from reranking."""

    index: int
    score: float
    text: str


@runtime_checkable
class Reranker(Protocol):
    """Contract for reranking providers."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 10,
    ) -> list[RerankResult]: ...
