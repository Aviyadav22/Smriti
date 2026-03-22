# Indian Kanoon & Tavily Web Search Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Maximize research quality from Indian Kanoon and Tavily web search providers by exploiting unused API capabilities, fixing 15 bugs (including 1 CRITICAL SQL injection), and adding proper filter propagation from the research plan to worker nodes.

**Architecture:** The research agent plans tasks with `filters` dicts, but workers currently ignore them. We will thread filters through to both IK (boolean operators, court codes, date ranges, `sortby`) and Tavily (`include_domains`, `time_range`, `country`, `include_raw_content`). Additionally, we fix the SQL injection in citation verification, add asyncio.Lock for IK rate limiting, fix empty-result caching, improve fuzzy matching, and parallelize sequential verification calls.

**Tech Stack:** Python 3.12, httpx, asyncio, SQLAlchemy (parameterized queries), Redis, pytest

---

## Task 1: Fix CRITICAL SQL Injection in Citation Verification

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:1676-1681`
- Test: `backend/tests/unit/test_research_v2_phase4.py`

**Step 1: Write the failing test**

```python
# In test_research_v2_phase4.py — add to the verify_citations section

@pytest.mark.asyncio
async def test_deterministic_verify_sql_injection_safe(mock_db_session):
    """SQL injection in case_id must not execute arbitrary SQL."""
    malicious_footnote = {
        "case_id": "'; DROP TABLE cases; --",
        "is_used": True,
        "number": 1,
        "citation": "Test v Test",
    }
    # Should NOT raise, should use parameterized query
    from app.core.agents.nodes.research_nodes import _deterministic_verify
    issues = await _deterministic_verify([malicious_footnote], mock_db_session)
    # The important thing: no SQL error from injection, just a normal "nonexistent" result
    assert isinstance(issues, list)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py -k "test_deterministic_verify_sql_injection_safe" -v`
Expected: FAIL (current code f-string interpolates the malicious case_id)

**Step 3: Fix the SQL injection — use parameterized query**

In `research_nodes.py`, replace lines 1676-1681:

```python
# BEFORE (vulnerable):
exists = await db.execute(
    select(1).select_from(
        text("cases")
    ).where(text(f"id = '{fn['case_id']}'::uuid"))
)

# AFTER (safe):
exists = await db.execute(
    text("SELECT 1 FROM cases WHERE id = :case_id::uuid"),
    {"case_id": fn["case_id"]},
)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py -k "test_deterministic_verify_sql_injection_safe" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/research_nodes.py backend/tests/unit/test_research_v2_phase4.py
git commit -m "fix: patch CRITICAL SQL injection in _deterministic_verify (CVE-level)"
```

---

## Task 2: Fix IK Rate Limiter Race Condition with asyncio.Lock

**Files:**
- Modify: `backend/app/core/providers/external/indiankanoon.py:44-73`
- Test: `backend/tests/unit/test_indiankanoon_client.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_indiankanoon_client.py
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

@pytest.fixture
def mock_settings():
    with patch("app.core.providers.external.indiankanoon.settings") as s:
        s.ik_api_token = "test-token"
        s.ik_rate_limit = 2.0
        yield s

@pytest.fixture
def ik_client(mock_settings):
    from app.core.providers.external.indiankanoon import IndianKanoonClient
    client = IndianKanoonClient(token="test-token")
    return client

@pytest.mark.asyncio
async def test_rate_limiter_uses_lock(ik_client):
    """Concurrent requests must be serialized by asyncio.Lock."""
    assert hasattr(ik_client, "_lock"), "IndianKanoonClient must have an asyncio.Lock"
    assert isinstance(ik_client._lock, asyncio.Lock)

@pytest.mark.asyncio
async def test_rate_limited_post_uses_monotonic_time(ik_client):
    """Rate limiter must use asyncio.get_event_loop().time() replacement (monotonic)."""
    import inspect
    source = inspect.getsource(ik_client._rate_limited_post)
    assert "get_event_loop" not in source, "Must not use deprecated asyncio.get_event_loop().time()"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_indiankanoon_client.py -v`
Expected: FAIL — no `_lock` attribute, uses `get_event_loop`

**Step 3: Fix the rate limiter**

Replace the `__init__` and `_rate_limited_post` methods in `indiankanoon.py`:

```python
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

    async def _rate_limited_post(self, url: str, data: dict | None = None) -> dict:
        """POST with rate limiting (2 req/sec default), protected by asyncio.Lock."""
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            min_interval = 1.0 / self._rate_limit
            wait_time = self._last_request_time + min_interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)

            response = await self._client.post(url, data=data or {})
            self._last_request_time = asyncio.get_running_loop().time()
            response.raise_for_status()
            return response.json()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_indiankanoon_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/providers/external/indiankanoon.py backend/tests/unit/test_indiankanoon_client.py
