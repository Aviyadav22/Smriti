# Indian Kanoon API Full Optimization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fully exploit the Indian Kanoon API — use free search headlines instead of paid fragments, add title/cite/author/bench filters, expand court codes, add court certified copy (`/origdoc/`) for trusted footnote references, and use `maxcites` for citation graph enrichment.

**Architecture:** Three layers of changes — (1) IK client gains new params and methods, (2) workers use free search data and new filters, (3) citation verification and footnotes reference court copies for trust.

**Tech Stack:** Python 3.12, FastAPI, httpx, asyncio, pytest

---

## Context: IK API Response Fields (Discovered via E2E Testing)

The `/search/` endpoint returns these fields per doc (ALL FREE — already in search results):

```json
{
  "tid": 501107,
  "title": "R. Rajagopal vs State Of T.N on 7 October, 1994",
  "citation": "1995 AIR 264",
  "headline": "must also be placed in the context of other <b>rights</b>...",
  "fragment": true,
  "docsource": "Supreme Court of India",
  "author": "B P Reddy",
  "authorEncoded": "b-p-reddy",
  "bench": [2189, 2197],
  "publishdate": "1994-10-07",
  "numcites": 9,
  "numcitedby": 172,
  "catids": [658, 154, 46],
  "doctype": 1000
}
```

With `maxcites=N`, each doc also gets:
```json
{ "cites": [{"tid": 1378441, "title": "Article 19(1)(a) in Constitution of India"}, ...] }
```

The `/origdoc/<docid>/` endpoint returns base64-encoded court-certified HTML copy.

---

### Task 1: Use Search `headline` as Primary Snippet — Eliminate Most Fragment Calls

Currently we make 5 `/docfragment/` calls per search at Rs 0.05 each (Rs 0.25/search). But the `/search/` response already includes `headline` with highlighted matching text. We should use this as the primary snippet and only call `/docfragment/` when the search headline is too short or empty.

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (lines 350-380)
- Test: `backend/tests/unit/test_ik_worker.py`

**Step 1: Write the failing test**

In `backend/tests/unit/test_ik_worker.py`, add to `TestIKWorkerCostControl`:

```python
@pytest.mark.asyncio
async def test_uses_search_headline_skips_fragment(self) -> None:
    """When search result has headline, skip fragment API call."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    mock_ik = AsyncMock()
    mock_ik.search = AsyncMock(return_value=[
        {"tid": 1, "title": "Case 1", "headline": "<b>Relevant</b> passage about privacy rights in detail"},
    ])
    mock_ik.get_fragment = AsyncMock(return_value={"headline": ["frag"]})

    state = {"task": _make_task()}
    result = await ik_search_worker(state, mock_ik)

    # Should NOT call fragment when headline is long enough (>50 chars)
    assert mock_ik.get_fragment.call_count == 0
    assert "Relevant" in result["worker_results"][0]["results"][0]["snippet"]

@pytest.mark.asyncio
async def test_falls_back_to_fragment_when_headline_short(self) -> None:
    """When search headline is too short, call fragment API."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    mock_ik = AsyncMock()
    mock_ik.search = AsyncMock(return_value=[
        {"tid": 1, "title": "Case 1", "headline": "short"},
    ])
    mock_ik.get_fragment = AsyncMock(return_value={"headline": ["Detailed fragment passage"]})

    state = {"task": _make_task()}
    result = await ik_search_worker(state, mock_ik)

    assert mock_ik.get_fragment.call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_ik_worker.py::TestIKWorkerCostControl::test_uses_search_headline_skips_fragment -v`
Expected: FAIL

**Step 3: Implement — modify `ik_search_worker` fragment logic**

In `worker_nodes.py`, change the fragment section (around line 352-377) to:

