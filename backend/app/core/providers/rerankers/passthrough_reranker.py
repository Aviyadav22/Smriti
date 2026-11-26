"""Passthrough reranker — keeps the incoming (RRF) order.

Used when no reranking service is configured (RERANKER_PROVIDER=none), e.g. a
self-hosted deploy without a Cohere key. Scores mirror the circuit-breaker
fallback in CohereReranker so downstream code sees the same shape.
"""

from __future__ import annotations

from app.core.interfaces.reranker import RerankResult


class PassthroughReranker:
    """Reranker implementing Reranker protocol without reordering."""

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 10,
    ) -> list[RerankResult]:
        return [
            RerankResult(index=i, score=1.0 - i * 0.01, text=doc)
            for i, doc in enumerate(documents[:top_n])
        ]