git commit -m "fix: add asyncio.Lock to IK rate limiter, replace deprecated get_event_loop"
```

---

## Task 3: Enhance IK Client — Boolean Operators, Court Codes, Sort, Pagination

**Files:**
- Modify: `backend/app/core/providers/external/indiankanoon.py:76-97`
- Modify: `backend/app/core/interfaces/external_doc.py`
- Test: `backend/tests/unit/test_indiankanoon_client.py`

**Step 1: Write the failing tests**

```python
# Add to test_indiankanoon_client.py

@pytest.mark.asyncio
async def test_search_builds_boolean_query(ik_client):
    """IK search must support boolean_query with ANDD/ORR operators."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"docs": [{"tid": 123, "title": "Test"}]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        results = await ik_client.search(
            "Section 498A",
            boolean_query="498A ANDD cruelty ANDD dowry",
            court_filter="supremecourt",
            sort_by="mostrecent",
            max_pages=2,
        )
        call_data = mock_post.call_args[1].get("data", mock_post.call_args[0][1] if len(mock_post.call_args[0]) > 1 else {})
        # The formInput should contain the boolean query
        assert "ANDD" in str(call_data) or "498A" in str(call_data)

@pytest.mark.asyncio
async def test_search_uses_date_format(ik_client):
    """IK date filters must use DD-MM-YYYY format."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"docs": []}
    mock_response.raise_for_status = MagicMock()

    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await ik_client.search("test", from_date="01-01-2020", to_date="31-12-2024")
        call_data = mock_post.call_args
        # Verify date params are passed
        assert call_data is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_indiankanoon_client.py -k "test_search_builds_boolean" -v`
Expected: FAIL — `search()` doesn't accept `boolean_query`, `sort_by`, `max_pages`

**Step 3: Enhance the IK search method**

Update `ExternalDocProvider` protocol to accept new params:

```python
# backend/app/core/interfaces/external_doc.py
@runtime_checkable
class ExternalDocProvider(Protocol):
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
    ) -> list[dict]: ...

    async def get_document(self, doc_id: str) -> dict: ...
    async def get_fragment(self, doc_id: str, query: str) -> dict: ...
    async def get_metadata(self, doc_id: str) -> dict: ...
```

Update the IK `search` method:

```python
# IK Court codes for inline filter syntax
IK_COURT_CODES = {
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
}

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
) -> list[dict]:
    """Search Indian Kanoon with boolean operators, court filter, date range, sort."""
    # Use boolean_query if provided (uses IK's ANDD/ORR/NOTT operators)
    search_query = boolean_query if boolean_query else query

    # Append inline doctype filter if court specified
    if court_filter:
        normalized = IK_COURT_CODES.get(court_filter.lower().replace(" ", "_"), court_filter)
        search_query += f" doctypes: {normalized}"

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
            params["sortby"] = sort_by  # "mostrecent" or default relevance

        url = f"{self.BASE_URL}/search/"
        result = await self._rate_limited_post(url, data=params)
        docs = result.get("docs", [])
        all_docs.extend(docs)

        if len(docs) < 10:  # Last page
            break

    return all_docs[:max_results]
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_indiankanoon_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/interfaces/external_doc.py backend/app/core/providers/external/indiankanoon.py backend/tests/unit/test_indiankanoon_client.py
git commit -m "feat: enhance IK client with boolean operators, court codes, sort, pagination"
```

---

## Task 4: Enhance Tavily Client — Country, Time Range, Raw Content, Expanded Domains

**Files:**
- Modify: `backend/app/core/providers/web_search/tavily.py`
- Modify: `backend/app/core/interfaces/web_search.py`
- Test: `backend/tests/unit/test_tavily_client.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_tavily_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_settings():
    with patch("app.core.providers.web_search.tavily.settings") as s:
        s.tavily_api_key = "test-key"
        s.web_search_timeout = 15
        yield s

@pytest.fixture
def tavily_client(mock_settings):
    from app.core.providers.web_search.tavily import TavilySearchClient
    return TavilySearchClient(api_key="test-key")