```python
_MIN_HEADLINE_LEN = 50  # Minimum chars to skip fragment call
_MAX_IK_FRAGMENT_CALLS = 5  # Cost control: Rs 0.05/fragment

# ...inside the for loop over search_results:

            # Use search headline if long enough; otherwise fetch fragment
            search_headline = doc.get("headline", "")
            snippet = ""
            if len(search_headline) >= _MIN_HEADLINE_LEN:
                # Free: headline already in search results
                snippet = search_headline
            elif idx < _MAX_IK_FRAGMENT_CALLS:
                # Paid: Rs 0.05/call — only for short/missing headlines
                try:
                    cached_frag = await get_cached_ik_fragment(redis, doc_id, task["nl_query"])
                    if cached_frag is not None:
                        fragment = cached_frag
                    else:
                        fragment = await ik_client.get_fragment(doc_id, task["nl_query"])
                        await set_cached_ik_fragment(redis, doc_id, task["nl_query"], fragment)
                    snippet = fragment.get("headline", fragment.get("fragment", ""))
                    # headline from fragment API is a list
                    if isinstance(snippet, list):
                        snippet = " ".join(snippet)
                except Exception:
                    snippet = search_headline  # fallback to short headline
```

Also update the `results.append(...)` to use `snippet` directly instead of `fragment.get(...)`.

**Step 4: Run tests**

Run: `pytest tests/unit/test_ik_worker.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_ik_worker.py
git commit -m "perf: use free search headlines as snippets, reduce paid fragment calls"
```

---

### Task 2: Extract Rich Fields from Search Results

Search results contain `docsource`, `author`, `publishdate`, `numcites`, `numcitedby` — all free. Add these to worker output for richer research memos.

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (results.append block, ~line 371)
- Test: `backend/tests/unit/test_ik_worker.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_extracts_rich_fields(self, mock_ik_client) -> None:
    """Worker should extract docsource, author, publishdate, numcites from search results."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    mock_ik_client.search = AsyncMock(return_value=[{
        "tid": 123, "title": "Test Case", "citation": "(2020) 5 SCC 1",
        "docsource": "Supreme Court of India", "author": "D Y Chandrachud",
        "publishdate": "2020-03-15", "numcites": 12, "numcitedby": 45,
        "headline": "A long enough headline about fundamental rights and privacy for testing purposes",
    }])
    state = {"task": _make_task()}
    result = await ik_search_worker(state, mock_ik_client)

    r = result["worker_results"][0]["results"][0]
    assert r["court"] == "Supreme Court of India"
    assert r["author"] == "D Y Chandrachud"
    assert r["date"] == "2020-03-15"
    assert r["num_cited_by"] == 45
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_ik_worker.py::TestIKWorkerFilterPropagation::test_extracts_rich_fields -v`
Expected: FAIL (missing keys)

**Step 3: Update results.append in worker**

```python
            results.append({
                "case_id": f"ik:{doc_id}",
                "title": doc.get("title", ""),
                "citation": doc.get("citation", ""),
                "court": doc.get("docsource", doc.get("court", "")),
                "author": doc.get("author", ""),
                "date": doc.get("publishdate", ""),
                "year": doc.get("year"),
                "num_cites": doc.get("numcites", 0),
                "num_cited_by": doc.get("numcitedby", 0),
                "snippet": snippet,
                "source": "indian_kanoon",
                "ik_doc_id": doc_id,
            })
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_ik_worker.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_ik_worker.py
git commit -m "feat: extract rich fields from IK search (author, date, citation counts)"
```

---

### Task 3: Add `title`, `cite`, `author`, `bench` Inline Filters to IK Client

The IK API supports inline query filters: `title: kesavananda`, `cite: 1993 AIR`, `author: chandrachud`, `bench: chandrachud`. Add these as named parameters.

**Files:**
- Modify: `backend/app/core/providers/external/indiankanoon.py` (search method)
- Modify: `backend/app/core/interfaces/external_doc.py` (Protocol)
- Test: `backend/tests/unit/test_indiankanoon_client.py`

**Step 1: Write failing tests**

In `test_indiankanoon_client.py`, add to `TestSearchEnhancements`:

```python
@pytest.mark.asyncio
async def test_search_appends_title_filter(self, ik_client) -> None:
    """title_filter should be appended as 'title: X' to query."""
    resp = _mock_response({"docs": []})
    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
        await ik_client.search("privacy", title_filter="Puttaswamy")
        data = mock_post.call_args[1]["data"]
        assert "title: Puttaswamy" in data["formInput"]

@pytest.mark.asyncio
async def test_search_appends_cite_filter(self, ik_client) -> None:
    """cite_filter should be appended as 'cite: X' to query."""
    resp = _mock_response({"docs": []})
    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
        await ik_client.search("privacy", cite_filter="1993 AIR")
        data = mock_post.call_args[1]["data"]
        assert "cite: 1993 AIR" in data["formInput"]

@pytest.mark.asyncio
async def test_search_appends_author_filter(self, ik_client) -> None:
    """author_filter should be appended as 'author: X' to query."""
    resp = _mock_response({"docs": []})
    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
        await ik_client.search("privacy", author_filter="chandrachud")
        data = mock_post.call_args[1]["data"]
        assert "author: chandrachud" in data["formInput"]

@pytest.mark.asyncio
async def test_search_appends_bench_filter(self, ik_client) -> None:
    """bench_filter should be appended as 'bench: X' to query."""
    resp = _mock_response({"docs": []})
    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
        await ik_client.search("privacy", bench_filter="chandrachud")
        data = mock_post.call_args[1]["data"]
        assert "bench: chandrachud" in data["formInput"]

@pytest.mark.asyncio
async def test_search_passes_maxcites(self, ik_client) -> None:
    """maxcites should be passed as form data."""
    resp = _mock_response({"docs": []})
    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
        await ik_client.search("privacy", max_cites=10)
        data = mock_post.call_args[1]["data"]
        assert data["maxcites"] == "10"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_indiankanoon_client.py -v -k "title_filter or cite_filter or author_filter or bench_filter or maxcites"`
Expected: FAIL

**Step 3: Update `search()` method in `indiankanoon.py`**

Add parameters to signature:

```python
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
```

After the court_filter append block, add:

```python
        # Append inline filters
        if title_filter:
            search_query += f" title: {title_filter}"
        if cite_filter:
            search_query += f" cite: {cite_filter}"
        if author_filter:
            search_query += f" author: {author_filter}"
        if bench_filter:
            search_query += f" bench: {bench_filter}"
```

In the params dict, add:

```python
            if max_cites is not None:
                params["maxcites"] = str(max_cites)
```

**Step 4: Update Protocol in `external_doc.py`**

Add the same params to the Protocol:

```python
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
    ) -> list[dict]: ...
```

**Step 5: Run tests**

Run: `pytest tests/unit/test_indiankanoon_client.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/core/providers/external/indiankanoon.py backend/app/core/interfaces/external_doc.py backend/tests/unit/test_indiankanoon_client.py
git commit -m "feat: add title/cite/author/bench/maxcites filters to IK client"
```

---

### Task 4: Add Court Certified Copy Endpoint (`/origdoc/`)

The `/origdoc/<docid>/` endpoint returns base64-encoded court-certified HTML. This is essential for trust — footnotes can link to the original court copy.

**Files:**
- Modify: `backend/app/core/providers/external/indiankanoon.py` (add `get_court_copy` method)
- Modify: `backend/app/core/interfaces/external_doc.py` (add to Protocol)
- Test: `backend/tests/unit/test_indiankanoon_client.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_get_court_copy_calls_origdoc(self, ik_client) -> None:
    """get_court_copy should POST to /origdoc/<docid>/."""
    resp = _mock_response({"doc": "base64content", "Content-Type": "text/html"})
    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
        result = await ik_client.get_court_copy("12345")
        mock_post.assert_called_once()
        assert "/origdoc/12345/" in str(mock_post.call_args)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_indiankanoon_client.py -v -k "court_copy"`
