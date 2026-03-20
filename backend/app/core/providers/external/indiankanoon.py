"""Indian Kanoon API client.

https://api.indiankanoon.org/documentation/

Rate limit: 2 req/sec. Pricing: Rs 0.02/docmeta, Rs 0.05/fragment, Rs 0.20/doc.
"""

from __future__ import annotations

import asyncio
import logging
import time

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
_CIRCUIT_BREAKER_THRESHOLD = 3   # [5E.5] consecutive 429s to trip open
_CIRCUIT_BREAKER_COOLDOWN = 60   # [5E.5] seconds before half-open retry

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


# IK court codes for inline doctype filter syntax
IK_COURT_CODES: dict[str, str] = {
    "supreme_court": "supremecourt",
    "sc": "supremecourt",
    "delhi": "delhihighcourt",
    "bombay": "bombayhighcourt",
    "madras": "madrashighcourt",
    "calcutta": "calcuttahighcourt",
    "karnataka": "karnatakahighcourt",
    "allahabad": "allabadhighcourt",
    "kerala": "keralahighcourt",
    "punjab": "punjabharayanahighcourt",
    "gauhati": "gauhatihighcourt",
    "gujarat": "gujarathighcourt",
    "rajasthan": "rajasthanhighcourt",
    "patna": "patnahighcourt",
    "telangana": "teabordhighcourt",
    "chhattisgarh": "cabordhighcourt",
    "jharkhand": "jabordhighcourt",
    "uttarakhand": "utabordhighcourt",
}


class IKCircuitBreakerOpen(Exception):
    """Raised when the IK API circuit breaker is open [5E.5]."""


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
            timeout=settings.web_search_timeout or _IK_TIMEOUT,
            headers={"Authorization": f"Token {self.token}"},
        )
        self._rate_limit = settings.ik_rate_limit
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()
        # [5E.5] Circuit breaker state
        self._consecutive_429s: int = 0
        self._circuit_open_until: float = 0.0

    def _check_circuit_breaker(self) -> None:
        """[5E.5] Raise if circuit breaker is open."""
        if self._consecutive_429s >= _CIRCUIT_BREAKER_THRESHOLD:
            if time.monotonic() < self._circuit_open_until:
                raise IKCircuitBreakerOpen(
                    f"IK API circuit breaker open — {self._consecutive_429s} consecutive 429s"
                )
            # Cooldown expired — half-open: reset and allow one request
            self._consecutive_429s = 0
            logger.info("IK circuit breaker half-open — allowing request")

    async def _rate_limited_post(self, url: str, data: dict | None = None) -> dict:
        """POST with token bucket rate limiting + circuit breaker [5E.5]."""
        self._check_circuit_breaker()

        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            min_interval = 1.0 / self._rate_limit
            wait_time = self._last_request_time + min_interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            response = await self._client.post(url, data=data or {})
            self._last_request_time = asyncio.get_running_loop().time()

            # [5E.5] Track 429s for circuit breaker
            if response.status_code == 429:
                self._consecutive_429s += 1
                self._circuit_open_until = time.monotonic() + _CIRCUIT_BREAKER_COOLDOWN
                logger.warning(
                    "IK API 429 rate limited (consecutive=%d/%d)",
                    self._consecutive_429s, _CIRCUIT_BREAKER_THRESHOLD,
                )
                response.raise_for_status()

            # Success — reset circuit breaker
            self._consecutive_429s = 0
            response.raise_for_status()
            return response.json()

    @_ik_retry
    async def search(
        self,
        query: str,
        *,
        max_results: int = 10,
        boolean_query: str | None = None,
        court_filter: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort_by: str | None = None,
        max_pages: int = 1,
        title_filter: str | None = None,
        cite_filter: str | None = None,
        author_filter: str | None = None,
        bench_filter: str | None = None,
        max_cites: int | None = None,
    ) -> list[dict]:
        """Search Indian Kanoon with boolean operators, court filter, dates, sort.

        Args:
            query: Natural language search query.
            boolean_query: IK boolean syntax (ANDD, ORR, NOTT, NEAR operators).
                If provided, used instead of query for the search.
            court_filter: Court name key (e.g. "supreme_court", "delhi").
                Mapped to IK doctype codes via IK_COURT_CODES.
            from_date: Start date in DD-MM-YYYY format.
            to_date: End date in DD-MM-YYYY format.
            sort_by: "mostrecent" for recency sort, None for relevance.
            max_pages: Number of result pages to fetch (10 results/page).
        """
        # Use boolean_query if provided (IK's ANDD/ORR/NOTT/NEAR operators)
        search_query = boolean_query if boolean_query else query

        # Append inline doctype filter if court specified
        if court_filter:
            normalized = IK_COURT_CODES.get(
                court_filter.lower().replace(" ", "_"), court_filter,
            )
            search_query += f" doctypes: {normalized}"

        if title_filter:
            search_query += f" title: {title_filter}"
        if cite_filter:
            search_query += f" cite: {cite_filter}"
        if author_filter:
            search_query += f" author: {author_filter}"
        if bench_filter:
            search_query += f" bench: {bench_filter}"

        all_docs: list[dict] = []
        for page in range(max_pages):
            params: dict[str, str] = {
                "formInput": search_query,
                "pagenum": str(page),
            }
            if from_date:
                params["fromdate"] = from_date
            if to_date:
                params["todate"] = to_date
            if sort_by:
                params["sortby"] = sort_by
            if max_cites is not None:
                params["maxcites"] = str(max_cites)

            url = f"{self.BASE_URL}/search/"
            result = await self._rate_limited_post(url, data=params)
            docs = result.get("docs", [])
            all_docs.extend(docs)

            if len(docs) < 10:  # Last page
                break

        return all_docs[:max_results]

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
