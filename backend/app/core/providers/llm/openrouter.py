"""OpenRouter LLM provider (OpenAI-compatible chat completions).

Lets Smriti run on OpenRouter's free models. Free models come and go and are
rate-limited upstream, so the model setting takes a comma-separated list:
OpenRouter tries them in order when one is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import TYPE_CHECKING

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 120


def limit_resets_later(response: httpx.Response, *, within_seconds: float = 60) -> bool:
    """True for a 429 whose window resets later than we'd wait (the free daily cap)."""
    reset_ms = response.headers.get("x-ratelimit-reset", "")
    if response.status_code != 429 or not reset_ms.isdigit():
        return False
    return int(reset_ms) / 1000 - time.time() > within_seconds


class EmptyResponseError(RuntimeError):
    """The model returned no content (e.g. a thinking model ran out of tokens)."""


def _is_retryable(exc: BaseException) -> bool:
    """Retry network errors, empty replies, short rate limits (429) and 5xx.

    The free daily cap also answers 429, but it only resets at midnight UTC, so
    retrying would just stall the request; fail fast and let callers fall back.
    A call that hit the overall deadline isn't retried either: it would most
    likely land on the same slow model and double the wait.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        if limit_resets_later(exc.response):
            return False
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return False
    return isinstance(exc, (EmptyResponseError, httpx.TransportError, ConnectionError, OSError))


# Free models allow 20 requests/minute, so back off for up to a minute.
openrouter_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception(_is_retryable),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def parse_model_list(value: str) -> list[str]:
    """Split a comma-separated model setting into OpenRouter model IDs."""
    return [m.strip() for m in value.split(",") if m.strip()]


def extract_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating code fences and prose."""
    text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        logger.error("Failed to parse OpenRouter structured response (raw: %.200s)", text)
        return {}


class OpenRouterClient:
    """Thin async client for OpenRouter's chat and embeddings endpoints."""

    def __init__(self, *, api_key: str | None = None) -> None:
        key = api_key or settings.openrouter_api_key
        if not key or not key.strip():
            raise ValueError(
                "OpenRouter API key is required. Set OPENROUTER_API_KEY environment variable."
            )
        self._http = httpx.AsyncClient(
            base_url=settings.openrouter_base_url,
            timeout=httpx.Timeout(_LLM_TIMEOUT, connect=15.0),
            headers={
                "Authorization": f"Bearer {key}",
                # Shown on openrouter.ai activity pages.
                "HTTP-Referer": "https://smriti.neetiq.in",
                "X-Title": "Smriti",
            },
        )

    def routing(self, models: list[str]) -> dict:
        """Model fallback list, data-collection preference and reasoning switch."""
        body: dict = {"model": models[0]}
        if len(models) > 1:
            body["models"] = models
        body["provider"] = {"data_collection": settings.openrouter_data_collection}
        if not settings.openrouter_reasoning:
            # Free "thinking" models can spend minutes reasoning before answering.
            body["reasoning"] = {"enabled": False}
        return body

    async def post(self, path: str, body: dict) -> dict:
        # httpx's timeout only bounds the gap between bytes, and OpenRouter sends
        # keep-alives while a model works, so enforce an overall deadline too.
        return await asyncio.wait_for(self._post(path, body), timeout=settings.openrouter_call_timeout)

    async def _post(self, path: str, body: dict) -> dict:
        response = await self._http.post(path, json=body)
        response.raise_for_status()
        data = response.json()
        # OpenRouter reports some upstream failures as 200 with an error body.
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            code = err.get("code") if isinstance(err, dict) else None
            raise httpx.HTTPStatusError(
                f"OpenRouter error: {err}",
                request=response.request,
                response=httpx.Response(code if isinstance(code, int) else 502, request=response.request),
            )
        return data

    def stream(self, path: str, body: dict):
        return self._http.stream("POST", path, json=body)

    async def check_key(self) -> dict:
        """Validate the key without spending a request (GET /key is free)."""
        response = await self._http.get("/key")
        response.raise_for_status()
        return response.json().get("data", {})


class OpenRouterLLM:
    """OpenRouter chat model implementing the LLMProvider protocol."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self._client = OpenRouterClient(api_key=api_key)
        self._models = parse_model_list(model or settings.openrouter_model)
        if not self._models:
            raise ValueError("OPENROUTER_MODEL must name at least one model.")

    @staticmethod
    def _messages(prompt: str, system: str | None) -> list[dict]:
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _content(data: dict) -> str:
        choices = data.get("choices") or []
        content = (choices[0].get("message") or {}).get("content") if choices else None
        if not content or not content.strip():
            raise EmptyResponseError(f"OpenRouter returned no content (model {data.get('model', '?')})")
        return content

    @openrouter_retry
    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
        **_: object,  # use_context_cache etc. are Gemini-only
    ) -> str:
        body = {
            **self._client.routing(self._models),
            "messages": self._messages(prompt, system),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        return self._content(await self._client.post("/chat/completions", body))

    @openrouter_retry
    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        # Not every free model enforces json_schema, so the schema also goes in
        # the prompt and the reply is parsed leniently.
        instruction = (
            "Respond with a single JSON object that matches this JSON Schema. "
            "Output only the JSON, with no other text.\n"
            f"{json.dumps(output_schema)}"
        )
        body = {
            **self._client.routing(self._models),
            "messages": self._messages(prompt, f"{system}\n\n{instruction}" if system else instruction),
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": output_schema, "strict": False},
            },
        }
        return extract_json(self._content(await self._client.post("/chat/completions", body)))

    async def generate_structured_from_pdf(
        self,
        pdf_path: str,
        *,
        prompt: str,
        system: str | None = None,
        output_schema: dict,
        temperature: float = 0.1,
    ) -> dict:
        """Extract the PDF's text locally, then run a normal structured call."""
        from app.core.providers.document_parsers.pdf_parser import PDFParser

        parser = PDFParser()
        text = await parser.extract_text(pdf_path)
        if not text or len(text.strip()) < 50:
            text = await parser.extract_text_with_ocr(pdf_path)
        return await self.generate_structured(
            f"{prompt}\n\nDocument text:\n{text}",
            system=system,
            output_schema=output_schema,
            temperature=temperature,
        )

    async def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        **_: object,
    ) -> AsyncIterator[str]:
        body = {
            **self._client.routing(self._models),
            "messages": self._messages(prompt, system),
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        async with self._client.stream("/chat/completions", body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                # SSE: "data: {...}" lines; ": OPENROUTER PROCESSING" keep-alives are comments.
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: ") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if chunk.get("error"):
                    raise RuntimeError(f"OpenRouter stream error: {chunk['error']}")
                for choice in chunk.get("choices") or []:
                    text = (choice.get("delta") or {}).get("content")
                    if text:
                        yield text
