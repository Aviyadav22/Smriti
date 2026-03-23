"""Gemini embedding provider implementation.

Uses gemini-embedding-001 with Matryoshka output dimensionality control.
Default: 1536 dims (recommended balance of quality vs storage).
"""

from __future__ import annotations

import asyncio
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

# Build retry exception tuple with granular Google exceptions when available
_EMBEDDING_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    GoogleAPIError, ConnectionError, OSError, TimeoutError,
)

try:
    from google.api_core.exceptions import (
        InternalServerError,
        ResourceExhausted,
        ServiceUnavailable,
    )

    _EMBEDDING_RETRY_EXCEPTIONS = (
        *_EMBEDDING_RETRY_EXCEPTIONS,
        ResourceExhausted,
        ServiceUnavailable,
        InternalServerError,
    )
except ImportError:
    pass

_embedding_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(_EMBEDDING_RETRY_EXCEPTIONS),
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
        """Embed a single text string into a 1536-dim vector via Gemini."""
        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                ),
            ),
            timeout=60.0,
        )
        return response.embeddings[0].values

    @_embedding_retry
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into 1536-dim vectors. Used during ingestion (batch 100)."""
        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                ),
            ),
            timeout=120.0,
        )
        return [e.values for e in response.embeddings]
