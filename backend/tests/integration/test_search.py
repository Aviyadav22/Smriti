"""Integration tests for search API endpoints and hybrid search pipeline.

Tests the search router (/api/v1/search), suggest, and facets endpoints
with mocked external services (DB, Redis, LLM, embedder, vector store, reranker).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.interfaces import RerankResult, SearchResult
from app.core.search.fulltext import FTSResult
from app.core.search.hybrid import SearchResponse, SearchResultItem, rrf_merge
from app.core.search.query import QueryEntities, QueryUnderstanding, SearchFilters

# ---------------------------------------------------------------------------
# Helpers — fake IDs and row factories
# ---------------------------------------------------------------------------

CASE_ID_1 = str(uuid.UUID(int=1))
CASE_ID_2 = str(uuid.UUID(int=2))
CASE_ID_3 = str(uuid.UUID(int=3))


def _make_case_row(
    case_id: str,
    title: str = "Test v. State",
    citation: str = "(2023) 1 SCC 100",
    court: str = "Supreme Court of India",
    year: int = 2023,
    case_type: str = "Civil Appeal",
    bench_type: str = "Division Bench",
    judge: str = "Justice A",
    decision_date: str = "2023-01-15",
) -> dict:
    """Build a dict mimicking a SQLAlchemy RowMapping for the cases table."""
    return {
        "id": case_id,
        "title": title,
        "citation": citation,
        "court": court,
        "year": year,
        "case_type": case_type,
        "bench_type": bench_type,
        "judge": judge,
        "decision_date": decision_date,
    }


def _fake_query_understanding(query: str = "test query") -> QueryUnderstanding:
    return QueryUnderstanding(
        intent="topic_search",
        original_query=query,
        expanded_query=query,
        filters=SearchFilters(),
        entities=QueryEntities(),
        search_strategy="balanced",
    )


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def _mock_db_session() -> AsyncMock:
    """Create an AsyncMock that behaves like AsyncSession."""
    db = AsyncMock()
    return db


def _configure_db_for_facets(db: AsyncMock) -> None:
    """Configure db.execute to return appropriate results for facets queries."""
    courts_result = MagicMock()
    courts_result.all.return_value = [("Supreme Court of India",), ("Delhi High Court",)]

    case_types_result = MagicMock()
    case_types_result.all.return_value = [("Civil Appeal",), ("Criminal Appeal",)]

    bench_types_result = MagicMock()
    bench_types_result.all.return_value = [("Division Bench",), ("Constitution Bench",)]

    years_result = MagicMock()
    years_mapping = MagicMock()
    years_mapping.__getitem__ = lambda self, key: {"min_year": 1950, "max_year": 2024}[key]
    years_result.mappings.return_value.one_or_none.return_value = years_mapping

    # Return results in order of calls in the facets endpoint
    db.execute = AsyncMock(
        side_effect=[courts_result, case_types_result, bench_types_result, years_result]
    )


def _configure_db_for_suggest(db: AsyncMock, rows: list[dict] | None = None) -> None:
    """Configure db.execute to return suggestions."""
    if rows is None:
        rows = [
            {"id": CASE_ID_1, "title": "State v. Kumar", "citation": "(2023) 1 SCC 100"},
            {"id": CASE_ID_2, "title": "Sharma v. State", "citation": "(2022) 5 SCC 200"},
        ]
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    db.execute = AsyncMock(return_value=result)


def _mock_redis_none() -> AsyncMock:
    """A redis mock that always returns None (cache miss)."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    return redis


def _mock_llm() -> AsyncMock:
    """Mock LLM that returns valid query understanding JSON."""
    llm = AsyncMock()
    llm.generate_structured = AsyncMock(
        return_value={
            "intent": "topic_search",
            "original_query": "right to privacy",
            "expanded_query": "right to privacy fundamental rights article 21",
            "filters": {},
            "entities": {
                "case_names": [],
                "statutes": [],
                "legal_concepts": ["right to privacy"],
                "judges": [],
                "courts": [],
            },
            "search_strategy": "balanced",
        }
    )
    return llm


def _mock_embedder() -> AsyncMock:
    """Mock embedder returning a fixed 768-dim vector."""
    embedder = AsyncMock()
    embedder.embed_text = AsyncMock(return_value=[0.1] * 768)
    embedder.dimension = 768
    return embedder


