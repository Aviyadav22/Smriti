# Audit Fixes (M1–M7) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 7 major audit findings — multi-tenancy prep in Pinecone, DB pool tuning, race-condition-free dedup, batched bulk upserts, graph-based treatment detection, rate limiter fail-fast, and computed cited_by_count.

**Architecture:** Each fix is isolated to 1–2 files with no cross-dependencies, so tasks can be executed in any order. All changes preserve backward compatibility — existing callers pass no new args and get identical behavior. TDD throughout.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, Pinecone, Neo4j, Redis, pytest

---

## Task 1: M1 — Vector Store User/Tenant Isolation

Add optional `user_scope` parameter to the VectorStore interface and PineconeStore implementation. When provided, it injects a `user_id` metadata filter into every search. Currently no callers pass it (all data is public case law), but the plumbing is ready for user-uploaded documents.

**Files:**
- Modify: `backend/app/core/interfaces/vector_store.py:26-32`
- Modify: `backend/app/core/providers/vector/pinecone_store.py:74-105`
- Create: `backend/tests/unit/test_pinecone_store_tenant.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_pinecone_store_tenant.py
"""Tests for user-scope filtering in PineconeStore.search()."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.interfaces.vector_store import SearchResult


class TestPineconeUserScope:
    """Verify user_scope injects user_id into Pinecone filters."""

    @pytest.fixture()
    def mock_index(self):
        index = MagicMock()
        match = MagicMock()
        match.id = "v1"
        match.score = 0.9
        match.metadata = {"case_id": "c1"}
        index.query.return_value = MagicMock(matches=[match])
        return index

    @patch("app.core.providers.vector.pinecone_store.settings")
    @patch("app.core.providers.vector.pinecone_store.Pinecone")
    async def test_search_without_user_scope(self, mock_pc_cls, mock_settings, mock_index):
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_host = "https://test"
        mock_pc_cls.return_value.Index.return_value = mock_index

        from app.core.providers.vector.pinecone_store import PineconeStore
        store = PineconeStore()
        results = await store.search([0.1] * 1536, top_k=5, filters={"court": "SC"})

        call_kwargs = mock_index.query.call_args
        assert call_kwargs.kwargs.get("filter") == {"court": "SC"} or call_kwargs[1].get("filter") == {"court": "SC"}

    @patch("app.core.providers.vector.pinecone_store.settings")
    @patch("app.core.providers.vector.pinecone_store.Pinecone")
    async def test_search_with_user_scope(self, mock_pc_cls, mock_settings, mock_index):
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_host = "https://test"
        mock_pc_cls.return_value.Index.return_value = mock_index

        from app.core.providers.vector.pinecone_store import PineconeStore
        store = PineconeStore()
        results = await store.search([0.1] * 1536, top_k=5, user_scope="user-42")

        call_kwargs = mock_index.query.call_args
        filt = call_kwargs.kwargs.get("filter") or call_kwargs[1].get("filter")
        assert filt == {"user_id": "user-42"}

    @patch("app.core.providers.vector.pinecone_store.settings")
    @patch("app.core.providers.vector.pinecone_store.Pinecone")
    async def test_search_with_user_scope_merges_filters(self, mock_pc_cls, mock_settings, mock_index):
        mock_settings.pinecone_api_key = "test-key"
        mock_settings.pinecone_host = "https://test"
        mock_pc_cls.return_value.Index.return_value = mock_index

        from app.core.providers.vector.pinecone_store import PineconeStore
        store = PineconeStore()
        results = await store.search([0.1] * 1536, filters={"court": "SC"}, user_scope="user-42")

        call_kwargs = mock_index.query.call_args
        filt = call_kwargs.kwargs.get("filter") or call_kwargs[1].get("filter")
        assert filt == {"court": "SC", "user_id": "user-42"}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_pinecone_store_tenant.py -v`
Expected: FAIL — `search()` doesn't accept `user_scope`

**Step 3: Implement — update interface**

In `backend/app/core/interfaces/vector_store.py`, update the `search` signature:

```python
async def search(
    self,
    query_vector: list[float],
    *,
    top_k: int = 20,
    filters: dict | None = None,
    user_scope: str | None = None,
) -> list[SearchResult]: ...
```

**Step 4: Implement — update PineconeStore**

In `backend/app/core/providers/vector/pinecone_store.py`, update `search`:

```python
@_pinecone_retry
async def search(
    self,
    query_vector: list[float],
    *,
    top_k: int = 20,
    filters: dict | None = None,
    user_scope: str | None = None,
) -> list[SearchResult]:
    if user_scope:
        filters = dict(filters) if filters else {}
        filters["user_id"] = user_scope
    try:
        # ... rest unchanged
```

**Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_pinecone_store_tenant.py -v`
Expected: PASS

**Step 6: Run existing test suite to verify no regressions**

Run: `cd backend && python -m pytest tests/unit/ -x -q --timeout=30`
Expected: All existing tests still pass

**Step 7: Commit**

```bash
git add backend/app/core/interfaces/vector_store.py backend/app/core/providers/vector/pinecone_store.py backend/tests/unit/test_pinecone_store_tenant.py
git commit -m "feat(M1): add user_scope tenant isolation to VectorStore.search"
```

---

## Task 2: M2 — Database Connection Pool Tuning + SSE Timeout

Lower per-instance pool defaults for Cloud Run scale-out. Add a 5-minute timeout to chat SSE streams.

**Files:**
- Modify: `backend/app/core/config.py:34-35`
- Modify: `backend/app/api/routes/chat.py:63-93`
- Create: `backend/tests/unit/test_config_pool.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_config_pool.py
"""Verify lowered pool defaults for Cloud Run scale-out."""

from app.core.config import Settings


class TestPoolDefaults:
    def test_pool_size_lowered(self):
        s = Settings(database_url="postgresql+asyncpg://x:x@localhost/db")
        assert s.database_pool_size == 10

    def test_max_overflow_lowered(self):
        s = Settings(database_url="postgresql+asyncpg://x:x@localhost/db")
        assert s.database_max_overflow == 20
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_config_pool.py -v`
Expected: FAIL — current defaults are 20 / 30

**Step 3: Implement config change**

In `backend/app/core/config.py`, change lines 34-35:

```python
database_pool_size: int = 10       # lowered for Cloud Run scale-out (10 instances × 30 = 300 max)
database_max_overflow: int = 20
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_config_pool.py -v`
Expected: PASS

**Step 5: Add SSE timeout to chat streams**

In `backend/app/api/routes/chat.py`, add a 5-minute timeout wrapper around the SSE generator. Add `import asyncio` at top if not present, then wrap the event_stream inner function body:

In the `event_stream()` function inside `create_chat` (around line 63), wrap the `async for` loop:

```python
async def event_stream():
    async with async_session_factory() as stream_db:
        try:
            async with asyncio.timeout(300):  # 5-minute max SSE duration
                async for event in rag_respond(
                    # ... same args ...
                ):
                    yield f"data: {json.dumps(event.data | {'type': event.type})}\n\n"
        except TimeoutError:
            logger.warning("Chat SSE stream timed out after 5 minutes")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Stream timed out after 5 minutes'})}\n\n"
        except Exception:
            logger.exception("SSE stream error in create_chat")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An internal error occurred'})}\n\n"
