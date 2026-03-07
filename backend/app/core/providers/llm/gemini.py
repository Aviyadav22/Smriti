"""Gemini LLM provider implementation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default timeout for LLM calls (seconds)
_LLM_TIMEOUT = 120


class GeminiLLM:
    """Google Gemini LLM provider implementing LLMProvider protocol."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self._model = settings.gemini_model

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
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=self._model, contents=prompt, config=config
            ),
            timeout=_LLM_TIMEOUT,
        )
        return response.text or ""

    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=output_schema,
        )
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=self._model, contents=prompt, config=config
            ),
            timeout=_LLM_TIMEOUT,
        )
        return json.loads(response.text or "{}")

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
        stream = await asyncio.wait_for(
            self._client.aio.models.generate_content_stream(
                model=self._model, contents=prompt, config=config
            ),
            timeout=_LLM_TIMEOUT,
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text