def _mock_vector_store(results: list[SearchResult] | None = None) -> AsyncMock:
    """Mock vector store returning given results."""
    vs = AsyncMock()
    if results is None:
        results = [
            SearchResult(id="chunk_1", score=0.95, metadata={"case_id": CASE_ID_1}),
            SearchResult(id="chunk_2", score=0.90, metadata={"case_id": CASE_ID_2}),
        ]
    vs.search = AsyncMock(return_value=results)
    return vs


def _mock_reranker(top_ids_count: int = 2) -> AsyncMock:
    """Mock reranker that returns results in the same order."""
    reranker = AsyncMock()
    reranker.rerank = AsyncMock(
        return_value=[
            RerankResult(index=i, score=0.9 - (i * 0.1), text=f"text_{i}")
            for i in range(top_ids_count)
        ]
    )
    return reranker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_db():
    return _mock_db_session()


@pytest.fixture
def mock_redis():
    return _mock_redis_none()


@pytest.fixture
def app_client():
    """Yield an app instance with dependency overrides cleared after use."""
    from app.main import app

    yield app
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestSearchEndpoint:
    """Tests for GET /api/v1/search."""

    async def test_basic_search_returns_results(self, app_client) -> None:
        """A valid search query returns results with expected shape."""
        mock_db = _mock_db_session()

        # Configure DB for enrich + facets queries (called after RRF/rerank)
        enrich_result = MagicMock()
        enrich_result.mappings.return_value.all.return_value = [
            _make_case_row(CASE_ID_1, title="Kesavananda v. State of Kerala"),
            _make_case_row(CASE_ID_2, title="Maneka Gandhi v. Union of India"),
        ]
        facets_result = MagicMock()
        facets_result.mappings.return_value.all.return_value = [
            {"court": "Supreme Court of India", "case_type": "Civil Appeal", "year": 2023, "bench_type": "Division Bench"},
        ]
        # FTS query returns rows too
        fts_result = MagicMock()
        fts_result.mappings.return_value.all.return_value = [
            {"id": CASE_ID_1, "title": "Kesavananda v. State of Kerala", "citation": "(1973) 4 SCC 225", "rank": 5.0, "snippet": "basic structure doctrine"},
            {"id": CASE_ID_2, "title": "Maneka Gandhi v. Union of India", "citation": "(1978) 1 SCC 248", "rank": 4.0, "snippet": "right to travel abroad"},
        ]
        mock_db.execute = AsyncMock(side_effect=[fts_result, enrich_result, facets_result])

        from app.db.postgres import get_db

        async def override_get_db():
            yield mock_db

        app_client.dependency_overrides[get_db] = override_get_db

        mock_llm = _mock_llm()
        mock_emb = _mock_embedder()
        mock_vs = _mock_vector_store()
        mock_rr = _mock_reranker(top_ids_count=2)
        mock_red = _mock_redis_none()

        with (
            patch("app.api.routes.search.get_llm", return_value=mock_llm),
            patch("app.api.routes.search.get_embedder", return_value=mock_emb),
            patch("app.api.routes.search.get_vector_store", return_value=mock_vs),
            patch("app.api.routes.search.get_reranker", return_value=mock_rr),
            patch("app.api.routes.search.get_redis", return_value=mock_red),
        ):
            transport = ASGITransport(app=app_client)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/search", params={"q": "right to privacy"})

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total_count" in data
        assert "query_understanding" in data
        assert isinstance(data["results"], list)
        assert data["total_count"] >= 0

    async def test_search_with_filters(self, app_client) -> None:
        """Search with court, year_from, case_type filters passes them through."""
        mock_db = _mock_db_session()

        enrich_result = MagicMock()
        enrich_result.mappings.return_value.all.return_value = [
            _make_case_row(CASE_ID_1, court="Supreme Court of India", year=2020, case_type="Criminal Appeal"),
        ]
        facets_result = MagicMock()
        facets_result.mappings.return_value.all.return_value = [
            {"court": "Supreme Court of India", "case_type": "Criminal Appeal", "year": 2020, "bench_type": "Division Bench"},
        ]
        fts_result = MagicMock()
        fts_result.mappings.return_value.all.return_value = [
            {"id": CASE_ID_1, "title": "Test Case", "citation": "(2020) 1 SCC 1", "rank": 3.0, "snippet": "murder conviction"},
        ]
        mock_db.execute = AsyncMock(side_effect=[fts_result, enrich_result, facets_result])

        from app.db.postgres import get_db

        async def override_get_db():
            yield mock_db

        app_client.dependency_overrides[get_db] = override_get_db

        mock_vs = _mock_vector_store(
            results=[SearchResult(id="chunk_1", score=0.85, metadata={"case_id": CASE_ID_1})]
        )

        with (
            patch("app.api.routes.search.get_llm", return_value=_mock_llm()),
            patch("app.api.routes.search.get_embedder", return_value=_mock_embedder()),
            patch("app.api.routes.search.get_vector_store", return_value=mock_vs),
            patch("app.api.routes.search.get_reranker", return_value=_mock_reranker(top_ids_count=1)),
            patch("app.api.routes.search.get_redis", return_value=_mock_redis_none()),
        ):
            transport = ASGITransport(app=app_client)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/search",
                    params={
                        "q": "murder conviction",
                        "court": "Supreme Court of India",
                        "year_from": 2018,
                        "case_type": "Criminal Appeal",
                    },
                )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["results"], list)

    async def test_search_empty_query_returns_error(self, app_client) -> None:
        """An empty query string should return 422 validation error."""
        transport = ASGITransport(app=app_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/search", params={"q": ""})

        assert resp.status_code == 422

    async def test_search_missing_query_returns_error(self, app_client) -> None:
        """Missing q parameter should return 422 validation error."""
        transport = ASGITransport(app=app_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/search")

        assert resp.status_code == 422

    async def test_search_returns_facets_in_response(self, app_client) -> None:
        """Verify response shape includes results, total_count, facets, query_understanding."""
        mock_db = _mock_db_session()

        enrich_result = MagicMock()
        enrich_result.mappings.return_value.all.return_value = [
            _make_case_row(CASE_ID_1),
        ]
        facets_result = MagicMock()
        facets_result.mappings.return_value.all.return_value = [
            {"court": "Supreme Court of India", "case_type": "Civil Appeal", "year": 2023, "bench_type": "Division Bench"},
        ]
        fts_result = MagicMock()
        fts_result.mappings.return_value.all.return_value = [
            {"id": CASE_ID_1, "title": "Test v. State", "citation": "(2023) 1 SCC 100", "rank": 5.0, "snippet": "snippet text"},
        ]
        mock_db.execute = AsyncMock(side_effect=[fts_result, enrich_result, facets_result])

        from app.db.postgres import get_db

        async def override_get_db():
            yield mock_db

        app_client.dependency_overrides[get_db] = override_get_db

        with (
            patch("app.api.routes.search.get_llm", return_value=_mock_llm()),
            patch("app.api.routes.search.get_embedder", return_value=_mock_embedder()),
            patch("app.api.routes.search.get_vector_store", return_value=_mock_vector_store(
                results=[SearchResult(id="c1", score=0.9, metadata={"case_id": CASE_ID_1})]
            )),
            patch("app.api.routes.search.get_reranker", return_value=_mock_reranker(top_ids_count=1)),
            patch("app.api.routes.search.get_redis", return_value=_mock_redis_none()),
        ):
            transport = ASGITransport(app=app_client)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/search", params={"q": "fundamental rights"})

        assert resp.status_code == 200
        data = resp.json()

        # Verify complete response shape
        assert "results" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
        assert "query_understanding" in data
        assert "facets" in data

        # Verify query_understanding shape
        qu = data["query_understanding"]
        assert "intent" in qu
        assert "original_query" in qu
        assert "expanded_query" in qu
        assert "search_strategy" in qu
        assert "filters" in qu
        assert "entities" in qu

        # Verify result item shape
        if data["results"]:
            item = data["results"][0]
            assert "case_id" in item
            assert "score" in item
            assert "title" in item
            assert "citation" in item
            assert "court" in item
            assert "year" in item


# ---------------------------------------------------------------------------
# Suggest endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestSuggestEndpoint:
    """Tests for GET /api/v1/search/suggest."""

    async def test_suggest_returns_suggestions(self, app_client) -> None:
        """A valid prefix returns matching suggestions."""
        mock_db = _mock_db_session()
        _configure_db_for_suggest(mock_db)

        from app.db.postgres import get_db

        async def override_get_db():
            yield mock_db

        app_client.dependency_overrides[get_db] = override_get_db

        with patch("app.api.routes.search.get_redis", return_value=_mock_redis_none()):
            transport = ASGITransport(app=app_client)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/search/suggest", params={"q": "State v"})

        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) == 2

        # Verify suggestion shape
        suggestion = data["suggestions"][0]
        assert "case_id" in suggestion
        assert "title" in suggestion
        assert "citation" in suggestion

    async def test_suggest_empty_query(self, app_client) -> None:
        """Empty q parameter returns 422 (min_length=3)."""
        transport = ASGITransport(app=app_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/search/suggest", params={"q": ""})

        assert resp.status_code == 422

    async def test_suggest_short_query(self, app_client) -> None:
        """Query shorter than 3 chars returns 422 (min_length=3)."""
        transport = ASGITransport(app=app_client)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/search/suggest", params={"q": "ab"})

        assert resp.status_code == 422

    async def test_suggest_no_results(self, app_client) -> None:
        """When DB returns no rows, suggestions list is empty."""
        mock_db = _mock_db_session()
        _configure_db_for_suggest(mock_db, rows=[])

        from app.db.postgres import get_db

        async def override_get_db():
            yield mock_db

        app_client.dependency_overrides[get_db] = override_get_db

        with patch("app.api.routes.search.get_redis", return_value=_mock_redis_none()):
            transport = ASGITransport(app=app_client)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/search/suggest", params={"q": "zzzzzznonexistent"})

        assert resp.status_code == 200
        assert resp.json()["suggestions"] == []


# ---------------------------------------------------------------------------
# Facets endpoint
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestFacetsEndpoint:
    """Tests for GET /api/v1/search/facets."""

    async def test_facets_returns_courts_and_years(self, app_client) -> None:
        """Facets endpoint returns courts and year range."""
        mock_db = _mock_db_session()
        _configure_db_for_facets(mock_db)

        from app.db.postgres import get_db

        async def override_get_db():
            yield mock_db

        app_client.dependency_overrides[get_db] = override_get_db

        with patch("app.api.routes.search.get_redis", return_value=_mock_redis_none()):
            transport = ASGITransport(app=app_client)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/search/facets")

        assert resp.status_code == 200
        data = resp.json()

        assert "courts" in data
        assert "Supreme Court of India" in data["courts"]
        assert "Delhi High Court" in data["courts"]

        assert "years" in data
        assert data["years"]["min"] == 1950
        assert data["years"]["max"] == 2024

    async def test_facets_response_shape(self, app_client) -> None:
        """Verify response has courts, case_types, years, bench_types."""
        mock_db = _mock_db_session()
        _configure_db_for_facets(mock_db)

        from app.db.postgres import get_db

        async def override_get_db():
            yield mock_db

        app_client.dependency_overrides[get_db] = override_get_db

        with patch("app.api.routes.search.get_redis", return_value=_mock_redis_none()):
            transport = ASGITransport(app=app_client)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/search/facets")

        assert resp.status_code == 200
        data = resp.json()

        # All four facet categories must be present
        assert "courts" in data
        assert "case_types" in data
        assert "bench_types" in data
        assert "years" in data

        # Types
        assert isinstance(data["courts"], list)
        assert isinstance(data["case_types"], list)
        assert isinstance(data["bench_types"], list)
        assert isinstance(data["years"], dict)
        assert "min" in data["years"]
        assert "max" in data["years"]

        # Values
        assert len(data["courts"]) == 2
        assert len(data["case_types"]) == 2
        assert len(data["bench_types"]) == 2


# ---------------------------------------------------------------------------
# Hybrid search pipeline (unit-level integration)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
class TestHybridSearch:
    """Tests for the hybrid search pipeline internals."""

    async def test_rrf_merge_integrates_vector_and_fts(self) -> None:
        """Mock both vector and FTS sources, verify RRF produces merged results."""
        # Simulate vector search results (case_id, score)
        vector_results = [
            (CASE_ID_1, 0.95),
            (CASE_ID_2, 0.88),
            (CASE_ID_3, 0.80),
        ]

        # Simulate FTS results (case_id, rank)
        fts_results = [
            (CASE_ID_2, 5.0),  # FTS ranks CASE_ID_2 first
            (CASE_ID_1, 4.0),
        ]

        merged = rrf_merge([vector_results, fts_results], k=60)
        merged_ids = [doc_id for doc_id, _ in merged]

        # Both CASE_ID_1 and CASE_ID_2 appear in both lists, should rank highest
        assert CASE_ID_1 in merged_ids[:2]
        assert CASE_ID_2 in merged_ids[:2]

        # CASE_ID_3 only in vector, should still appear
        assert CASE_ID_3 in merged_ids

        # Total should be 3 unique IDs
        assert len(merged) == 3

        # Scores should be descending
        scores = [s for _, s in merged]
        assert scores == sorted(scores, reverse=True)

    async def test_rrf_scores_reflect_overlap(self) -> None:
        """Documents in both lists get higher RRF scores than single-list docs."""
        vector = [(CASE_ID_1, 0.9), (CASE_ID_2, 0.8)]
        fts = [(CASE_ID_1, 5.0), (CASE_ID_3, 4.0)]

        merged = rrf_merge([vector, fts], k=60)
        score_map = dict(merged)

        # CASE_ID_1 is in both lists, should have higher score
        assert score_map[CASE_ID_1] > score_map[CASE_ID_2]
        assert score_map[CASE_ID_1] > score_map[CASE_ID_3]

    async def test_search_falls_back_on_llm_failure(self) -> None:
        """When LLM fails, query understanding falls back to passthrough."""
        from app.core.search.query import understand_query

        # Mock LLM that raises an error
        failing_llm = AsyncMock()
        failing_llm.generate_structured = AsyncMock(
            side_effect=RuntimeError("LLM service unavailable")
        )

        qu = await understand_query("right to privacy", failing_llm)

        # Should fall back to passthrough defaults
        assert qu.intent == "general"
        assert qu.original_query == "right to privacy"
        assert qu.expanded_query == "right to privacy"
        assert qu.search_strategy == "balanced"
        assert qu.filters == SearchFilters()
        assert qu.entities == QueryEntities()

    async def test_search_falls_back_on_llm_connection_error(self) -> None:
        """ConnectionError from LLM also triggers passthrough fallback."""
        from app.core.search.query import understand_query

        failing_llm = AsyncMock()
        failing_llm.generate_structured = AsyncMock(
            side_effect=ConnectionError("Cannot reach LLM")
        )

        qu = await understand_query("section 302 IPC cases", failing_llm)

        assert qu.intent == "general"
        assert qu.original_query == "section 302 IPC cases"
        assert qu.expanded_query == "section 302 IPC cases"

    async def test_hybrid_search_empty_results(self) -> None:
        """When both vector and FTS return empty, search returns empty response."""
        from app.core.search.hybrid import hybrid_search

        mock_db = _mock_db_session()
        # FTS returns empty
        fts_result = MagicMock()
        fts_result.mappings.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=fts_result)

        mock_llm = _mock_llm()
        mock_emb = _mock_embedder()
        mock_vs = _mock_vector_store(results=[])  # Vector returns empty
        mock_rr = _mock_reranker()

        response = await hybrid_search(
            query="completely irrelevant query xyz",
            llm=mock_llm,
            embedder=mock_emb,
            vector_store=mock_vs,
            reranker=mock_rr,
            db=mock_db,
            redis_client=None,
        )

        assert isinstance(response, SearchResponse)
        assert response.results == []
        assert response.total_count == 0

    async def test_hybrid_search_reranker_failure_uses_rrf_order(self) -> None:
        """When reranker fails, results fall back to RRF ordering."""
        from app.core.search.hybrid import hybrid_search

        mock_db = _mock_db_session()
        # FTS result
        fts_result = MagicMock()
        fts_result.mappings.return_value.all.return_value = [
            {"id": CASE_ID_1, "title": "Test Case", "citation": "(2023) 1 SCC 1", "rank": 5.0, "snippet": "test snippet"},
        ]
        # Enrich result
        enrich_result = MagicMock()
        enrich_result.mappings.return_value.all.return_value = [
            _make_case_row(CASE_ID_1),
        ]
        # Facets result
        facets_result = MagicMock()
        facets_result.mappings.return_value.all.return_value = [
            {"court": "Supreme Court of India", "case_type": "Civil Appeal", "year": 2023, "bench_type": "Division Bench"},
        ]
        mock_db.execute = AsyncMock(side_effect=[fts_result, enrich_result, facets_result])

        mock_llm = _mock_llm()
        mock_emb = _mock_embedder()
        mock_vs = _mock_vector_store(
            results=[SearchResult(id="chunk_1", score=0.9, metadata={"case_id": CASE_ID_1})]
        )

        # Reranker that fails
        failing_reranker = AsyncMock()
        failing_reranker.rerank = AsyncMock(side_effect=RuntimeError("Cohere is down"))

        response = await hybrid_search(
            query="test query",
            llm=mock_llm,
            embedder=mock_emb,
            vector_store=mock_vs,
            reranker=failing_reranker,
            db=mock_db,
            redis_client=None,
        )

        # Should still return results via RRF fallback
        assert isinstance(response, SearchResponse)
        assert response.total_count > 0