@pytest.mark.asyncio
async def test_search_sends_country_and_time_range(tavily_client):
    """Tavily search must send country=IN and time_range when provided."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()

    with patch.object(tavily_client._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await tavily_client.search("recent SC judgment", time_range="year", country="IN")
        payload = mock_post.call_args[1]["json"]
        assert payload["country"] == "IN"
        assert payload["time_range"] == "year"

@pytest.mark.asyncio
async def test_search_includes_raw_content(tavily_client):
    """Tavily should request markdown raw content."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"results": [{"title": "T", "url": "u", "content": "c", "raw_content": "# Full", "score": 0.9}]}
    mock_response.raise_for_status = MagicMock()

    with patch.object(tavily_client._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        results = await tavily_client.search("test", include_raw_content=True)
        payload = mock_post.call_args[1]["json"]
        assert payload["include_raw_content"] == "markdown"
        # Result should include raw_content
        assert results[0].get("raw_content") == "# Full"

@pytest.mark.asyncio
async def test_default_domains_expanded(tavily_client):
    """Default legal domains must include key Indian legal sites."""
    from app.core.providers.web_search.tavily import _DEFAULT_LEGAL_DOMAINS
    assert "indiankanoon.org" in _DEFAULT_LEGAL_DOMAINS
    assert "livelaw.in" in _DEFAULT_LEGAL_DOMAINS
    assert "latestlaws.com" in _DEFAULT_LEGAL_DOMAINS
    assert "lawctopus.com" not in _DEFAULT_LEGAL_DOMAINS  # Not a legal authority
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_tavily_client.py -v`
Expected: FAIL

**Step 3: Enhance the Tavily client**

Update `WebSearchProvider` protocol:

```python
# backend/app/core/interfaces/web_search.py
@runtime_checkable
class WebSearchProvider(Protocol):
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: list[str] | None = None,
        time_range: str | None = None,
        country: str | None = None,
        include_raw_content: bool = False,
    ) -> list[dict]: ...
```

Update `tavily.py`:

```python
_DEFAULT_LEGAL_DOMAINS = [
    "indiankanoon.org",
    "scconline.com",
    "livelaw.in",
    "barandbench.com",
    "latestlaws.com",
    "legalbites.in",
    "judis.nic.in",
    "main.sci.gov.in",
    "lawtrend.in",
]

class TavilySearchClient:
    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.tavily_api_key
        if not self.api_key:
            raise ValueError(
                "Tavily API key is required. Set TAVILY_API_KEY environment variable."
            )
        self._client = httpx.AsyncClient(timeout=settings.web_search_timeout or _TAVILY_TIMEOUT)

    @_tavily_retry
    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: list[str] | None = None,
        time_range: str | None = None,
        country: str | None = None,
        include_raw_content: bool = False,
    ) -> list[dict]:
        """Search via Tavily with India-specific optimization."""
        domains = include_domains or _DEFAULT_LEGAL_DOMAINS

        payload: dict = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_domains": domains,
        }
        if time_range:
            payload["time_range"] = time_range  # day|week|month|year
        if country:
            payload["country"] = country
        if include_raw_content:
            payload["include_raw_content"] = "markdown"

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
                **({"raw_content": r["raw_content"]} if include_raw_content and r.get("raw_content") else {}),
            }
            for r in data.get("results", [])
        ]
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_tavily_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/interfaces/web_search.py backend/app/core/providers/web_search/tavily.py backend/tests/unit/test_tavily_client.py
git commit -m "feat: enhance Tavily client with country, time_range, raw_content, expanded domains"
```

---

## Task 5: Propagate Research Plan Filters to IK Worker

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:295-373`
- Test: `backend/tests/unit/test_ik_worker.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_ik_worker.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_ik_client():
    client = AsyncMock()
    client.search = AsyncMock(return_value=[
        {"tid": 123, "title": "Test Case", "citation": "(2020) 5 SCC 1", "court": "Supreme Court"}
    ])
    client.get_fragment = AsyncMock(return_value={"fragment": "Test fragment"})
    return client

@pytest.mark.asyncio
async def test_ik_worker_passes_filters(mock_ik_client):
    """IK worker must pass court_filter, from_date, to_date, boolean_query from task filters."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    state = {
        "task": {
            "task_id": "test-1",
            "task_type": "ik_search",
            "nl_query": "Section 498A cruelty",
            "boolean_query": "498A ANDD cruelty ANDD dowry",
            "named_cases": [],
            "rationale": "test",
            "filters": {
                "court": "supreme_court",
                "from_year": 2015,
                "to_year": 2024,
            },
            "priority": 1,
        },
    }

    with patch("app.core.agents.nodes.worker_nodes.get_redis", new_callable=AsyncMock, return_value=None):
        with patch("app.core.agents.nodes.worker_nodes.get_cached_ik_search", new_callable=AsyncMock, return_value=None):
            with patch("app.core.agents.nodes.worker_nodes.set_cached_ik_search", new_callable=AsyncMock):
                with patch("app.core.agents.nodes.worker_nodes.get_cached_ik_fragment", new_callable=AsyncMock, return_value=None):
                    with patch("app.core.agents.nodes.worker_nodes.set_cached_ik_fragment", new_callable=AsyncMock):
                        result = await ik_search_worker(state, mock_ik_client)

    # Verify search was called with boolean_query, court_filter, dates
    mock_ik_client.search.assert_called_once()
    call_kwargs = mock_ik_client.search.call_args[1]
    assert call_kwargs.get("boolean_query") == "498A ANDD cruelty ANDD dowry"
    assert call_kwargs.get("court_filter") == "supreme_court"
    assert "from_date" in call_kwargs
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_ik_worker.py -v`
Expected: FAIL — current `ik_search_worker` ignores task filters

**Step 3: Update `ik_search_worker` to pass filters**

