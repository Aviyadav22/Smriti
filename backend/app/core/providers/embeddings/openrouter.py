"""OpenRouter embedding provider (OpenAI-compatible /embeddings)."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.providers.llm.openrouter import OpenRouterClient, openrouter_retry

logger = logging.getLogger(__name__)


class OpenRouterEmbedder:
    """OpenRouter embedding model implementing the EmbeddingProvider protocol."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._client = OpenRouterClient(api_key=api_key)
        self._model = settings.openrouter_embedding_model
        # Shared with Gemini: case_vectors is vector(gemini_embedding_dimension).
        self._dimension = settings.gemini_embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str, *, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
        return (await self.embed_batch([text], task_type=task_type))[0]

    @openrouter_retry
    async def embed_batch(
        self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        body = {
            "model": self._model,
            "input": texts,
            "dimensions": self._dimension,
            "input_type": "query" if task_type == "RETRIEVAL_QUERY" else "document",
            "provider": {"data_collection": settings.openrouter_data_collection},
        }
        data = await self._client.post("/embeddings", body)
        vectors = [item["embedding"] for item in sorted(data["data"], key=lambda d: d["index"])]
        if vectors and len(vectors[0]) != self._dimension:
            raise ValueError(
                f"{self._model} returned {len(vectors[0])}-dim vectors; "
                f"the vector index expects {self._dimension}."
            )
        return vectors