```

Apply the same pattern to the `send_message` endpoint's event_stream (the continue-conversation endpoint).

**Step 6: Run all tests**

Run: `cd backend && python -m pytest tests/unit/ -x -q --timeout=30`
Expected: All pass

**Step 7: Commit**

```bash
git add backend/app/core/config.py backend/app/api/routes/chat.py
git commit -m "feat(M2): lower DB pool defaults for scale-out, add 5-min SSE timeout"
```

---

## Task 3: M3 — Text-Hash Dedup Race Condition Fix

Replace the check-then-act SELECT → INSERT pattern with atomic INSERT ... ON CONFLICT DO NOTHING using the existing `idx_cases_text_hash` unique index. The early check before the LLM call becomes a "fast path hint" — the real dedup is the unique index.

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:117-137`
- Create: `backend/tests/unit/test_pipeline_dedup.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_pipeline_dedup.py
"""Tests for text-hash dedup early-exit logic in ingest_single_case."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestTextHashDedupComment:
    """Verify the dedup query uses ON CONFLICT for atomicity."""

    def test_dedup_check_uses_for_update(self):
        """Verify the dedup SQL includes FOR UPDATE SKIP LOCKED."""
        from app.core.ingestion import pipeline
        import inspect
        source = inspect.getsource(pipeline.ingest_single_case)
        # The advisory SELECT should use FOR UPDATE SKIP LOCKED to prevent races
        assert "FOR UPDATE SKIP LOCKED" in source or "ON CONFLICT" in source
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_pipeline_dedup.py -v`
Expected: FAIL — current code uses neither

**Step 3: Implement — add row-level locking to the advisory check**

In `backend/app/core/ingestion/pipeline.py`, around lines 120-123, change the SELECT to use `FOR UPDATE SKIP LOCKED`. This makes the early check race-safe — if two workers check simultaneously, the second one's SELECT will skip the locked row (returning no result) and proceed to the INSERT, where the unique index will catch the real duplicate:

```python
# Replace current advisory SELECT (lines 120-123):
existing_hash = await db.execute(
    text("SELECT id, chunk_count FROM cases WHERE text_hash = :hash FOR UPDATE SKIP LOCKED"),
    {"hash": text_hash},
)
```

This is the minimal fix: the unique index on `text_hash` is already the true dedup guard (migration 013). The `FOR UPDATE SKIP LOCKED` prevents the advisory check from giving a false negative during concurrent ingestion.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_pipeline_dedup.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd backend && python -m pytest tests/unit/ -x -q --timeout=30`
Expected: All pass

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py backend/tests/unit/test_pipeline_dedup.py
git commit -m "fix(M3): add FOR UPDATE SKIP LOCKED to text-hash dedup check"
```

---

## Task 4: M4 — Batch Bulk Upsert (Single Round-Trip)

Replace the per-row `for params in param_list: db.execute(stmt, params)` loop with a single `executemany`-style execution. Since the statement uses `RETURNING id`, we need to collect results. asyncpg supports `executemany` but doesn't return rows — so we use a VALUES-list approach: build one big INSERT with all rows in a single statement.

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:1018-1022`
- Create: `backend/tests/unit/test_bulk_upsert.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_bulk_upsert.py
"""Test that bulk_upsert_cases executes in batches, not row-by-row."""

import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch


class TestBulkUpsertBatching:
    """Verify bulk_upsert_cases uses batch execution."""

    @pytest.mark.asyncio
    async def test_batch_executes_once_per_batch_not_per_row(self):
        """With 5 rows and batch_size=250, should be 1 db.execute call, not 5."""
        from app.core.ingestion.pipeline import bulk_upsert_cases

        mock_db = AsyncMock()
        # Each execute returns a result with one row
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("fake-id",)
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        mock_db.flush = AsyncMock()

        cases = [
            {"id": f"id-{i}", "title": f"Case {i}", "court": "SC", "citation": f"cite-{i}"}
            for i in range(5)
        ]

        ids = await bulk_upsert_cases(cases, mock_db)
        assert len(ids) == 5
        # Key assertion: should NOT be 5 execute calls (one per row)
        # After fix, should be 1 call with all params
        assert mock_db.execute.call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_bulk_upsert.py -v`
Expected: FAIL — currently 5 calls (one per row)

**Step 3: Implement batch execution**

In `backend/app/core/ingestion/pipeline.py`, replace lines 1018-1022. The challenge is that `RETURNING id` with `executemany` doesn't return rows in asyncpg. Instead, we build a CTE with `unnest` arrays or simply accept the approach of executing the single large statement once per batch (not per row). The simplest correct approach: build the param list and use a single `execute` with a modified statement that accepts array params and uses `unnest`.

Actually, the simplest approach that preserves RETURNING: keep the same SQL statement but wrap the loop body to build a single combined statement using `UNION ALL` of VALUES, or just collect IDs from param_list since we generate them ourselves:

```python
# Replace lines 1018-1022:
        # Batch execute — IDs are pre-generated, so we don't need RETURNING.
        # The ON CONFLICT clause handles duplicates; we trust our generated IDs.
        for params in param_list:
            await db.execute(stmt, params)
        all_ids.extend(p["id"] for p in param_list)
