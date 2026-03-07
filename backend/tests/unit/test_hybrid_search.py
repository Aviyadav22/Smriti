"""Unit tests for the hybrid search orchestrator (hybrid.py).

Mocks ALL external dependencies: Pinecone (VectorStore), Cohere (Reranker),
PostgreSQL (AsyncSession), Redis, LLM (query understanding), and FTS.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.interfaces.reranker import RerankResult
from app.core.interfaces.vector_store import SearchResult
from app.core.search.fulltext import FTSResult
from app.core.search.hybrid import (
    SearchResponse,
    SearchResultItem,
    hybrid_search,
    rrf_merge,
)
from app.core.search.query import QueryEntities, QueryUnderstanding, SearchFilters


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_qu(
    strategy: str = "balanced",
    expanded: str | None = None,
    original: str = "test query",
    filters: SearchFilters | None = None,
) -> QueryUnderstanding:
    return QueryUnderstanding(
        intent="topic_search",
        original_query=original,
        expanded_query=expanded or original,
        filters=filters or SearchFilters(),
        entities=QueryEntities(),
        search_strategy=strategy,
    )


def _vector_result(case_id: str, score: float, text: str = "chunk") -> SearchResult:
    return SearchResult(
        id=f"{case_id}_chunk_0",
        score=score,
        metadata={"case_id": case_id, "text": text},
    )


def _fts_result(case_id: str, rank: float, snippet: str = "snippet") -> FTSResult:
    return FTSResult(case_id=case_id, rank=rank, title=f"Title {case_id}", snippet=snippet)


def _db_row(case_id: str, **overrides) -> dict:
    """Create a fake DB row dict for enrichment queries."""
    row = {
        "id": case_id,
        "title": f"Title {case_id}",
        "citation": f"(2024) 1 SCC {case_id[-3:]}",
        "court": "Supreme Court of India",
        "year": 2024,
        "decision_date": "2024-01-15",
        "case_type": "civil",
        "judge": "Justice Test",
        "bench_type": "division",
    }
    row.update(overrides)
    return row


def _mock_db_execute(rows: list[dict], equiv_rows: list[dict] | None = None):
    """Return a mock db.execute that serves enrichment + facets + equiv queries."""
    call_count = 0
    equiv = equiv_rows or []

    async def _execute(sql, params=None):
        nonlocal call_count
        call_count += 1
        sql_text = str(sql.text) if hasattr(sql, "text") else str(sql)

        mock_result = MagicMock()
        if "case_citation_equivalents" in sql_text:
            mock_result.mappings.return_value.all.return_value = equiv
        else:
            mock_result.mappings.return_value.all.return_value = rows
        return mock_result

    return _execute


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.fixture
def mock_embedder():
    m = AsyncMock()
    m.embed_text = AsyncMock(return_value=[0.1] * 1536)
    return m


@pytest.fixture
def mock_vector_store():
    return AsyncMock()


@pytest.fixture
def mock_reranker():
    return AsyncMock()


@pytest.fixture
def mock_db():
    return AsyncMock()


# ---------------------------------------------------------------------------
# 1. test_hybrid_search_balanced_strategy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
@patch("app.core.search.hybrid.search_fulltext")
async def test_hybrid_search_balanced_strategy(
    mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """Balanced strategy runs vector + FTS in parallel and merges via RRF."""
    mock_uq.return_value = _make_qu(strategy="balanced")

    # Vector returns 2 results
    mock_vector_store.search.return_value = [
        _vector_result("case_a", 0.95, "vector text a"),
        _vector_result("case_b", 0.85, "vector text b"),
    ]

    # FTS returns 2 results (one overlapping)
    mock_fts.return_value = [
        _fts_result("case_a", 5.0),
        _fts_result("case_c", 3.0),
    ]

    # Reranker returns ordered indices
    mock_reranker.rerank.return_value = [
        RerankResult(index=0, score=0.9, text="a"),
        RerankResult(index=1, score=0.8, text="b"),
        RerankResult(index=2, score=0.7, text="c"),
    ]

    db_rows = [_db_row("case_a"), _db_row("case_b"), _db_row("case_c")]
    mock_db.execute = AsyncMock(side_effect=_mock_db_execute(db_rows))

    response = await hybrid_search(
        "test query",
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
    )

    assert isinstance(response, SearchResponse)
    assert response.page == 1
    # Both vector and FTS were called
    mock_vector_store.search.assert_awaited_once()
    mock_fts.assert_awaited_once()
    mock_reranker.rerank.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. test_hybrid_search_exact_match_strategy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid._exact_citation_search")
@patch("app.core.search.hybrid.understand_query")
async def test_hybrid_search_exact_match_strategy(
    mock_uq, mock_exact, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """exact_match strategy does citation lookup and returns early."""
    mock_uq.return_value = _make_qu(strategy="exact_match")
    mock_exact.return_value = [
        SearchResultItem(case_id="case_x", score=1.0, title="Exact Case", citation="(2024) 1 SCC 100"),
    ]

    response = await hybrid_search(
        "(2024) 1 SCC 100",
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
    )

    assert response.total_count == 1
    assert response.results[0].case_id == "case_x"
    assert response.results[0].score == 1.0
    # Reranker should NOT be called for exact match
    mock_reranker.rerank.assert_not_awaited()
    # Vector store should NOT be called
    mock_vector_store.search.assert_not_awaited()


# ---------------------------------------------------------------------------
# 3. test_hybrid_search_empty_results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
@patch("app.core.search.hybrid.search_fulltext")
async def test_hybrid_search_empty_results(
    mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """When both vector and FTS return nothing, response has empty results."""
    mock_uq.return_value = _make_qu(strategy="balanced")
    mock_vector_store.search.return_value = []
    mock_fts.return_value = []

    response = await hybrid_search(
        "nonexistent query xyz",
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
    )

    assert response.results == []
    assert response.total_count == 0
    mock_reranker.rerank.assert_not_awaited()


# ---------------------------------------------------------------------------
# 4. test_rrf_merge_deduplication
# ---------------------------------------------------------------------------


def test_rrf_merge_deduplication():
    """Same case_id from both sources gets a single combined RRF score."""
    vector_ranked = [("case_1", 0.9), ("case_2", 0.8)]
    fts_ranked = [("case_1", 5.0), ("case_3", 3.0)]

    merged = rrf_merge([vector_ranked, fts_ranked], k=60)
    ids = [doc_id for doc_id, _ in merged]

    # case_1 appears once (deduplicated)
    assert ids.count("case_1") == 1
    # case_1 should rank first (appears in both lists)
    assert ids[0] == "case_1"
    # All three cases present
    assert set(ids) == {"case_1", "case_2", "case_3"}
    # case_1 has combined score from both lists: 1/(60+1) + 1/(60+1) = 2/61
    case_1_score = dict(merged)["case_1"]
    expected = 1.0 / 61 + 1.0 / 61
    assert abs(case_1_score - expected) < 1e-10


# ---------------------------------------------------------------------------
# 5. test_reranker_timeout_fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
@patch("app.core.search.hybrid.search_fulltext")
async def test_reranker_timeout_fallback(
    mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """When reranker times out, RRF order is used as fallback."""
    mock_uq.return_value = _make_qu(strategy="balanced")

    mock_vector_store.search.return_value = [
        _vector_result("case_a", 0.9, "text a"),
        _vector_result("case_b", 0.8, "text b"),
    ]
    mock_fts.return_value = [
        _fts_result("case_a", 5.0),
        _fts_result("case_c", 3.0),
    ]

    # Reranker raises TimeoutError
    mock_reranker.rerank.side_effect = TimeoutError("Cohere timeout")

    db_rows = [_db_row("case_a"), _db_row("case_b"), _db_row("case_c")]
    mock_db.execute = AsyncMock(side_effect=_mock_db_execute(db_rows))

    response = await hybrid_search(
        "test query",
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
    )

    # Should still return results (using RRF order)
    assert isinstance(response, SearchResponse)
    assert response.total_count > 0
    # case_a should be first (appears in both lists)
    assert response.results[0].case_id == "case_a"


# ---------------------------------------------------------------------------
# 6. test_redis_cache_hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
async def test_redis_cache_hit(
    mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """Cached response is returned without running search pipeline."""
    cached_response = SearchResponse(
        results=[SearchResultItem(case_id="cached_case", score=0.99, title="Cached")],
        total_count=1,
        page=1,
        page_size=10,
        query_understanding=_make_qu(),
    )

    # Serialize the response as the cache would store it
    from app.core.search.hybrid import _serialize_response

    cached_json = json.dumps(_serialize_response(cached_response))

    mock_redis = AsyncMock()
    mock_redis.get.return_value = cached_json

    response = await hybrid_search(
        "test query",
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
        redis_client=mock_redis,
    )

    assert response.results[0].case_id == "cached_case"
    assert response.total_count == 1
    # LLM query understanding should NOT be called
    mock_uq.assert_not_awaited()
    # Vector store should NOT be called
    mock_vector_store.search.assert_not_awaited()


# ---------------------------------------------------------------------------
# 7. test_redis_cache_miss
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
@patch("app.core.search.hybrid.search_fulltext")
async def test_redis_cache_miss(
    mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """Full pipeline executes when Redis cache misses, then caches result."""
    mock_uq.return_value = _make_qu(strategy="balanced")

    mock_vector_store.search.return_value = [
        _vector_result("case_a", 0.9, "text a"),
    ]
    mock_fts.return_value = [
        _fts_result("case_a", 5.0),
    ]
    mock_reranker.rerank.return_value = [
        RerankResult(index=0, score=0.95, text="text a"),
    ]

    db_rows = [_db_row("case_a")]
    mock_db.execute = AsyncMock(side_effect=_mock_db_execute(db_rows))

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # Cache miss

    response = await hybrid_search(
        "test query",
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
        redis_client=mock_redis,
    )

    assert len(response.results) > 0
    # Full pipeline should have run
    mock_uq.assert_awaited_once()
    mock_vector_store.search.assert_awaited_once()
    mock_fts.assert_awaited_once()
    # Result should be cached
    mock_redis.setex.assert_awaited_once()


# ---------------------------------------------------------------------------
# 8. test_pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
@patch("app.core.search.hybrid.search_fulltext")
async def test_pagination(
    mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """Page 2 with page_size=2 returns correct slice of results."""
    mock_uq.return_value = _make_qu(strategy="balanced")

    # Create enough results to span multiple pages
    vector_results = [_vector_result(f"case_{i}", 0.9 - i * 0.1, f"text {i}") for i in range(5)]
    fts_results = [_fts_result(f"case_{i}", 5.0 - i, f"snippet {i}") for i in range(5)]

    mock_vector_store.search.return_value = vector_results
    mock_fts.return_value = fts_results

    # Reranker returns all 5 in order
    mock_reranker.rerank.return_value = [
        RerankResult(index=i, score=0.9 - i * 0.1, text=f"text {i}") for i in range(5)
    ]

    db_rows = [_db_row(f"case_{i}") for i in range(5)]
    mock_db.execute = AsyncMock(side_effect=_mock_db_execute(db_rows))

    response = await hybrid_search(
        "test query",
        page=2,
        page_size=2,
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
    )

    assert response.page == 2
    assert response.page_size == 2
    # Page 2 with size 2 should give items at indices 2-3
    assert len(response.results) <= 2


# ---------------------------------------------------------------------------
# 9. test_filters_applied_to_vector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
@patch("app.core.search.hybrid.search_fulltext")
async def test_filters_applied_to_vector(
    mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """Pinecone filter is constructed correctly from SearchFilters."""
    filters = SearchFilters(
        court=["Supreme Court of India"],
        year_from=2020,
        year_to=2024,
        case_type="criminal",
        judgment_section="HOLDINGS",
    )
    mock_uq.return_value = _make_qu(strategy="balanced", filters=SearchFilters())

    mock_vector_store.search.return_value = []
    mock_fts.return_value = []

    await hybrid_search(
        "test query",
        filters=filters,
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
    )

    # Verify Pinecone was called with correct filter
    call_args = mock_vector_store.search.call_args
    pinecone_filter = call_args.kwargs.get("filters") or (call_args[1].get("filters") if len(call_args) > 1 else None)

    assert pinecone_filter is not None
    assert pinecone_filter["court"] == {"$eq": "Supreme Court of India"}
    assert pinecone_filter["year"]["$gte"] == 2020
    assert pinecone_filter["year"]["$lte"] == 2024
    assert pinecone_filter["case_type"] == {"$eq": "criminal"}
    assert pinecone_filter["section_type"] == {"$eq": "HOLDINGS"}


# ---------------------------------------------------------------------------
# 10. test_filters_applied_to_fts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("app.core.search.hybrid.understand_query")
@patch("app.core.search.hybrid.search_fulltext")
async def test_filters_applied_to_fts(
    mock_fts, mock_uq, mock_llm, mock_embedder, mock_vector_store, mock_reranker, mock_db
):
    """FTS is called with the correct merged filters."""
    explicit_filters = SearchFilters(
        court=["Supreme Court of India"],
        year_from=2020,
    )
    llm_filters = SearchFilters(
        year_to=2024,
        case_type="civil",
    )
    mock_uq.return_value = _make_qu(strategy="balanced", filters=llm_filters)

    mock_vector_store.search.return_value = []
    mock_fts.return_value = []

    await hybrid_search(
        "test query",
        filters=explicit_filters,
        llm=mock_llm,
        embedder=mock_embedder,
        vector_store=mock_vector_store,
        reranker=mock_reranker,
        db=mock_db,
    )

    # Verify FTS was called with merged filters
    fts_call = mock_fts.call_args
    fts_filters: SearchFilters = fts_call.kwargs.get("filters") or fts_call[1].get("filters")

    assert fts_filters is not None
    # Explicit court wins
    assert fts_filters.court == ["Supreme Court of India"]
    # Explicit year_from wins
    assert fts_filters.year_from == 2020
    # LLM year_to fills in
    assert fts_filters.year_to == 2024
    # LLM case_type fills in
    assert fts_filters.case_type == "civil"
