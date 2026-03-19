"""Tavily web search provider implementation."""

from __future__ import annotations

import asyncio
import logging

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_TAVILY_TIMEOUT = 10  # seconds

_tavily_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        httpx.HTTPStatusError,
        httpx.ConnectError,
        httpx.TimeoutException,
        asyncio.TimeoutError,
        ConnectionError,
        OSError,
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

# Default domains for legal web search
_DEFAULT_LEGAL_DOMAINS = [
    "indiankanoon.org",
    "scconline.com",
    "livelaw.in",
    "barandbench.com",
]


class TavilySearchClient:
    """Tavily web search client implementing WebSearchProvider protocol."""

    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.tavily_api_key
        if not self.api_key:
            raise ValueError(
                "Tavily API key is required. Set TAVILY_API_KEY environment variable."
            )
        self._client = httpx.AsyncClient(timeout=_TAVILY_TIMEOUT)

    @_tavily_retry
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: list[str] | None = None,
    ) -> list[dict]:
        """Search the web via Tavily API.

        Returns list of {title, url, content, score}.
        """
        domains = include_domains or _DEFAULT_LEGAL_DOMAINS

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_domains": domains,
        }

        response = await self._client.post(
            f"{self.BASE_URL}/search",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0.0),
            }
            for r in data.get("results", [])
        ]

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