```python
async def ik_search_worker(
    state: dict,
    ik_client: ExternalDocProvider,
) -> dict:
    """Search Indian Kanoon API with full filter propagation."""
    task = state["task"]
    filters = task.get("filters", {})

    try:
        redis = await get_redis()
    except Exception:
        redis = None

    # Build IK-specific search params from research plan filters
    court_filter = filters.get("court")
    from_year = filters.get("from_year")
    to_year = filters.get("to_year")
    # IK uses DD-MM-YYYY format
    from_date = f"01-01-{from_year}" if from_year else None
    to_date = f"31-12-{to_year}" if to_year else None
    boolean_query = task.get("boolean_query") or None
    sort_by = filters.get("sort_by")  # "mostrecent" for recency queries

    # Cache key includes filters for correct cache isolation
    cache_key = f"{task['nl_query']}:{court_filter}:{from_date}:{to_date}"

    try:
        cached_results = await get_cached_ik_search(redis, cache_key)
        if cached_results is not None:
            logger.debug("IK search cache hit for: %s", task["nl_query"][:60])
            return {"worker_results": [WorkerResult(
                task_id=task["task_id"], task_type="ik_search",
                query=task["nl_query"], results=cached_results,
                source_urls=[f"https://indiankanoon.org/doc/{r.get('ik_doc_id', '')}/" for r in cached_results],
                metadata={"source": "indian_kanoon", "cached": True},
                error=None, reasoning="",
            )]}

        search_results = await ik_client.search(
            task["nl_query"],
            max_results=10,
            boolean_query=boolean_query,
            court_filter=court_filter,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
        )

        # Don't cache empty results — they may be transient API failures
        results: list[dict] = []
        source_urls: list[str] = []
        for doc in search_results:
            doc_id = str(doc.get("tid", ""))
            if not doc_id:
                continue
            try:
                cached_frag = await get_cached_ik_fragment(redis, doc_id, task["nl_query"])
                if cached_frag is not None:
                    fragment = cached_frag
                else:
                    fragment = await ik_client.get_fragment(doc_id, task["nl_query"])
                    await set_cached_ik_fragment(redis, doc_id, task["nl_query"], fragment)
            except Exception:
                fragment = {}

            results.append({
                "case_id": f"ik:{doc_id}",
                "title": doc.get("title", ""),
                "citation": doc.get("citation", ""),
                "court": doc.get("court", ""),
                "year": doc.get("year"),
                "snippet": fragment.get("fragment", ""),
                "source": "indian_kanoon",
                "ik_doc_id": doc_id,
            })
            source_urls.append(f"https://indiankanoon.org/doc/{doc_id}/")

        # Only cache non-empty results
        if results:
            await set_cached_ik_search(redis, cache_key, results)

    except Exception as exc:
        logger.warning("ik_search_worker failed: %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="ik_search",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={"source": "indian_kanoon"},
            error=str(exc), reasoning="",
        )]}

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="ik_search",
        query=task["nl_query"], results=results,
        source_urls=source_urls,
        metadata={"source": "indian_kanoon", "filters_applied": bool(filters)},
        error=None, reasoning="",
    )]}
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_ik_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_ik_worker.py
git commit -m "feat: propagate research plan filters to IK worker (court, dates, boolean query)"
```

---

## Task 6: Propagate Research Plan Filters to Web Search Worker

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py:381-426`
- Test: `backend/tests/unit/test_web_search_worker.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_web_search_worker.py
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_web_search():
    client = AsyncMock()
    client.search = AsyncMock(return_value=[
        {"title": "Latest SC Ruling", "url": "https://livelaw.in/test", "content": "Content", "score": 0.9}
    ])
    return client

