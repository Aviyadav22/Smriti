"""Cohere reranker provider implementation."""

from __future__ import annotations

import asyncio
import logging

import cohere

from app.core.config import settings
from app.core.interfaces.reranker import RerankResult

logger = logging.getLogger(__name__)

# Timeout for reranker calls (seconds)
_RERANK_TIMEOUT = 30


class CohereReranker:
    """Cohere reranker implementing Reranker protocol."""

    def __init__(self) -> None:
        self._client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
        self._model = settings.cohere_rerank_model

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int = 10,
    ) -> list[RerankResult]:
        if not documents:
            return []
        try:
            response = await asyncio.wait_for(
                self._client.rerank(
                    model=self._model,
                    query=query,
                    documents=documents,
                    top_n=top_n,
                ),
                timeout=_RERANK_TIMEOUT,
            )
            return [
                RerankResult(
                    index=r.index,
                    score=r.relevance_score,
                    text=documents[r.index],
                )
                for r in response.results
            ]
        except asyncio.TimeoutError:
            logger.warning("Cohere rerank timed out after %ds, returning original order", _RERANK_TIMEOUT)
            # Return original order as fallback
            return [
                RerankResult(index=i, score=1.0 - i * 0.01, text=doc)
                for i, doc in enumerate(documents[:top_n])
            ]