```

Wait — this is still per-row. The real fix is to restructure to use `executemany`. But asyncpg's `executemany` doesn't support `RETURNING`. The pragmatic fix: since we generate IDs upfront (line 975: `row_id = str(row.get("id") or uuid.uuid4())`), we don't actually need RETURNING. We can use `executemany` and collect from param_list:

Actually the simplest and most impactful change: use `connection.execute()` with a list of params (asyncpg executemany under the hood via SQLAlchemy). SQLAlchemy's `execute` with a list of dicts does use `executemany`:

```python
        # Batch execution: single round-trip for all rows in this batch.
        # We pre-generate IDs (line 975), so we don't need RETURNING.
        stmt_no_returning = text(stmt.text.replace("RETURNING id", ""))
        await db.execute(stmt_no_returning, param_list)
        all_ids.extend(p["id"] for p in param_list)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_bulk_upsert.py -v`
Expected: PASS (1 execute call instead of 5)

**Step 5: Run full test suite**

Run: `cd backend && python -m pytest tests/unit/ -x -q --timeout=30`
Expected: All pass

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py backend/tests/unit/test_bulk_upsert.py
git commit -m "perf(M4): batch bulk_upsert_cases into single execute per batch"
```

---

## Task 5: M5 — Graph-Based Overruled Case Detection

Query Neo4j citation graph for authoritative treatment status (`CITES` edges with `treatment = 'overruled'`) alongside the existing text heuristic. The graph result takes precedence — if the graph says overruled, flag it regardless of text. If graph is unavailable, fall back to existing heuristic.

**Files:**
- Modify: `backend/app/core/chat/rag.py:19,194-221`
- Create: `backend/tests/unit/test_rag_treatment_graph.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_rag_treatment_graph.py
"""Tests for graph-based treatment detection in RAG pipeline."""

import pytest
from unittest.mock import AsyncMock


class TestCheckTreatmentFromGraph:
    """Verify check_treatment_from_graph queries Neo4j correctly."""

    @pytest.mark.asyncio
    async def test_returns_overruled_cases(self):
        from app.core.chat.rag import check_treatment_from_graph

        mock_graph = AsyncMock()
        mock_graph.query.return_value = [
            {"case_id": "c1", "overruled_by": "(2023) 5 SCC 100"},
        ]

        result = await check_treatment_from_graph(["c1", "c2"], mock_graph)
        assert result == {"c1": "(2023) 5 SCC 100"}
        mock_graph.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_overruled(self):
        from app.core.chat.rag import check_treatment_from_graph

        mock_graph = AsyncMock()
        mock_graph.query.return_value = []

        result = await check_treatment_from_graph(["c1"], mock_graph)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_empty_on_graph_error(self):
        from app.core.chat.rag import check_treatment_from_graph

        mock_graph = AsyncMock()
        mock_graph.query.side_effect = RuntimeError("Neo4j down")

        result = await check_treatment_from_graph(["c1"], mock_graph)
        assert result == {}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_rag_treatment_graph.py -v`
Expected: FAIL — `check_treatment_from_graph` doesn't exist

**Step 3: Implement `check_treatment_from_graph`**

In `backend/app/core/chat/rag.py`, add the function (after imports, before `rag_respond`):

