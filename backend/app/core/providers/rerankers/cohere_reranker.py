"""Cohere reranker provider implementation."""

from __future__ import annotations

import cohere

from app.core.config import settings
from app.core.interfaces.reranker import RerankResult


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
        response = await self._client.rerank(
            model=self._model,
            query=query,
            documents=documents,
            top_n=top_n,
        )
        return [
            RerankResult(
                index=r.index,
                score=r.relevance_score,
                text=documents[r.index],
            )
            for r in response.results
        ]
