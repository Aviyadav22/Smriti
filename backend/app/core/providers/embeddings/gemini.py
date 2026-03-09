"""Gemini embedding provider implementation.

Uses gemini-embedding-001 with Matryoshka output dimensionality control.
Default: 1536 dims (recommended balance of quality vs storage).
"""

from __future__ import annotations

import logging

from google import genai
from google.api_core.exceptions import GoogleAPIError
from google.genai import types
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_embedding_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((GoogleAPIError, ConnectionError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class GeminiEmbedder:
    """Google Gemini embedding provider implementing EmbeddingProvider protocol."""

    def __init__(self, *, api_key: str | None = None) -> None:
        resolved_key = api_key or settings.gemini_api_key
        if not resolved_key or not resolved_key.strip():
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key to GeminiEmbedder()."
            )
        self._client = genai.Client(api_key=resolved_key)
        self._model = settings.gemini_embedding_model
        self._dimension = settings.gemini_embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @_embedding_retry
    async def embed_text(self, text: str) -> list[float]:
        try:
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                ),
            )
            return response.embeddings[0].values
        except GoogleAPIError as exc:
            logger.error("Gemini embedding API error for embed_text: %s", exc)
            raise RuntimeError(f"Gemini embedding failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in embed_text: %s", exc)
            raise RuntimeError(f"Gemini embedding failed unexpectedly: {exc}") from exc

    @_embedding_retry
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                ),
            )
            return [e.values for e in response.embeddings]
        except GoogleAPIError as exc:
            logger.error("Gemini embedding API error for embed_batch (%d texts): %s", len(texts), exc)
            raise RuntimeError(f"Gemini batch embedding failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in embed_batch (%d texts): %s", len(texts), exc)
            raise RuntimeError(f"Gemini batch embedding failed unexpectedly: {exc}") from exc
