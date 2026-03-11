"""Gemini LLM provider implementation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

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
_GEMINI_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    GoogleAPIError, asyncio.TimeoutError, ConnectionError, OSError, TimeoutError,
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

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        resolved_key = api_key or settings.gemini_api_key
        if not resolved_key or not resolved_key.strip():
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key to GeminiLLM()."
            )
        self._client = genai.Client(api_key=resolved_key)
        self._model = model or settings.gemini_model

    @_gemini_retry
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model, contents=prompt, config=config
                ),
                timeout=_LLM_TIMEOUT,
            )
            return response.text or ""
        except asyncio.TimeoutError:
            logger.error("Gemini generate() timed out after %ds", _LLM_TIMEOUT)
            raise RuntimeError(f"Gemini generate timed out after {_LLM_TIMEOUT}s")
        except GoogleAPIError as exc:
            logger.error("Gemini API error in generate(): %s", exc)
            raise RuntimeError(f"Gemini generate failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in generate(): %s", exc)
            raise RuntimeError(f"Gemini generate failed unexpectedly: {exc}") from exc

    @_gemini_retry
    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        normalized_schema = self._normalize_schema(output_schema)
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=normalized_schema,
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model, contents=prompt, config=config
                ),
                timeout=_LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("Gemini generate_structured() timed out after %ds", _LLM_TIMEOUT)
            raise RuntimeError(f"Gemini generate_structured timed out after {_LLM_TIMEOUT}s")
        except GoogleAPIError as exc:
            logger.error("Gemini API error in generate_structured(): %s", exc)
            raise RuntimeError(f"Gemini generate_structured failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in generate_structured(): %s", exc)
            raise RuntimeError(f"Gemini generate_structured failed unexpectedly: {exc}") from exc

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
    async def _start_stream(
        self,
        prompt: str,
        config: types.GenerateContentConfig,
    ):
        """Start a streaming response (retryable helper)."""
        try:
            return await asyncio.wait_for(
                self._client.aio.models.generate_content_stream(
                    model=self._model, contents=prompt, config=config
                ),
                timeout=_LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("Gemini stream() timed out waiting for initial response after %ds", _LLM_TIMEOUT)
            raise RuntimeError(f"Gemini stream timed out after {_LLM_TIMEOUT}s")
        except GoogleAPIError as exc:
            logger.error("Gemini API error in stream(): %s", exc)
            raise RuntimeError(f"Gemini stream failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error in stream(): %s", exc)
            raise RuntimeError(f"Gemini stream failed unexpectedly: {exc}") from exc

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> AsyncIterator[str]:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
        )
        stream = await self._start_stream(prompt, config)

        async for chunk in stream:
            if chunk.text:
                yield chunk.text
