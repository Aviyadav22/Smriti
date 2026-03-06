"""Gemini embedding provider implementation.

Uses gemini-embedding-001 with Matryoshka output dimensionality control.
Default: 1536 dims (recommended balance of quality vs storage).
"""

from __future__ import annotations

from google import genai
from google.genai import types

from app.core.config import settings


class GeminiEmbedder:
    """Google Gemini embedding provider implementing EmbeddingProvider protocol."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self._model = settings.gemini_embedding_model
        self._dimension = settings.gemini_embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> list[float]:
        response = await self._client.aio.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self._dimension,
            ),
        )
        return response.embeddings[0].values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.aio.models.embed_content(
            model=self._model,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=self._dimension,
            ),
        )
        return [e.values for e in response.embeddings]