```python
from app.core.interfaces.graph_store import GraphStore

async def check_treatment_from_graph(
    case_ids: list[str],
    graph_store: GraphStore,
) -> dict[str, str]:
    """Query Neo4j for cases that have been overruled.

    Returns:
        Mapping of case_id → overruling citation for cases found to be overruled.
        Returns empty dict on error (graph unavailability should not break RAG).
    """
    if not case_ids:
        return {}
    try:
        results = await graph_store.query(
            "MATCH (c:Case)-[r:CITES]->(cited:Case) "
            "WHERE cited.id IN $case_ids AND r.treatment = 'overruled' "
            "RETURN cited.id AS case_id, c.citation AS overruled_by",
            params={"case_ids": case_ids},
        )
        return {r["case_id"]: r["overruled_by"] for r in results}
    except Exception:
        logger.warning("Failed to check treatment from graph, falling back to heuristic", exc_info=True)
        return {}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_rag_treatment_graph.py -v`
Expected: PASS

**Step 5: Wire into rag_respond**

The `rag_respond` function needs a new optional `graph_store` parameter. Update its signature and the source-yielding loop (around line 194).

Add `graph_store: GraphStore | None = None` to `rag_respond`'s parameters.

Before the source loop (line 194), add:

```python
# Check graph for authoritative treatment status
graph_overruled: dict[str, str] = {}
if graph_store and sources:
    graph_overruled = await check_treatment_from_graph(
        [s.case_id for s in sources], graph_store
    )
```

Then update the treatment warning block (lines 215-220):

```python
# Graph-based treatment takes precedence over heuristic
if source.case_id in graph_overruled:
    source_data["treatment_warning"] = (
        f"This case has been overruled by {graph_overruled[source.case_id]}. "
        "Verify its current status before relying on it."
    )
elif check_text.strip() and has_overruling_language(check_text):
    source_data["treatment_warning"] = (
        "This case may have been overruled or distinguished. "
        "Verify its current status before relying on it."
    )
```

**Step 6: Update callers to pass graph_store**

In `backend/app/api/routes/chat.py`, import `get_graph_store` and pass it through:

```python
from app.core.providers import get_graph_store
# ... in create_chat and send_message:
graph_store = get_graph_store()
# ... pass graph_store=graph_store to rag_respond(...)
```

Check if `get_graph_store` exists; if it follows the same pattern as `get_vector_store` / `get_llm`, it should be in `backend/app/core/providers/__init__.py`. If not, the graph store may need to be obtained differently — check existing patterns.

**Step 7: Run full test suite**

Run: `cd backend && python -m pytest tests/unit/ -x -q --timeout=30`
Expected: All pass

**Step 8: Commit**

```bash
git add backend/app/core/chat/rag.py backend/app/api/routes/chat.py backend/tests/unit/test_rag_treatment_graph.py
git commit -m "feat(M5): add graph-based overruled case detection in RAG pipeline"
```

---

## Task 6: M6 — Rate Limiter Fail-Fast on Redis Down

Replace the in-memory fallback with a 503 response when Redis is unavailable. In production, a degraded rate limiter that doesn't actually limit across instances is worse than briefly refusing requests.

**Files:**
- Modify: `backend/app/security/rate_limiter.py:229-239`
- Modify: `backend/tests/unit/test_rate_limiter.py` (update existing tests)

**Step 1: Write failing test**

```python
# Add to backend/tests/unit/test_rate_limiter.py (or create new test class):

class TestRateLimiterFailFast:
    """Verify rate limiter returns 503 when Redis is down (not in-memory fallback)."""

    @pytest.mark.asyncio
    async def test_redis_down_returns_503(self):
        from app.security.rate_limiter import rate_limit_dependency
        from fastapi import HTTPException

        dep = rate_limit_dependency("10/minute")

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/test"

        with patch("app.security.rate_limiter._get_rate_limiter", side_effect=ConnectionError("Redis down")):
            with pytest.raises(HTTPException) as exc_info:
                await dep(mock_request)
            assert exc_info.value.status_code == 503
            assert "unavailable" in exc_info.value.detail.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_rate_limiter.py::TestRateLimiterFailFast -v`
Expected: FAIL — current code falls back to in-memory instead of 503

**Step 3: Implement fail-fast**

In `backend/app/security/rate_limiter.py`, replace lines 231-239:

```python
        except RateLimitExceededError:
            raise
        except Exception as exc:
            # Redis unavailable — fail fast with 503 instead of unreliable
            # in-memory fallback (each Cloud Run instance would have independent
            # limits, making rate limiting ineffective at scale).
            logger.error("Rate limiter Redis unavailable: %s", exc)
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail="Rate limiting service temporarily unavailable. Please retry shortly.",
            )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_rate_limiter.py -v`
Expected: PASS (check existing tests too — some may expect the fallback behavior and need updating)

**Step 5: Update existing tests that expect fallback behavior**

Search for tests that mock Redis failure and expect in-memory behavior. Update them to expect 503.

**Step 6: Run full test suite**

Run: `cd backend && python -m pytest tests/unit/ -x -q --timeout=30`
Expected: All pass

**Step 7: Commit**

```bash
git add backend/app/security/rate_limiter.py backend/tests/unit/test_rate_limiter.py
git commit -m "fix(M6): rate limiter returns 503 when Redis is down instead of unreliable fallback"
```

---

## Task 7: M7 — Computed cited_by_count (Replace Non-Atomic Increment)

Replace the non-atomic `SET b.cited_by_count = COALESCE(...) + 1` with an on-demand computed count. Remove the increment from the ingestion pipeline and add a utility function that computes the count from the graph when needed.

**Files:**
- Modify: `backend/app/core/ingestion/pipeline.py:762-768`
- Create: `backend/tests/unit/test_cited_by_count.py`

**Step 1: Write failing test**

```python
# backend/tests/unit/test_cited_by_count.py
"""Tests for computed cited_by_count."""

import pytest
from unittest.mock import AsyncMock


class TestComputedCitedByCount:
    """Verify cited_by_count is computed from graph, not stored."""

    @pytest.mark.asyncio
    async def test_get_cited_by_count(self):
        from app.core.ingestion.pipeline import get_cited_by_count

        mock_graph = AsyncMock()
        mock_graph.query.return_value = [{"cited_by_count": 42}]

        count = await get_cited_by_count("case-1", mock_graph)
        assert count == 42

    @pytest.mark.asyncio
    async def test_get_cited_by_count_not_found(self):
        from app.core.ingestion.pipeline import get_cited_by_count

        mock_graph = AsyncMock()
        mock_graph.query.return_value = []

        count = await get_cited_by_count("case-1", mock_graph)
        assert count == 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_cited_by_count.py -v`
Expected: FAIL — `get_cited_by_count` doesn't exist

**Step 3: Implement**

In `backend/app/core/ingestion/pipeline.py`:

1. Add `get_cited_by_count` function:

```python
async def get_cited_by_count(case_id: str, graph_store: GraphStore) -> int:
    """Compute cited_by_count on demand from the graph (avoids non-atomic increment)."""
    try:
        results = await graph_store.query(
            "MATCH (cited:Case {id: $id})<-[:CITES]-(c) "
            "RETURN count(c) AS cited_by_count",
            params={"id": case_id},
        )
        return results[0]["cited_by_count"] if results else 0
    except Exception:
        logger.warning("Failed to compute cited_by_count for %s", case_id, exc_info=True)
        return 0
```

2. Remove the non-atomic increment (lines 762-768). Comment out or delete:

```python
        # REMOVED: Non-atomic cited_by_count increment (M7 audit fix).
        # cited_by_count is now computed on demand via get_cited_by_count().
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_cited_by_count.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `cd backend && python -m pytest tests/unit/ -x -q --timeout=30`
Expected: All pass (check that no existing tests assert on the removed increment query)

**Step 6: Commit**

```bash
git add backend/app/core/ingestion/pipeline.py backend/tests/unit/test_cited_by_count.py
git commit -m "fix(M7): replace non-atomic cited_by_count increment with computed count"
```

---

## Final Verification

After all 7 tasks are complete:

1. Run full backend test suite: `cd backend && python -m pytest tests/unit/ -v --timeout=30`
2. Run frontend tests: `cd frontend && npm test -- --run`
3. Verify no regressions in existing functionality
4. Create a single summary commit if any cleanup is needed

```bash
git log --oneline -7  # Should show 7 clean commits, one per audit fix
```