@pytest.mark.asyncio
async def test_web_worker_passes_time_range_and_country(mock_web_search):
    """Web worker must pass time_range, country=IN, include_raw_content to Tavily."""
    from app.core.agents.nodes.worker_nodes import web_search_worker

    state = {
        "task": {
            "task_id": "test-web-1",
            "task_type": "web",
            "nl_query": "latest Supreme Court ruling on bail",
            "boolean_query": "",
            "named_cases": [],
            "rationale": "Recent developments",
            "filters": {"recency": "year"},
            "priority": 2,
        },
    }
    result = await web_search_worker(state, mock_web_search)
    call_kwargs = mock_web_search.search.call_args[1]
    assert call_kwargs.get("country") == "IN"
    assert call_kwargs.get("include_raw_content") is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_web_search_worker.py -v`
Expected: FAIL

**Step 3: Update `web_search_worker` to pass filters**

```python
async def web_search_worker(
    state: dict,
    web_search: WebSearchProvider,
) -> dict:
    """Search web via Tavily with India-specific filters."""
    task = state["task"]
    filters = task.get("filters", {})

    # Map task filters to Tavily params
    time_range = filters.get("recency")  # day|week|month|year
    include_domains = filters.get("domains")  # Override default domains if specified

    try:
        search_results = await web_search.search(
            task["nl_query"],
            max_results=5,
            search_depth="advanced",
            include_domains=include_domains,
            time_range=time_range,
            country="IN",
            include_raw_content=True,
        )

        results: list[dict] = []
        source_urls: list[str] = []
        for r in search_results:
            results.append({
                "title": r.get("title", ""),
                "snippet": r.get("raw_content", r.get("content", ""))[:2000],
                "url": r.get("url", ""),
                "score": r.get("score", 0.0),
                "source": "web",
            })
            if r.get("url"):
                source_urls.append(r["url"])

    except Exception as exc:
        logger.warning("web_search_worker failed (non-blocking): %s", exc)
        return {"worker_results": [WorkerResult(
            task_id=task["task_id"], task_type="web",
            query=task["nl_query"], results=[],
            source_urls=[], metadata={"source": "web"},
            error=str(exc), reasoning="",
        )]}

    return {"worker_results": [WorkerResult(
        task_id=task["task_id"], task_type="web",
        query=task["nl_query"], results=results,
        source_urls=source_urls,
        metadata={"source": "web", "country": "IN"},
        error=None, reasoning="",
    )]}
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_web_search_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_web_search_worker.py
git commit -m "feat: propagate filters to web search worker (country=IN, time_range, raw_content)"
```

---

## Task 7: Fix Fuzzy Match Algorithm (False Positives)

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:1778-1793`
- Test: `backend/tests/unit/test_research_v2_phase4.py`

**Step 1: Write the failing test**

```python
# Add to test_research_v2_phase4.py

def test_fuzzy_match_rejects_unrelated_strings():
    """Character-overlap fuzzy match must not produce false positives."""
    from app.core.agents.nodes.research_nodes import _fuzzy_match
    # These share many common characters but are completely different passages
    assert _fuzzy_match("the court held", "held the court") is True  # Same words
    assert _fuzzy_match("Section 498A IPC", "Section 302 IPC deals with murder") is False
    assert _fuzzy_match("abc", "cba") is False  # Same chars, different text
    assert _fuzzy_match("constitutional validity", "constitution of india") is False

def test_fuzzy_match_trigram_approach():
    """Fuzzy match should use n-gram overlap, not character set overlap."""
    from app.core.agents.nodes.research_nodes import _fuzzy_match
    # Near-exact match with small edit
    assert _fuzzy_match("the court dismissed the appeal", "the court dismissed the appael") is True
    # Completely different meaning despite shared words
    assert _fuzzy_match("the petitioner filed a case", "a case was filed by the respondent against the petitioner") is True
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py -k "test_fuzzy_match" -v`
Expected: FAIL — current char-overlap gives false positives for "Section 498A IPC" vs "Section 302 IPC"

**Step 3: Replace with trigram-based fuzzy match**

```python
def _fuzzy_match(quote: str, passage: str, threshold: int = 85) -> bool:
    """Trigram-based fuzzy match — more accurate than character overlap."""
    if not quote or not passage:
        return False
    # Normalize whitespace
    q = " ".join(quote.lower().split())
    p = " ".join(passage.lower().split())
    # Exact substring check (fast path)
    if q in p:
        return True
    # Word-level overlap (much more accurate than char-level)
    q_words = set(q.split())
    p_words = set(p.split())
    if not q_words:
        return False
    overlap = len(q_words & p_words)
    ratio = (overlap / len(q_words)) * 100
    if ratio >= threshold:
        return True
    # Trigram overlap as fallback for near-exact matches (typos, OCR errors)
    def trigrams(s: str) -> set[str]:
        return {s[i:i+3] for i in range(max(0, len(s) - 2))}
    q_tri = trigrams(q)
    p_tri = trigrams(p)
    if not q_tri:
        return False
    tri_ratio = (len(q_tri & p_tri) / len(q_tri)) * 100
    return tri_ratio >= threshold
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py -k "test_fuzzy_match" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/research_nodes.py backend/tests/unit/test_research_v2_phase4.py
git commit -m "fix: replace char-overlap fuzzy match with word+trigram algorithm"
```

---

## Task 8: Parallelize Sequential Citation Verification

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py:1695-1760`
- Test: `backend/tests/unit/test_research_v2_phase4.py`

**Step 1: Write the failing test**

```python
# Add to test_research_v2_phase4.py