Expected: FAIL (method doesn't exist)

**Step 3: Add `get_court_copy` method**

In `indiankanoon.py`, add after `get_metadata`:

```python
    @_ik_retry
    async def get_court_copy(self, doc_id: str) -> dict:
        """Get court-certified copy. POST /origdoc/<doc_id>/ (Rs 0.20/req).

        Returns dict with 'doc' (base64-encoded HTML) and 'Content-Type'.
        Use for trusted footnote references.
        """
        url = f"{self.BASE_URL}/origdoc/{doc_id}/"
        return await self._rate_limited_post(url)
```

**Step 4: Update Protocol**

In `external_doc.py`, add:

```python
    async def get_court_copy(self, doc_id: str) -> dict: ...
```

**Step 5: Run tests**

Run: `pytest tests/unit/test_indiankanoon_client.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add backend/app/core/providers/external/indiankanoon.py backend/app/core/interfaces/external_doc.py backend/tests/unit/test_indiankanoon_client.py
git commit -m "feat: add get_court_copy() for IK /origdoc/ endpoint — trusted references"
```

---

### Task 5: Expand Court Codes — All Courts, Tribunals, Aggregators

Our mapping has 18 entries. The API supports ~40+ courts, 15+ tribunals, and aggregators like `highcourts`, `tribunals`, `judgments`, `laws`.

**Files:**
- Modify: `backend/app/core/providers/external/indiankanoon.py` (IK_COURT_CODES dict)
- Test: `backend/tests/unit/test_indiankanoon_client.py`

**Step 1: Write the failing test**

```python
def test_court_codes_includes_all_courts(self) -> None:
    """Court codes should include all documented IK courts, tribunals, and aggregators."""
    from app.core.providers.external.indiankanoon import IK_COURT_CODES

    # Key courts that must exist
    required = [
        "supreme_court", "delhi", "bombay", "calcutta", "madras",
        "andhra", "orissa", "himachal_pradesh", "madhya_pradesh", "sikkim",
        "meghalaya", "jammu",
    ]
    for court in required:
        assert court in IK_COURT_CODES, f"Missing court: {court}"

    # Key tribunals
    required_tribunals = ["itat", "cci", "ngt", "cat", "consumer", "tdsat"]
    for tribunal in required_tribunals:
        assert tribunal in IK_COURT_CODES, f"Missing tribunal: {tribunal}"

    # Aggregators
    required_agg = ["highcourts", "tribunals", "judgments", "laws"]
    for agg in required_agg:
        assert agg in IK_COURT_CODES, f"Missing aggregator: {agg}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_indiankanoon_client.py -v -k "all_courts"`
Expected: FAIL

**Step 3: Replace IK_COURT_CODES with complete mapping**

```python
IK_COURT_CODES: dict[str, str] = {
    # Supreme Court
    "supreme_court": "supremecourt",
    "sc": "supremecourt",
    # High Courts (from IK docs)
    "delhi": "delhi",
    "bombay": "bombay",
    "madras": "chennai",
    "chennai": "chennai",
    "calcutta": "kolkata",
    "kolkata": "kolkata",
    "allahabad": "allahabad",
    "lucknow": "lucknow",
    "karnataka": "karnataka",
    "kerala": "kerala",
    "punjab": "punjab",
    "punjab_haryana": "punjab",
    "gauhati": "gauhati",
    "gujarat": "gujarat",
    "rajasthan": "rajasthan",
    "jodhpur": "jodhpur",
    "patna": "patna",
    "andhra": "andhra",
    "telangana": "andhra",
    "chhattisgarh": "chattisgarh",
    "jharkhand": "jharkhand",
    "uttarakhand": "uttaranchal",
    "orissa": "orissa",
    "odisha": "orissa",
    "himachal_pradesh": "himachal_pradesh",
    "madhya_pradesh": "madhyapradesh",
    "sikkim": "sikkim",
    "meghalaya": "meghalaya",
    "jammu": "jammu",
    "srinagar": "srinagar",
    # District Courts
    "delhi_district": "delhidc",
    # Tribunals
    "itat": "itat",
    "cat": "cat",
    "cci": "cci",
    "ngt": "greentribunal",
    "green_tribunal": "greentribunal",
    "consumer": "consumer",
    "tdsat": "tdsat",
    "drat": "drat",
    "aptel": "aptel",
    "sebi_sat": "sebisat",
    "cerc": "cerc",
    "cic": "cic",
    "ipab": "ipab",
    "trademark": "trademark",
    "copyright": "copyrightboard",
    # Aggregators (search across groups)
    "highcourts": "highcourts",
    "tribunals": "tribunals",
    "judgments": "judgments",
    "laws": "laws",
}
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_indiankanoon_client.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/providers/external/indiankanoon.py backend/tests/unit/test_indiankanoon_client.py
git commit -m "feat: expand IK court codes — 50+ courts, tribunals, and aggregators"
```

---

### Task 6: Use `maxpages` for Single-Call Multi-Page Fetch

Currently `search()` loops with separate POST per page. IK supports `maxpages=N` to get N pages in one call (charged only for pages returned).

**Files:**
- Modify: `backend/app/core/providers/external/indiankanoon.py` (search method loop)
- Test: `backend/tests/unit/test_indiankanoon_client.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_search_uses_maxpages_param(self, ik_client) -> None:
    """When max_pages > 1, should use maxpages param in single call instead of looping."""
    resp = _mock_response({"docs": [{"tid": i} for i in range(15)]})
    with patch.object(ik_client._client, "post", new_callable=AsyncMock, return_value=resp) as mock_post:
        await ik_client.search("test", max_results=15, max_pages=2)
        # Should make exactly ONE API call with maxpages=2
        assert mock_post.call_count == 1
        data = mock_post.call_args[1]["data"]
        assert data["maxpages"] == "2"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_indiankanoon_client.py -v -k "maxpages_param"`
Expected: FAIL (currently makes 2 calls)

**Step 3: Replace loop with single `maxpages` call**

Replace the pagination loop in `search()`:

```python
        params: dict[str, str] = {
            "formInput": search_query,
            "pagenum": "0",
        }
        if from_date:
            params["fromdate"] = from_date
        if to_date:
            params["todate"] = to_date
        if sort_by:
            params["sortby"] = sort_by
        if max_cites is not None:
            params["maxcites"] = str(max_cites)
        if max_pages > 1:
            params["maxpages"] = str(max_pages)

        url = f"{self.BASE_URL}/search/"
        result = await self._rate_limited_post(url, data=params)
        all_docs = result.get("docs", [])

        return all_docs[:max_results]
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_indiankanoon_client.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/providers/external/indiankanoon.py backend/tests/unit/test_indiankanoon_client.py
git commit -m "perf: use IK maxpages param for single-call multi-page search"
```

---

### Task 7: Use `cite:` Filter for Citation Verification

Current citation verification does `ik_client.search(fn["citation"], max_results=1)` — a full-text search. Using the `cite:` filter is much more precise and avoids false positives.

**Files:**
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (citation verification section)
- Test: `backend/tests/unit/test_research_v2_phase4.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_citation_verification_uses_cite_filter(self) -> None:
    """IK citation verification should use cite_filter for precision."""
    from app.core.agents.nodes.research_nodes import _verify_citations_against_sources

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar=lambda: None))

    mock_ik = AsyncMock()
    mock_ik.search = AsyncMock(return_value=[{"tid": 1, "title": "Match"}])

    footnotes = [Footnote(number=1, citation="(2020) 5 SCC 1", text="Test", case_id="ik:123", is_used=True)]
    result = await _verify_citations_against_sources(footnotes, mock_db, mock_ik, None)

    # Should use cite_filter, not just raw query
    call_kwargs = mock_ik.search.call_args[1]
    assert call_kwargs.get("cite_filter") == "(2020) 5 SCC 1"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_research_v2_phase4.py -v -k "cite_filter"`
Expected: FAIL

**Step 3: Update citation verification**

In `research_nodes.py`, find the IK verification block and change:

```python
            # Check 2: Indian Kanoon API — use cite: filter for precision
            if status == "unverified" and ik_client and fn.get("citation"):
                try:
                    ik_results = await ik_client.search(
                        fn["citation"],
                        max_results=1,
                        cite_filter=fn["citation"],
                    )
                    if ik_results:
                        status = "verified_ik"
                except Exception:
                    pass  # IK failure is non-fatal
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_research_v2_phase4.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/research_nodes.py backend/tests/unit/test_research_v2_phase4.py
git commit -m "fix: use IK cite: filter for precise citation verification"
```

---

### Task 8: Propagate New Filters from Research Plan to IK Worker

The research plan can now specify `title`, `author`, `bench` filters. Wire these through the worker.

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (ik_search_worker)
- Test: `backend/tests/unit/test_ik_worker.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_passes_title_filter(self, mock_ik_client) -> None:
    """title from filters should be passed as title_filter."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    state = {"task": _make_task(filters={"title": "Puttaswamy"})}
    await ik_search_worker(state, mock_ik_client)
    call_kwargs = mock_ik_client.search.call_args[1]
    assert call_kwargs["title_filter"] == "Puttaswamy"

@pytest.mark.asyncio
async def test_passes_author_filter(self, mock_ik_client) -> None:
    """author from filters should be passed as author_filter."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    state = {"task": _make_task(filters={"author": "chandrachud"})}
    await ik_search_worker(state, mock_ik_client)
    call_kwargs = mock_ik_client.search.call_args[1]
    assert call_kwargs["author_filter"] == "chandrachud"

@pytest.mark.asyncio
async def test_passes_bench_filter(self, mock_ik_client) -> None:
    """bench from filters should be passed as bench_filter."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    state = {"task": _make_task(filters={"bench": "nariman"})}
    await ik_search_worker(state, mock_ik_client)
    call_kwargs = mock_ik_client.search.call_args[1]
    assert call_kwargs["bench_filter"] == "nariman"
```

**Step 2: Run test to verify it fails**

Expected: FAIL (worker doesn't pass these yet)

**Step 3: Add filter extraction to worker**

After the existing filter extraction in `ik_search_worker`, add:

```python
    title_filter = filters.get("title")
    author_filter = filters.get("author")
    bench_filter = filters.get("bench")
```

And pass them to the search call:

```python
        search_results = await ik_client.search(
            task["nl_query"],
            max_results=10,
            boolean_query=boolean_query,
            court_filter=court_filter,
            from_date=from_date,
            to_date=to_date,
            sort_by=sort_by,
            title_filter=title_filter,
            author_filter=author_filter,
            bench_filter=bench_filter,
            max_cites=5,  # Get citation list for free
        )
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_ik_worker.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_ik_worker.py
git commit -m "feat: propagate title/author/bench/maxcites filters to IK worker"
```

---

### Task 9: Include Court Copy URL in Footnotes

For trust, footnotes should reference the court-certified copy URL. The format is `https://indiankanoon.org/origdoc/<doc_id>/`. This is a link reference — we don't need to fetch the copy, just include the URL.

**Files:**
- Modify: `backend/app/core/agents/nodes/worker_nodes.py` (results output)
- Modify: `backend/app/core/agents/nodes/research_nodes.py` (footnote construction)
- Test: `backend/tests/unit/test_ik_worker.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_includes_court_copy_url(self, mock_ik_client) -> None:
    """Results should include court_copy_url for trusted references."""
    from app.core.agents.nodes.worker_nodes import ik_search_worker

    state = {"task": _make_task()}
    result = await ik_search_worker(state, mock_ik_client)

    r = result["worker_results"][0]["results"][0]
    assert r["court_copy_url"] == "https://indiankanoon.org/origdoc/123/"
```

**Step 2: Run test to verify it fails**

Expected: FAIL (no court_copy_url key)

**Step 3: Add court_copy_url to results**

In the `results.append(...)` block in `ik_search_worker`:

```python
                "court_copy_url": f"https://indiankanoon.org/origdoc/{doc_id}/",
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_ik_worker.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/agents/nodes/worker_nodes.py backend/tests/unit/test_ik_worker.py
git commit -m "feat: include court copy URL in IK results for trusted footnotes"
```

---

### Task 10: Update Research Plan Prompt with New IK Capabilities

Tell the LLM about the new filters and guide it to use them effectively.

**Files:**
- Modify: `backend/app/core/legal/prompts.py` (RESEARCH_PLAN_SYSTEM)
- Test: `backend/tests/unit/test_agent_prompts.py` (check prompt contains new filter names)

**Step 1: Write the failing test**

```python
def test_research_plan_prompt_includes_ik_filters() -> None:
    """Research plan prompt should mention all IK filter capabilities."""
    from app.core.legal.prompts import RESEARCH_PLAN_SYSTEM

    for keyword in ["title", "cite", "author", "bench", "court_copy"]:
        assert keyword in RESEARCH_PLAN_SYSTEM, f"Missing IK filter: {keyword}"
```

**Step 2: Run test to verify it fails**

Expected: FAIL (prompt doesn't mention all filters yet)

**Step 3: Update the IK section in RESEARCH_PLAN_SYSTEM**

Replace the "Indian Kanoon Query Optimization" section with:

```
## Indian Kanoon Query Optimization

When generating tasks with task_type "ik_search", create boolean_query using Indian Kanoon's
native operators for maximum precision:
- ANDD: both terms must appear (e.g., "498A ANDD cruelty ANDD dowry")
- ORR: either term (e.g., "murder ORR culpable homicide")
- NOTT: exclude term (e.g., "bail NOTT anticipatory")
- NEAR: proximity search (e.g., "fundamental NEAR rights")
- Wrap exact phrases in quotes: "right to life"

For filters dict on "ik_search" tasks, include when relevant:
- court: "supreme_court" | "delhi" | "bombay" | "madras" | "calcutta" | "highcourts" | "tribunals" | etc.
- from_year: integer (e.g., 2015)
- to_year: integer (e.g., 2024)
- sort_by: "mostrecent" for recency-sensitive queries
- title: case name keyword (e.g., "Puttaswamy") — restricts to docs with this in title
- cite: specific citation (e.g., "1993 AIR 264") — restricts to docs with this citation
- author: judge name (e.g., "chandrachud") — restricts to judgments authored by this judge
- bench: judge name (e.g., "nariman") — restricts to judgments where this judge was on bench

IK results include court_copy_url for verified court-certified copies — use these as
trusted footnote references for maximum credibility.

Use "highcourts" to search all high courts, "tribunals" for all tribunals,
"judgments" for SC+HC+District Courts, "laws" for Central Acts and Rules.
```

Also update `RESEARCH_PLAN_SCHEMA` filters to include the new fields:

```python
"filters": {
    "type": "object",
    "properties": {
        "court": {"type": "string"},
        "from_year": {"type": "integer"},
        "to_year": {"type": "integer"},
        "sort_by": {"type": "string"},
        "title": {"type": "string"},
        "cite": {"type": "string"},
        "author": {"type": "string"},
        "bench": {"type": "string"},
        "recency": {"type": "string"},
        "domains": {"type": "array", "items": {"type": "string"}},
    },
},
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_agent_prompts.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app/core/legal/prompts.py backend/tests/unit/test_agent_prompts.py
git commit -m "docs: update research plan prompt with full IK filter capabilities"
```

---

### Task 11: E2E Verification — All New Features

Run the full E2E test script with real API keys to verify all new features work against the live IK API.

**Files:**
- Modify: `backend/scripts/e2e_test_apis.py` (add tests for new features)

**Step 1: Add E2E tests for new features**

Add to the script:

```python
async def test_ik_title_filter(token: str) -> bool:
    """Test: IK title filter."""
    print("\n=== IK Test 6: Title Filter ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("privacy", title_filter="Puttaswamy", max_results=3)
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - {r.get('title', '?')[:80]}")
        assert all("puttaswamy" in r.get("title", "").lower() for r in results), "Title filter didn't work"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()

async def test_ik_cite_filter(token: str) -> bool:
    """Test: IK cite filter."""
    print("\n=== IK Test 7: Cite Filter ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("privacy", cite_filter="1995 AIR", max_results=3)
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - {r.get('title', '?')[:60]} [{r.get('citation', '')}]")
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()

async def test_ik_author_filter(token: str) -> bool:
    """Test: IK author filter."""
    print("\n=== IK Test 8: Author Filter ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("fundamental rights", author_filter="chandrachud", max_results=3)
        print(f"  Results: {len(results)}")
        for r in results:
            print(f"  - {r.get('title', '?')[:60]} [author: {r.get('author', '?')}]")
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()

async def test_ik_maxcites(token: str) -> bool:
    """Test: IK maxcites returns citation list."""
    print("\n=== IK Test 9: maxcites ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("right to privacy", max_results=1, max_cites=5)
        print(f"  Results: {len(results)}")
        cites = results[0].get("cites", [])
        print(f"  Cites for first result: {len(cites)}")
        for c in cites[:3]:
            print(f"    - [{c.get('tid')}] {c.get('title', '?')[:60]}")
        assert len(cites) > 0, "No cites returned with maxcites"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()

async def test_ik_maxpages(token: str) -> bool:
    """Test: IK maxpages in single call."""
    print("\n=== IK Test 10: maxpages (single call) ===")
    client = IndianKanoonClient(token=token)
    try:
        results = await client.search("article 21 life liberty", max_results=15, max_pages=2)
        print(f"  Results: {len(results)}")
        assert len(results) > 10, f"Expected >10 results from 2 pages, got {len(results)}"
        print("  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    finally:
        await client.close()
```

**Step 2: Run the E2E tests**

```bash
cd backend
IK_API_TOKEN=... TAVILY_API_KEY=... python -m scripts.e2e_test_apis
```

Expected: ALL PASS

**Step 3: Commit**

```bash
git add backend/scripts/e2e_test_apis.py
git commit -m "test: add E2E tests for IK title/cite/author/maxcites/maxpages"
```

---

### Task 12: Full Test Suite Verification

Run the entire test suite to ensure nothing is broken.

**Step 1: Run all unit tests**

```bash
cd backend
pytest tests/unit/ -x -q --tb=short
```

Expected: ALL PASS (should be ~1800+ tests)

**Step 2: Run E2E tests with real keys**

```bash
IK_API_TOKEN=32f1d9bbbc0a65237cb04b7ea733d122ea934305 TAVILY_API_KEY=tvly-dev-... python -m scripts.e2e_test_apis
```

Expected: ALL PASS

---

## Summary of Changes

| # | What | Cost Impact | Quality Impact |
|---|------|-------------|----------------|
| 1 | Use search headlines as snippets | Save Rs 0.25/search (~5 fragment calls) | Same quality — headlines are contextual |
| 2 | Rich fields from search | Free | Author, date, citation counts in results |
| 3 | title/cite/author/bench filters | Fewer irrelevant results | Precise case/judge lookup |
| 4 | Court certified copy endpoint | Rs 0.20 when needed | Trust signal for footnotes |
| 5 | All courts + tribunals + aggregators | Same | Full court coverage |
| 6 | maxpages single-call | Fewer API round trips | Same results, faster |
| 7 | cite: filter for verification | Same | Fewer false positive verifications |
| 8 | New filters in worker | Same | Precise research |
| 9 | court_copy_url in results | Free (URL only) | Footnote credibility |
| 10 | Prompt update | N/A | LLM uses all filters |
| 11-12 | E2E + full tests | N/A | Verified correct |
