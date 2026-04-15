"""Gemini embedding provider implementation.

Uses gemini-embedding-001 with Matryoshka output dimensionality control.
Default: 1536 dims (recommended balance of quality vs storage).
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
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
    httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException,
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

    def __init__(self, *, api_key: str | None = None, use_vertexai: bool = False,
                 project: str | None = None, location: str | None = None) -> None:
        self._use_vertexai = use_vertexai or settings.gemini_use_vertexai
        self._model = settings.gemini_embedding_model
        self._dimension = settings.gemini_embedding_dimension

        # Google dropped :predict endpoint support for gemini-embedding-2-preview
        # on Vertex AI (returns 400 FAILED_PRECONDITION). The SDK routes all
        # Vertex AI embed calls to :predict, so we use the :embedContent REST
        # endpoint directly for affected models.
        self._use_vertex_rest = (
            self._use_vertexai
            and self._model in ("gemini-embedding-2-preview",)
        )

        if self._use_vertexai:
            _project = project or settings.gemini_vertexai_project
            _location = location or settings.gemini_vertexai_location
            if not _project:
                raise ValueError(
                    "gemini_vertexai_project is required when using Vertex AI. "
                    "Set GEMINI_VERTEXAI_PROJECT environment variable."
                )
            # Ensure GOOGLE_APPLICATION_CREDENTIALS env var is set for the SDK
            if settings.google_application_credentials and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

            if self._use_vertex_rest:
                # Direct REST path — bypass SDK's broken :predict routing
                self._vertex_project = _project
                self._vertex_location = _location
                self._vertex_url = (
                    f"https://{_location}-aiplatform.googleapis.com/v1/"
                    f"projects/{_project}/locations/{_location}/"
                    f"publishers/google/models/{self._model}:embedContent"
                )
                self._client = None  # Not used for REST path
                self._http_client = httpx.AsyncClient(timeout=60.0)
                logger.info(
                    "GeminiEmbedder using Vertex AI REST :embedContent (model=%s, project=%s)",
                    self._model, _project,
                )
            else:
                self._client = genai.Client(
                    vertexai=True, project=_project, location=_location,
                )
                logger.info("GeminiEmbedder using Vertex AI SDK (project=%s, location=%s)", _project, _location)
        else:
            resolved_key = api_key or settings.gemini_api_key
            if not resolved_key or not resolved_key.strip():
                raise ValueError(
                    "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                    "or pass api_key to GeminiEmbedder()."
                )
            self._client = genai.Client(api_key=resolved_key)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _vertex_rest_embed(self, text: str, task_type: str) -> list[float]:
        """Call Vertex AI :embedContent REST endpoint directly.

        The google-genai SDK routes Vertex AI embedding calls to the legacy
        :predict endpoint, which Google dropped for gemini-embedding-2-preview
        (returns 400 FAILED_PRECONDITION). This method calls :embedContent
        directly via HTTP.
        """
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        # Refresh token if expired (sync call, but fast — cached by google-auth)
        if not credentials.valid:
            credentials.refresh(google.auth.transport.requests.Request())

        body = {
            "content": {"parts": [{"text": text}]},
            "taskType": task_type,
            "outputDimensionality": self._dimension,
        }
        resp = await self._http_client.post(
            self._vertex_url,
            json=body,
            headers={
                "Authorization": f"Bearer {credentials.token}",
                "Content-Type": "application/json",
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Vertex AI embedContent failed ({resp.status_code}): {resp.text[:300]}"
            )
        return resp.json()["embedding"]["values"]

    @_embedding_retry
    async def embed_text(self, text: str, *, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
        """Embed a single text string into a 1536-dim vector via Gemini."""
        if self._use_vertex_rest:
            return await self._vertex_rest_embed(text, task_type)

        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                    task_type=task_type,
                ),
            ),
            timeout=60.0,
        )
        return response.embeddings[0].values

    @_embedding_retry
    async def embed_batch(self, texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        """Embed a batch of texts into 1536-dim vectors. Used during ingestion (batch 100).

        On Vertex AI, embedContent only supports one content at a time,
        so we embed concurrently with asyncio.gather.
        On AI Studio, the API supports batch embedding in a single call.
        """
        if self._use_vertex_rest:
            # REST path: one content per call, limited concurrency
            _SUB_BATCH = int(os.environ.get("EMBED_SUB_BATCH", "5"))
            _EMBED_SEM = int(os.environ.get("EMBED_CONCURRENCY", "3"))
            _EMBED_SLEEP = float(os.environ.get("EMBED_SLEEP", "0.5"))
            sem = asyncio.Semaphore(_EMBED_SEM)

            async def _embed_one(text: str) -> list[float]:
                async with sem:
                    return await self._vertex_rest_embed(text, task_type)

            all_results: list[list[float]] = []
            for i in range(0, len(texts), _SUB_BATCH):
                sub = texts[i : i + _SUB_BATCH]
                batch_results = await asyncio.gather(*[_embed_one(t) for t in sub])
                all_results.extend(batch_results)
                if i + _SUB_BATCH < len(texts):
                    await asyncio.sleep(_EMBED_SLEEP)
            return all_results

        if self._use_vertexai:
            # Vertex AI SDK: one content per call, process sequentially in small
            # sub-batches with limited concurrency to respect token-per-minute quota
            _SUB_BATCH = int(os.environ.get("EMBED_SUB_BATCH", "5"))
            _CONCURRENCY = int(os.environ.get("EMBED_CONCURRENCY", "3"))
            _EMBED_SLEEP = float(os.environ.get("EMBED_SLEEP", "0.5"))
            sem = asyncio.Semaphore(_CONCURRENCY)

            async def _embed_one_sdk(text: str) -> list[float]:
                async with sem:
                    resp = await asyncio.wait_for(
                        self._client.aio.models.embed_content(
                            model=self._model,
                            contents=text,
                            config=types.EmbedContentConfig(
                                output_dimensionality=self._dimension,
                                task_type=task_type,
                            ),
                        ),
                        timeout=60.0,
                    )
                    return resp.embeddings[0].values

            all_results: list[list[float]] = []
            for i in range(0, len(texts), _SUB_BATCH):
                sub = texts[i : i + _SUB_BATCH]
                batch_results = await asyncio.gather(*[_embed_one_sdk(t) for t in sub])
                all_results.extend(batch_results)
                if i + _SUB_BATCH < len(texts):
                    await asyncio.sleep(_EMBED_SLEEP)
            return all_results

        # AI Studio: batch in single call
        response = await asyncio.wait_for(
            self._client.aio.models.embed_content(
                model=self._model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=self._dimension,
                    task_type=task_type,
                ),
            ),
            timeout=120.0,
        )
        return [e.values for e in response.embeddings]
