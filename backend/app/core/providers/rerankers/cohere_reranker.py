"""Cohere reranker provider implementation."""

from __future__ import annotations

import asyncio
import logging

import cohere
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.interfaces.reranker import RerankResult

logger = logging.getLogger(__name__)

# Timeout for reranker calls (seconds)
_RERANK_TIMEOUT = 30

_cohere_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((
        asyncio.TimeoutError, ConnectionError, OSError,
        cohere.TooManyRequestsError,
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class CohereReranker:
    """Cohere reranker implementing Reranker protocol."""

    def __init__(self) -> None:
        if not settings.cohere_api_key or not settings.cohere_api_key.strip():
            raise ValueError(
                "Cohere API key is required. Set COHERE_API_KEY environment variable."
            )
        self._client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)
        self._model = settings.cohere_rerank_model

    @_cohere_retry
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

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if hasattr(self._client, '_client') and hasattr(self._client._client, 'aclose'):
            await self._client._client.aclose()