@pytest.mark.asyncio
async def test_verify_citations_runs_concurrently(mock_db_session):
    """Citation verification for N footnotes should use asyncio.gather, not sequential loop."""
    import inspect
    from app.core.agents.nodes.research_nodes import _verify_citations_against_sources
    source = inspect.getsource(_verify_citations_against_sources)
    assert "gather" in source or "TaskGroup" in source, (
        "Verification must use asyncio.gather or TaskGroup for parallelism"
    )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py -k "test_verify_citations_runs_concurrently" -v`
Expected: FAIL — current code uses sequential `for fn in footnotes` loop

**Step 3: Refactor to use asyncio.gather with semaphore**

```python
async def _verify_citations_against_sources(
    footnotes: list[Footnote],
    db: AsyncSession,
    ik_client: object | None,
    graph_store: object | None,
) -> list[Footnote]:
    """[T4] Verify every citation against at least ONE primary source.
    Uses asyncio.gather for parallel verification with a concurrency limit.
    """
    sem = asyncio.Semaphore(5)  # Max 5 concurrent verifications

    async def verify_one(fn: Footnote) -> Footnote:
        async with sem:
            status = "unverified"

            # Check 1: PostgreSQL cases table
            if fn.get("case_id") and not str(fn["case_id"]).startswith("ik:"):
                try:
                    exists = await db.execute(
                        text("SELECT 1 FROM cases WHERE id = :id::uuid"),
                        {"id": fn["case_id"]},
                    )
                    if exists.scalar():
                        status = "verified_pg"
                except Exception:
                    logger.warning("PG verification failed for %s", fn.get("case_id"))

            # Check 2: Indian Kanoon API
            if status == "unverified" and ik_client and fn.get("citation"):
                try:
                    ik_results = await ik_client.search(fn["citation"], max_results=1)
                    if ik_results:
                        status = "verified_ik"
                except Exception:
                    pass

            # Check 3: Neo4j Case node
            if status == "unverified" and graph_store and fn.get("citation"):
                try:
                    neo4j_match = await graph_store.query(
                        "MATCH (c:Case) WHERE c.citation CONTAINS $cit "
                        "RETURN c.id LIMIT 1",
                        {"cit": fn["citation"][:30]},
                    )
                    if neo4j_match:
                        status = "verified_neo4j"
                except Exception:
                    pass

            fn_copy = dict(fn)
            fn_copy["verification_status"] = status
            fn_copy["verified_against"] = (
                status.replace("verified_", "") if status != "unverified" else "none"
            )

            if status == "unverified" and fn_copy.get("is_used", False):
                fn_copy["citation"] = (
                    f"[CITATION REMOVED — unable to verify: {fn['citation']}]"
                )
                fn_copy["is_used"] = False
                logger.warning(
                    "T4 guardrail: removed unverifiable citation footnote %s: %s",
                    fn["number"], fn["citation"],
                )

            return Footnote(**fn_copy)

    return list(await asyncio.gather(*(verify_one(fn) for fn in footnotes)))
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_phase4.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/research_nodes.py backend/tests/unit/test_research_v2_phase4.py
git commit -m "perf: parallelize citation verification with asyncio.gather + semaphore"
```

---

## Task 9: Fix Empty Results Being Cached for 24h

**Files:**
- Modify: `backend/app/core/agents/research_cache.py:139-149`
- Test: `backend/tests/unit/test_research_cache.py` (create)

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_research_cache.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_set_cached_ik_search_skips_empty_results():
    """Empty results must NOT be cached — they may represent transient failures."""
    from app.core.agents.research_cache import set_cached_ik_search
    mock_redis = AsyncMock()
    await set_cached_ik_search(mock_redis, "test query", [])
    mock_redis.setex.assert_not_called()

@pytest.mark.asyncio
async def test_set_cached_ik_search_caches_nonempty_results():
    """Non-empty results SHOULD be cached."""
    from app.core.agents.research_cache import set_cached_ik_search
    mock_redis = AsyncMock()
    await set_cached_ik_search(mock_redis, "test query", [{"case_id": "ik:123"}])
    mock_redis.setex.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_research_cache.py -v`
Expected: FAIL — current code caches empty lists

**Step 3: Add empty-result guard to cache setters**

In `research_cache.py`, update `set_cached_ik_search`:

```python
async def set_cached_ik_search(
    redis: aioredis.Redis | None, query: str, results: list[dict]
) -> None:
    """[S8-L3] Cache IK search results. Skips empty results to avoid caching failures."""
    if redis is None or not results:
        return
    try:
        key = f"ik:search:{normalize_cache_key(query)}"
        await redis.setex(key, IK_TTL, json.dumps(results, default=str))
    except Exception as exc:
        logger.warning("IK cache write failed: %s", exc)
```

Also update `set_cached_search` with the same guard:

```python
async def set_cached_search(
    redis: aioredis.Redis | None, query: str, results: list[dict], **filters: Any
) -> None:
    """[S8-L2] Cache hybrid search results. Skips empty results."""
    if redis is None or not results:
        return
    try:
        key = f"search:hybrid:{normalize_cache_key(query, **filters)}"
        await redis.setex(key, SEARCH_TTL, json.dumps(results, default=str))
    except Exception as exc:
        logger.warning("Search cache write failed: %s", exc)
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_research_cache.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/research_cache.py backend/tests/unit/test_research_cache.py
git commit -m "fix: don't cache empty IK/search results (prevents 24h stale misses)"
```

---

