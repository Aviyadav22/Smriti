"""Indian Kanoon API client.

https://api.indiankanoon.org/documentation/

Rate limit: 2 req/sec. Pricing: Rs 0.02/docmeta, Rs 0.05/fragment, Rs 0.20/doc.
"""

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

_IK_TIMEOUT = 15  # seconds per request

_ik_retry = retry(
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


class IndianKanoonClient:
    """Indian Kanoon API client implementing ExternalDocProvider protocol."""

    BASE_URL = "https://api.indiankanoon.org"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.ik_api_token
        if not self.token:
            raise ValueError(
                "Indian Kanoon API token is required. Set IK_API_TOKEN environment variable."
            )
        self._client = httpx.AsyncClient(
            timeout=_IK_TIMEOUT,
            headers={"Authorization": f"Token {self.token}"},
        )
        self._rate_limit = settings.ik_rate_limit
        self._last_request_time: float = 0.0

    async def _rate_limited_post(self, url: str, data: dict | None = None) -> dict:
        """POST with rate limiting (2 req/sec default)."""
        now = asyncio.get_event_loop().time()
        min_interval = 1.0 / self._rate_limit
        wait_time = self._last_request_time + min_interval - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        response = await self._client.post(url, data=data or {})
        self._last_request_time = asyncio.get_event_loop().time()
        response.raise_for_status()
        return response.json()

    @_ik_retry
    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        court_filter: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        """Search Indian Kanoon. POST /search/?formInput=<query>&pagenum=0."""
        params: dict[str, str] = {"formInput": query, "pagenum": "0"}
        if court_filter:
            params["formInput"] += f" doctypes: {court_filter}"
        if from_date:
            params["fromdate"] = from_date
        if to_date:
            params["todate"] = to_date

        url = f"{self.BASE_URL}/search/"
        result = await self._rate_limited_post(url, data=params)
        docs = result.get("docs", [])
        return docs[:max_results]

    @_ik_retry
    async def get_document(self, doc_id: str) -> dict:
        """Get full document text. POST /doc/<doc_id>/ (Rs 0.20/req)."""
        url = f"{self.BASE_URL}/doc/{doc_id}/"
        return await self._rate_limited_post(url)

    @_ik_retry
    async def get_fragment(self, doc_id: str, query: str) -> dict:
        """Get relevant fragment. POST /docfragment/<doc_id>/ (Rs 0.05/req)."""
        url = f"{self.BASE_URL}/docfragment/{doc_id}/"
        return await self._rate_limited_post(url, data={"formInput": query})

    @_ik_retry
    async def get_metadata(self, doc_id: str) -> dict:
        """Get document metadata. POST /docmeta/<doc_id>/ (Rs 0.02/req)."""
        url = f"{self.BASE_URL}/docmeta/{doc_id}/"
        return await self._rate_limited_post(url)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
