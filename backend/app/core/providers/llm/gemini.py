"""Gemini LLM provider implementation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator

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

# Thinking control for cost savings on gemini-2.5-flash.
# The SDK's ThinkingConfig API changes across versions. We attempt to set
# thinking_budget=0 if the SDK supports it, otherwise skip (no-op).
_THINKING_BUDGET: int | None = None
_raw_budget = os.environ.get("GEMINI_THINKING_BUDGET")
if _raw_budget is not None:
    _THINKING_BUDGET = int(_raw_budget)


def _apply_thinking_config(config_kwargs: dict) -> None:
    """Add thinking_config to GenerateContentConfig kwargs if supported."""
    if _THINKING_BUDGET is None:
        return
    try:
        tc = types.ThinkingConfig(thinking_budget=_THINKING_BUDGET)
        config_kwargs["thinking_config"] = tc
    except (TypeError, ValueError, Exception):
        # SDK version doesn't support thinking_budget — skip silently.
        # Thinking may be on by default but costs are acceptable.
        pass

# Build retry exception tuple with granular Google exceptions when available
_GEMINI_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    GoogleAPIError, asyncio.TimeoutError, ConnectionError, OSError, TimeoutError,
    httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException,
)

try:
    from google.api_core.exceptions import (
        InternalServerError,
        ResourceExhausted,
        ServiceUnavailable,
    )

    _GEMINI_RETRY_EXCEPTIONS = (
        *_GEMINI_RETRY_EXCEPTIONS,
        ResourceExhausted,
        ServiceUnavailable,
        InternalServerError,
    )
except ImportError:
    pass

_gemini_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(_GEMINI_RETRY_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# Default timeout for LLM calls (seconds)
_LLM_TIMEOUT = 120


class GeminiLLM:
    """Google Gemini LLM provider implementing LLMProvider protocol."""

    @staticmethod
    def _normalize_schema(schema: dict) -> dict:
        """Convert standard JSON Schema nullable to Gemini format.

        Gemini SDK requires {"type": "string", "nullable": true} instead of
        standard JSON Schema {"type": ["string", "null"]}.
        """
        if not isinstance(schema, dict):
            return schema

        result = {}
        for key, value in schema.items():
            if key == "type" and isinstance(value, list):
                # Convert ["string", "null"] -> "string" with nullable=true
                non_null_types = [t for t in value if t != "null"]
                if len(non_null_types) == 1 and "null" in value:
                    result["type"] = non_null_types[0]
                    result["nullable"] = True
                else:
                    result["type"] = value
            elif key == "properties" and isinstance(value, dict):
                result["properties"] = {
                    k: GeminiLLM._normalize_schema(v) for k, v in value.items()
                }
            elif key == "items" and isinstance(value, dict):
                result["items"] = GeminiLLM._normalize_schema(value)
            else:
                result[key] = value
        return result

    # [S10] Class-level cache for synthesis system prompt
    _synthesis_cache_name: str | None = None

    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 use_vertexai: bool = False, project: str | None = None,
                 location: str | None = None) -> None:
        if use_vertexai or settings.gemini_use_vertexai:
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
            self._client = genai.Client(
                vertexai=True, project=_project, location=_location,
            )
            logger.info("GeminiLLM using Vertex AI (project=%s, location=%s)", _project, _location)
        else:
            resolved_key = api_key or settings.gemini_api_key
            if not resolved_key or not resolved_key.strip():
                raise ValueError(
                    "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                    "or pass api_key to GeminiLLM()."
                )
            self._client = genai.Client(api_key=resolved_key)
        self._model = model or settings.gemini_model

    async def _get_or_create_synthesis_cache(self, system_prompt: str) -> str | None:
        """[S10] Create or reuse a CachedContent for the synthesis system prompt.

        Returns the cached content name (e.g. "caches/abc123") or None on failure.
        """
        if not settings.gemini_context_cache_enabled:
            return None

        if GeminiLLM._synthesis_cache_name is not None:
            return GeminiLLM._synthesis_cache_name

        try:
            cached_content = await self._client.aio.caches.create(
                model=self._model,
                config=types.CreateCachedContentConfig(
                    system_instruction=system_prompt,
                    display_name="smriti-research-synthesis",
                    ttl=f"{settings.gemini_context_cache_ttl}s",
                ),
            )
            GeminiLLM._synthesis_cache_name = cached_content.name
            logger.info("Created Gemini context cache: %s", cached_content.name)
            return cached_content.name
        except Exception as exc:
            logger.warning("Failed to create Gemini context cache: %s", exc)
            return None

    @_gemini_retry
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
        use_context_cache: bool = False,
    ) -> str:
        """Generate text via Gemini API with optional context caching.

        Used for research memo synthesis, query understanding, treatment
        classification, and all free-form LLM generation in the legal pipeline.
        """
        config_kwargs: dict = {
            "system_instruction": system,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        _apply_thinking_config(config_kwargs)
        # [S10] Use context cache for synthesis calls
        if use_context_cache and system:
            cached_name = await self._get_or_create_synthesis_cache(system)
            if cached_name:
                config_kwargs["cached_content"] = cached_name
                config_kwargs["system_instruction"] = None  # Avoid duplication
        config = types.GenerateContentConfig(**config_kwargs)
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=self._model, contents=prompt, config=config
            ),
            timeout=_LLM_TIMEOUT,
        )
        return response.text or ""

    @_gemini_retry
    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        """Generate structured JSON output via Gemini with schema enforcement.

        Used for metadata extraction (16 fields), query understanding,
        research plan generation, and all structured LLM outputs.
        Schema is normalized to use Gemini-compatible nullable format.
        """
        normalized_schema = self._normalize_schema(output_schema)
        config_kwargs: dict = {
            "system_instruction": system,
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": normalized_schema,
        }
        _apply_thinking_config(config_kwargs)
        config = types.GenerateContentConfig(**config_kwargs)
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=self._model, contents=prompt, config=config
            ),
            timeout=_LLM_TIMEOUT,
        )

        raw_text = response.text or "{}"
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse Gemini structured response as JSON: %s (raw: %.200s)",
                exc,
                raw_text,
            )
            return {}

    @_gemini_retry
    async def generate_structured_from_pdf(
        self,
        pdf_path: str,
        *,
        prompt: str,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        """Extract structured data directly from a PDF file (multimodal)."""
        import pathlib

        pdf_bytes = pathlib.Path(pdf_path).read_bytes()
        pdf_part = types.Part.from_bytes(
            data=pdf_bytes, mime_type="application/pdf"
        )

        normalized_schema = self._normalize_schema(output_schema)
        pdf_config_kwargs: dict = {
            "system_instruction": system,
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_schema": normalized_schema,
        }
        _apply_thinking_config(pdf_config_kwargs)
        config = types.GenerateContentConfig(**pdf_config_kwargs)
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=self._model,
                contents=[pdf_part, prompt],
                config=config,
            ),
            timeout=180,  # Longer timeout for PDF processing
        )

        raw_text = response.text or "{}"
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse Gemini PDF structured response: %s (raw: %.200s)",
                exc,
                raw_text,
            )
            return {}

    @_gemini_retry
    async def _start_stream(
        self,
        prompt: str,
        config: types.GenerateContentConfig,
    ):
        """Start a streaming response (retryable helper)."""
        return await asyncio.wait_for(
            self._client.aio.models.generate_content_stream(
                model=self._model, contents=prompt, config=config
            ),
            timeout=_LLM_TIMEOUT,
        )

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        use_context_cache: bool = False,
    ) -> AsyncIterator[str]:
        config_kwargs: dict = {
            "system_instruction": system,
            "temperature": temperature,
        }
        if max_tokens:
            config_kwargs["max_output_tokens"] = max_tokens
        _apply_thinking_config(config_kwargs)
        # [S10] Use context cache for synthesis calls
        if use_context_cache and system:
            cached_name = await self._get_or_create_synthesis_cache(system)
            if cached_name:
                config_kwargs["cached_content"] = cached_name
                config_kwargs["system_instruction"] = None
        config = types.GenerateContentConfig(**config_kwargs)
        stream = await self._start_stream(prompt, config)

        async for chunk in stream:
            if chunk.text:
                yield chunk.text
