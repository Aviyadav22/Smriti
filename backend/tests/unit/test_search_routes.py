"""Tests for search API routes — hybrid search, suggestions, and facets."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.search import router
from app.core.search.hybrid import SearchResponse, SearchResultItem
from app.core.search.query import QueryEntities, QueryUnderstanding, SearchFilters
from app.db.postgres import get_db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_search_response(
    *,
    page: int = 1,
    page_size: int = 10,
    total_count: int = 1,
) -> SearchResponse:
    """Build a minimal SearchResponse for mocking."""
    return SearchResponse(
        results=[
            SearchResultItem(
                case_id="case-001",
                score=0.95,
                title="State v. Kumar",
                citation="(2023) 5 SCC 123",
                court="Supreme Court of India",
                year=2023,
                date="2023-05-15",
                case_type="Civil Appeal",
                judge="Justice A.B. Sharma",
                snippet="The court held that ...",
                bench_type="Division Bench",
                equivalent_citations=["AIR 2023 SC 456"],
            ),
        ],
        total_count=total_count,
        page=page,
        page_size=page_size,
        query_understanding=QueryUnderstanding(
            intent="case_law_search",
            original_query="land acquisition",
            expanded_query="land acquisition compensation section 26",
            filters=SearchFilters(),
            entities=QueryEntities(),
            search_strategy="hybrid",
        ),
        facets={},
    )


def _mock_db_session() -> AsyncMock:
    """Create a mock async DB session."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/search")
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Client with DB dependency overridden."""
    mock_db = _mock_db_session()

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    """Tests for GET /api/v1/search."""

    @patch("app.api.routes.search.get_redis", new_callable=AsyncMock)
    @patch("app.api.routes.search.get_reranker")
    @patch("app.api.routes.search.get_vector_store")
    @patch("app.api.routes.search.get_embedder")
    @patch("app.api.routes.search.get_llm")
    @patch("app.api.routes.search.hybrid_search", new_callable=AsyncMock)
    def test_search_returns_200_with_results(
        self,
        mock_hybrid_search: AsyncMock,
        mock_get_llm: MagicMock,
        mock_get_embedder: MagicMock,
        mock_get_vector_store: MagicMock,
        mock_get_reranker: MagicMock,
        mock_get_redis: AsyncMock,
        client: TestClient,
    ) -> None:
        """A valid query returns 200 with serialized search results."""
        mock_hybrid_search.return_value = _make_search_response()
        mock_get_redis.return_value = None  # no redis

        resp = client.get("/api/v1/search", params={"q": "land acquisition"})

        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body
        assert len(body["results"]) == 1
        assert body["results"][0]["case_id"] == "case-001"
        assert body["results"][0]["score"] == 0.95
        assert body["total_count"] == 1
        assert body["page"] == 1
        assert body["query_understanding"]["intent"] == "case_law_search"
        mock_hybrid_search.assert_called_once()

    def test_search_empty_query_returns_422(self, client: TestClient) -> None:
        """An empty query string triggers FastAPI validation error (422)."""
        resp = client.get("/api/v1/search", params={"q": ""})
        assert resp.status_code == 422

    def test_search_missing_query_returns_422(self, client: TestClient) -> None:
        """Missing q parameter triggers FastAPI validation error (422)."""
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422

    @patch("app.api.routes.search.get_redis", new_callable=AsyncMock)
    @patch("app.api.routes.search.get_reranker")
    @patch("app.api.routes.search.get_vector_store")
    @patch("app.api.routes.search.get_embedder")
    @patch("app.api.routes.search.get_llm")
    @patch("app.api.routes.search.hybrid_search", new_callable=AsyncMock)
    def test_search_with_filters(
        self,
        mock_hybrid_search: AsyncMock,
        mock_get_llm: MagicMock,
        mock_get_embedder: MagicMock,
        mock_get_vector_store: MagicMock,
        mock_get_reranker: MagicMock,
        mock_get_redis: AsyncMock,
        client: TestClient,
    ) -> None:
        """Court and year filters are forwarded to hybrid_search correctly."""
        mock_hybrid_search.return_value = _make_search_response()
        mock_get_redis.return_value = None

        resp = client.get(
            "/api/v1/search",
            params={
                "q": "fundamental rights",
                "court": "Supreme Court of India,Delhi High Court",
                "year_from": 2020,
                "year_to": 2024,
                "case_type": "Writ Petition",
            },
        )

        assert resp.status_code == 200
        call_kwargs = mock_hybrid_search.call_args
        filters: SearchFilters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters.court == ["Supreme Court of India", "Delhi High Court"]
        assert filters.year_from == 2020
        assert filters.year_to == 2024
        assert filters.case_type == "Writ Petition"

    @patch("app.api.routes.search.get_redis", new_callable=AsyncMock)
    @patch("app.api.routes.search.get_reranker")
    @patch("app.api.routes.search.get_vector_store")
    @patch("app.api.routes.search.get_embedder")
    @patch("app.api.routes.search.get_llm")
    @patch("app.api.routes.search.hybrid_search", new_callable=AsyncMock)
    def test_search_pagination_params(
        self,
        mock_hybrid_search: AsyncMock,
        mock_get_llm: MagicMock,
        mock_get_embedder: MagicMock,
        mock_get_vector_store: MagicMock,
        mock_get_reranker: MagicMock,
        mock_get_redis: AsyncMock,
        client: TestClient,
    ) -> None:
        """Page and page_size params are forwarded to hybrid_search."""
        mock_hybrid_search.return_value = _make_search_response(page=3, page_size=20)
        mock_get_redis.return_value = None

        resp = client.get(
            "/api/v1/search",
            params={"q": "section 498A", "page": 3, "page_size": 20},
        )

        assert resp.status_code == 200
        call_kwargs = mock_hybrid_search.call_args
        assert call_kwargs.kwargs.get("page") == 3 or call_kwargs[1].get("page") == 3
        assert call_kwargs.kwargs.get("page_size") == 20 or call_kwargs[1].get("page_size") == 20
        body = resp.json()
        assert body["page"] == 3
        assert body["page_size"] == 20


class TestSuggestEndpoint:
    """Tests for GET /api/v1/search/suggest."""

    @patch("app.api.routes.search.get_redis", new_callable=AsyncMock)
    def test_suggest_returns_suggestions(
        self,
        mock_get_redis: AsyncMock,
        app: FastAPI,
    ) -> None:
        """The suggest endpoint returns matching case suggestions."""
        mock_get_redis.return_value = None  # no redis cache

        import uuid

        case_id = uuid.uuid4()
        mock_row = {"id": case_id, "title": "State v. Kumar", "citation": "(2023) 5 SCC 123"}
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [mock_row]

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db

        suggest_client = TestClient(app, raise_server_exceptions=False)
        resp = suggest_client.get(
            "/api/v1/search/suggest",
            params={"q": "Kumar"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "suggestions" in body
        assert len(body["suggestions"]) == 1
        assert body["suggestions"][0]["title"] == "State v. Kumar"
        assert body["suggestions"][0]["case_id"] == str(case_id)
        app.dependency_overrides.clear()

    def test_suggest_short_query_returns_422(self, client: TestClient) -> None:
        """Query shorter than min_length=3 returns validation error."""
        resp = client.get("/api/v1/search/suggest", params={"q": "ab"})
        assert resp.status_code == 422


class TestFacetsEndpoint:
    """Tests for GET /api/v1/search/facets."""

    @patch("app.api.routes.search.get_redis", new_callable=AsyncMock)
    def test_facets_returns_facets(
        self,
        mock_get_redis: AsyncMock,
        client: TestClient,
    ) -> None:
        """The facets endpoint returns court, case_type, bench_type, and year ranges."""
        mock_get_redis.return_value = None

        # Mock DB session — single combined query returns all facets at once
        mock_db = AsyncMock()

        combined_row = {
            "courts": ["Supreme Court of India", "Delhi High Court"],
            "case_types": ["Civil Appeal", "Writ Petition"],
            "bench_types": ["Division Bench", "Full Bench"],
            "min_year": 1950,
            "max_year": 2024,
        }
        combined_result = MagicMock()
        combined_result.mappings.return_value.one_or_none.return_value = combined_row

        mock_db.execute.return_value = combined_result

        async def _override_db():
            yield mock_db

        client.app.dependency_overrides[get_db] = _override_db  # type: ignore[union-attr]

        resp = client.get("/api/v1/search/facets")

        assert resp.status_code == 200
        body = resp.json()
        assert body["courts"] == ["Supreme Court of India", "Delhi High Court"]
        assert body["case_types"] == ["Civil Appeal", "Writ Petition"]
        assert body["bench_types"] == ["Division Bench", "Full Bench"]
        assert body["years"]["min"] == 1950
        assert body["years"]["max"] == 2024


class TestRouteRegistration:
    """Verify search routes are correctly registered."""

    def test_search_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "" in paths or "/" in paths, f"Main search route not found in {paths}"
        assert "/suggest" in paths, f"/suggest not found in {paths}"
        assert "/facets" in paths, f"/facets not found in {paths}"

    def test_search_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path in ("", "/"):
                assert "GET" in route.methods  # type: ignore[attr-defined]

    def test_suggest_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/suggest":
                assert "GET" in route.methods  # type: ignore[attr-defined]

    def test_facets_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/facets":
                assert "GET" in route.methods  # type: ignore[attr-defined]