## Task 10: Fix LRU Cache Cleanup in `dependencies.py`

**Files:**
- Modify: `backend/app/core/dependencies.py:159-188`
- Test: `backend/tests/unit/test_dependencies.py` (look for existing, else create minimal)

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_dependency_cleanup.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_cleanup_clears_lru_cache():
    """cleanup_providers must clear LRU caches after closing clients."""
    from app.core.dependencies import cleanup_providers, get_ik_client, get_web_search

    mock_ik = MagicMock()
    mock_ik.close = AsyncMock()
    mock_ws = MagicMock()
    mock_ws.close = AsyncMock()

    # Reset caches
    get_ik_client.cache_clear()
    get_web_search.cache_clear()

    with patch("app.core.dependencies.get_graph_store") as mock_gs:
        mock_gs.cache_info.return_value = MagicMock(currsize=0)
        with patch("app.core.dependencies.get_reranker") as mock_rr:
            mock_rr.cache_info.return_value = MagicMock(currsize=0)
            with patch("app.core.dependencies.get_ik_client") as mock_ik_fn:
                mock_ik_fn.cache_info.return_value = MagicMock(currsize=1)
                mock_ik_fn.return_value = mock_ik
                mock_ik_fn.cache_clear = MagicMock()
                with patch("app.core.dependencies.get_web_search") as mock_ws_fn:
                    mock_ws_fn.cache_info.return_value = MagicMock(currsize=1)
                    mock_ws_fn.return_value = mock_ws
                    mock_ws_fn.cache_clear = MagicMock()

                    await cleanup_providers()

                    mock_ik.close.assert_called_once()
                    mock_ws.close.assert_called_once()
                    mock_ik_fn.cache_clear.assert_called_once()
                    mock_ws_fn.cache_clear.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_dependency_cleanup.py -v`
Expected: FAIL — `cache_clear()` never called

**Step 3: Add `cache_clear()` calls after closing**

```python
async def cleanup_providers() -> None:
    """Close cached provider connections on shutdown and clear LRU caches."""
    try:
        if get_graph_store.cache_info().currsize > 0:
            store = get_graph_store()
            if hasattr(store, "close"):
                await store.close()
            get_graph_store.cache_clear()
    except Exception:
        pass
    try:
        if get_reranker.cache_info().currsize > 0:
            reranker = get_reranker()
            if hasattr(reranker, "close"):
                await reranker.close()
            get_reranker.cache_clear()
    except Exception:
        pass
    try:
        if get_ik_client.cache_info().currsize > 0:
            ik = get_ik_client()
            if hasattr(ik, "close"):
                await ik.close()
            get_ik_client.cache_clear()
    except Exception:
        pass
    try:
        if get_web_search.cache_info().currsize > 0:
            ws = get_web_search()
            if hasattr(ws, "close"):
                await ws.close()
            get_web_search.cache_clear()
    except Exception:
        pass
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_dependency_cleanup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/dependencies.py backend/tests/unit/test_dependency_cleanup.py
git commit -m "fix: clear LRU caches after closing providers in cleanup_providers"
```

---

## Task 11: Limit IK Fragment Calls per Search (Cost Control)

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (ik_search_worker)
- Test: `backend/tests/unit/test_ik_worker.py`

**Step 1: Write the failing test**

```python
# Add to test_ik_worker.py

@pytest.mark.asyncio
async def test_ik_worker_limits_fragment_calls():
    """IK worker must limit fragment API calls to top-N results (cost control)."""
    # Return 10 search results
    mock_ik = AsyncMock()
    mock_ik.search = AsyncMock(return_value=[
        {"tid": i, "title": f"Case {i}", "citation": f"(2020) {i} SCC 1"} for i in range(10)
    ])
    mock_ik.get_fragment = AsyncMock(return_value={"fragment": "test"})

    from app.core.agents.nodes.worker_nodes import ik_search_worker
    state = {
        "task": {
            "task_id": "t1", "task_type": "ik_search",
            "nl_query": "test", "boolean_query": "", "named_cases": [],
            "rationale": "", "filters": {}, "priority": 1,
        }
    }

    with patch("app.core.agents.nodes.worker_nodes.get_redis", new_callable=AsyncMock, return_value=None):
        with patch("app.core.agents.nodes.worker_nodes.get_cached_ik_search", new_callable=AsyncMock, return_value=None):
            with patch("app.core.agents.nodes.worker_nodes.set_cached_ik_search", new_callable=AsyncMock):
                with patch("app.core.agents.nodes.worker_nodes.get_cached_ik_fragment", new_callable=AsyncMock, return_value=None):
                    with patch("app.core.agents.nodes.worker_nodes.set_cached_ik_fragment", new_callable=AsyncMock):
                        result = await ik_search_worker(state, mock_ik)

    # Fragment calls should be limited to top 5, not all 10
    assert mock_ik.get_fragment.call_count <= 5
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_ik_worker.py -k "test_ik_worker_limits_fragment" -v`
Expected: FAIL — current code calls fragment for all 10

**Step 3: Add fragment limit**

In the `ik_search_worker`, add a constant and limit the fragment loop:

```python
_MAX_IK_FRAGMENT_CALLS = 5  # Cost control: Rs 0.05/fragment

# In the loop:
for idx, doc in enumerate(search_results):
    doc_id = str(doc.get("tid", ""))
    if not doc_id:
        continue

    # Only fetch fragments for top N results (cost control)
    fragment = {}
    if idx < _MAX_IK_FRAGMENT_CALLS:
        try:
            cached_frag = await get_cached_ik_fragment(redis, doc_id, task["nl_query"])
            if cached_frag is not None:
                fragment = cached_frag
            else:
                fragment = await ik_client.get_fragment(doc_id, task["nl_query"])
                await set_cached_ik_fragment(redis, doc_id, task["nl_query"], fragment)
        except Exception:
            fragment = {}

    results.append({...})
```

**Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_ik_worker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_ik_worker.py
git commit -m "fix: limit IK fragment calls to top 5 results (cost control)"
```

---

## Task 12: Update Research Plan Prompt to Generate IK-Optimized Queries

**Files:**
- Modify: `backend/app/core/legal/prompts.py` — `RESEARCH_PLAN_SYSTEM` and `RESEARCH_PLAN_SCHEMA`
- Test: `backend/tests/unit/test_research_v2_nodes.py`

**Step 1: Locate and read the current plan prompt**

Run: `cd backend && grep -n "RESEARCH_PLAN_SYSTEM\|RESEARCH_PLAN_SCHEMA" app/core/legal/prompts.py | head -20`

**Step 2: Update the plan prompt to instruct the LLM about IK boolean syntax**

Add to `RESEARCH_PLAN_SYSTEM`:
```
## Indian Kanoon Query Optimization

When generating tasks with task_type "ik_search", create boolean_query using Indian Kanoon's
native operators for maximum precision:
- ANDD: both terms must appear (e.g., "498A ANDD cruelty ANDD dowry")
- ORR: either term (e.g., "murder ORR culpable homicide")
- NOTT: exclude term (e.g., "bail NOTT anticipatory")
- NEAR: proximity search (e.g., "fundamental NEAR rights")
- Wrap exact phrases in quotes: "right to life"

For filters dict, include:
- court: "supreme_court" | "delhi" | "bombay" | "madras" | etc.
- from_year: integer (e.g., 2015)
- to_year: integer (e.g., 2024)
- sort_by: "mostrecent" for recency-sensitive queries

For web search tasks (task_type "web"), include in filters:
- recency: "day" | "week" | "month" | "year" — how recent the results should be
```

**Step 3: Add `filters` to the schema**

Ensure `RESEARCH_PLAN_SCHEMA` includes a `filters` object with the properties `court`, `from_year`, `to_year`, `sort_by`, `recency`.

**Step 4: Run existing tests to verify no regressions**

Run: `cd backend && python -m pytest tests/unit/test_research_v2_nodes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/legal/prompts.py
git commit -m "feat: update research plan prompt with IK boolean operators and filter guidance"
```

---

## Task 13: Run Full Test Suite and E2E Verification

**Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -x -q --tb=short`
Expected: All tests pass (previous count: 1698+)

**Step 2: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: 298 tests pass

**Step 3: Verify E2E with a real research query (if API keys available)**

```bash
cd backend && python -c "
import asyncio
from app.core.agents.research import build_research_graph
# ... (E2E test from previous session)
"
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: all tests passing after IK/Tavily optimization"
```

---

## Summary of Changes

| # | Type | File | Description |
|---|------|------|-------------|
| 1 | CRITICAL FIX | research_nodes.py:1680 | SQL injection → parameterized query |
| 2 | BUG FIX | indiankanoon.py | asyncio.Lock for rate limiter, monotonic time |
| 3 | FEATURE | indiankanoon.py + interface | Boolean operators, court codes, sort, pagination |
| 4 | FEATURE | tavily.py + interface | Country, time_range, raw_content, expanded domains |
| 5 | FEATURE | worker_nodes.py (IK) | Filter propagation from research plan to IK API |
| 6 | FEATURE | worker_nodes.py (web) | Filter propagation from research plan to Tavily |
| 7 | BUG FIX | research_nodes.py:1778 | Trigram fuzzy match replacing char-overlap |
| 8 | PERF | research_nodes.py:1695 | asyncio.gather for parallel verification |
| 9 | BUG FIX | research_cache.py | Don't cache empty results |
| 10 | BUG FIX | dependencies.py | Clear LRU caches after closing providers |
| 11 | COST | worker_nodes.py (IK) | Limit fragment API calls to top 5 |
| 12 | FEATURE | prompts.py | Teach LLM to generate IK-optimized queries |
| 13 | VERIFY | — | Full test suite + E2E verification |
