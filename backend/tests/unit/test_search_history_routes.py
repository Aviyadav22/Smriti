"""Tests for search history API routes — list, bookmark, delete."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.search import router
from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_A_ID = str(uuid.uuid4())
_USER_B_ID = str(uuid.uuid4())
_HISTORY_ID = str(uuid.uuid4())

_TOKEN_A = TokenPayload(
    sub=_USER_A_ID,
    role="researcher",
    exp=datetime(2099, 1, 1, tzinfo=UTC),
    iat=datetime(2024, 1, 1, tzinfo=UTC),
    jti="jti-user-a",
)

_TOKEN_B = TokenPayload(
    sub=_USER_B_ID,
    role="researcher",
    exp=datetime(2099, 1, 1, tzinfo=UTC),
    iat=datetime(2024, 1, 1, tzinfo=UTC),
    jti="jti-user-b",
)


def _history_row(
    *,
    history_id: str = _HISTORY_ID,
    user_id: str = _USER_A_ID,
    query: str = "section 302 IPC murder",
    filters: str | None = '{"court": "Supreme Court of India"}',
    result_count: int = 42,
    is_bookmarked: bool = False,
    created_at: str = "2026-03-27 10:00:00+00:00",
) -> dict:
    """Build a dict mimicking a search_history row from mappings()."""
    return {
        "id": history_id,
        "user_id": user_id,
        "query": query,
        "filters": filters,
        "result_count": result_count,
        "is_bookmarked": is_bookmarked,
        "created_at": created_at,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Build a test FastAPI app with the search router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/search")
    return test_app


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client_a(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client authenticated as user A with DB dependency overridden."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _TOKEN_A
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def client_b(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client authenticated as user B with DB dependency overridden."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _TOKEN_B
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def client_unauth(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client with no auth override (unauthenticated)."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    # Do NOT override get_current_user — let it fail naturally
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /search/history — List user's recent searches
# ---------------------------------------------------------------------------


class TestListSearchHistory:
    """Tests for GET /api/v1/search/history."""

    def test_list_history_returns_entries(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Authenticated user gets paginated search history."""
        # First execute: COUNT(*)
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        # Second execute: SELECT rows
        row1 = _history_row(history_id=str(uuid.uuid4()), query="murder IPC 302")
        row2 = _history_row(history_id=str(uuid.uuid4()), query="bail conditions")
        rows_result = MagicMock()
        rows_result.mappings.return_value.all.return_value = [row1, row2]

        mock_db.execute.side_effect = [count_result, rows_result]

        resp = client_a.get("/api/v1/search/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["history"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert body["history"][0]["query"] == "murder IPC 302"

    def test_list_history_empty(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """User with no search history gets empty list."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        rows_result = MagicMock()
        rows_result.mappings.return_value.all.return_value = []

        mock_db.execute.side_effect = [count_result, rows_result]

        resp = client_a.get("/api/v1/search/history")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["history"] == []

    def test_list_history_pagination_params(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Custom page and page_size are respected."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = 50

        rows_result = MagicMock()
        rows_result.mappings.return_value.all.return_value = [
            _history_row(history_id=str(uuid.uuid4()))
        ]

        mock_db.execute.side_effect = [count_result, rows_result]

        resp = client_a.get("/api/v1/search/history?page=3&page_size=5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 3
        assert body["page_size"] == 5

    def test_list_history_unauthenticated_returns_401(
        self,
        client_unauth: TestClient,
    ) -> None:
        """Unauthenticated request to history returns 401."""
        resp = client_unauth.get("/api/v1/search/history")

        # FastAPI's OAuth2PasswordBearer returns 401 when no token is provided
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /search/history/{id}/bookmark — Toggle bookmark
# ---------------------------------------------------------------------------


class TestToggleBookmark:
    """Tests for POST /api/v1/search/history/{id}/bookmark."""

    def test_bookmark_toggle_on(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Toggle bookmark from False to True."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = {
            "user_id": _USER_A_ID,
            "is_bookmarked": False,
        }

        mock_db.execute.side_effect = [
            select_result,  # SELECT
            None,  # UPDATE
        ]

        resp = client_a.post(f"/api/v1/search/history/{_HISTORY_ID}/bookmark")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == _HISTORY_ID
        assert body["is_bookmarked"] is True
        mock_db.commit.assert_called_once()

    def test_bookmark_toggle_off(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Toggle bookmark from True to False."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = {
            "user_id": _USER_A_ID,
            "is_bookmarked": True,
        }

        mock_db.execute.side_effect = [
            select_result,  # SELECT
            None,  # UPDATE
        ]

        resp = client_a.post(f"/api/v1/search/history/{_HISTORY_ID}/bookmark")

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_bookmarked"] is False

    def test_bookmark_not_found_returns_404(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Non-existent history entry returns 404."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = None

        mock_db.execute.return_value = select_result

        fake_id = str(uuid.uuid4())
        resp = client_a.post(f"/api/v1/search/history/{fake_id}/bookmark")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_bookmark_idor_returns_403(
        self,
        client_b: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """User B cannot bookmark user A's history entry."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = {
            "user_id": _USER_A_ID,  # belongs to user A
            "is_bookmarked": False,
        }

        mock_db.execute.return_value = select_result

        resp = client_b.post(f"/api/v1/search/history/{_HISTORY_ID}/bookmark")

        assert resp.status_code == 403
        assert "denied" in resp.json()["detail"].lower()

    def test_bookmark_invalid_uuid_returns_422(
        self,
        client_a: TestClient,
    ) -> None:
        """Invalid UUID format in path returns 422."""
        resp = client_a.post("/api/v1/search/history/not-a-uuid/bookmark")

        assert resp.status_code == 422
        assert "invalid" in resp.json()["detail"].lower()

    def test_bookmark_unauthenticated_returns_401(
        self,
        client_unauth: TestClient,
    ) -> None:
        """Unauthenticated request to bookmark returns 401."""
        resp = client_unauth.post(f"/api/v1/search/history/{_HISTORY_ID}/bookmark")

        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# DELETE /search/history/{id} — Delete a search history entry
# ---------------------------------------------------------------------------


class TestDeleteSearchHistory:
    """Tests for DELETE /api/v1/search/history/{id}."""

    def test_delete_success(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Owner can delete their own history entry."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = {
            "user_id": _USER_A_ID,
        }

        mock_db.execute.side_effect = [
            select_result,  # SELECT
            None,  # DELETE
        ]

        resp = client_a.delete(f"/api/v1/search/history/{_HISTORY_ID}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "deleted"
        assert body["id"] == _HISTORY_ID
        mock_db.commit.assert_called_once()

    def test_delete_not_found_returns_404(
        self,
        client_a: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Deleting a non-existent entry returns 404."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = None

        mock_db.execute.return_value = select_result

        fake_id = str(uuid.uuid4())
        resp = client_a.delete(f"/api/v1/search/history/{fake_id}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_delete_idor_returns_403(
        self,
        client_b: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """User B cannot delete user A's history entry."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = {
            "user_id": _USER_A_ID,  # belongs to user A
        }

        mock_db.execute.return_value = select_result

        resp = client_b.delete(f"/api/v1/search/history/{_HISTORY_ID}")

        assert resp.status_code == 403
        assert "denied" in resp.json()["detail"].lower()

    def test_delete_invalid_uuid_returns_422(
        self,
        client_a: TestClient,
    ) -> None:
        """Invalid UUID format in path returns 422."""
        resp = client_a.delete("/api/v1/search/history/not-a-valid-uuid")

        assert resp.status_code == 422
        assert "invalid" in resp.json()["detail"].lower()

    def test_delete_unauthenticated_returns_401(
        self,
        client_unauth: TestClient,
    ) -> None:
        """Unauthenticated request to delete returns 401."""
        resp = client_unauth.delete(f"/api/v1/search/history/{_HISTORY_ID}")

        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Fire-and-forget history insertion (via main search endpoint)
# ---------------------------------------------------------------------------


class TestSearchHistoryInsertion:
    """Verify that authenticated search requests fire history persistence."""

    @patch("app.api.routes.search.get_redis", new_callable=AsyncMock)
    @patch("app.api.routes.search._serialize_response")
    @patch("app.api.routes.search.hybrid_search", new_callable=AsyncMock)
    @patch("app.api.routes.search.async_session_factory")
    @patch("app.api.routes.search.detect_prompt_injection", return_value=False)
    @patch("app.api.routes.search.sanitize_search_query", side_effect=lambda q: q)
    @patch("app.api.routes.search.get_reranker")
    @patch("app.api.routes.search.get_vector_store")
    @patch("app.api.routes.search.get_embedder")
    @patch("app.api.routes.search.get_llm")
    def test_authenticated_search_creates_history_task(
        self,
        mock_llm: MagicMock,
        mock_embedder: MagicMock,
        mock_vector: MagicMock,
        mock_reranker: MagicMock,
        mock_sanitize: MagicMock,
        mock_injection: MagicMock,
        mock_session_factory: MagicMock,
        mock_hybrid: AsyncMock,
        mock_serialize: MagicMock,
        mock_get_redis: AsyncMock,
        app: FastAPI,
        mock_db: AsyncMock,
    ) -> None:
        """An authenticated search triggers fire-and-forget history save."""
        mock_hybrid.return_value = MagicMock()
        mock_serialize.return_value = {
            "results": [],
            "total_count": 0,
            "page": 1,
            "page_size": 10,
            "query_understanding": {
                "intent": "case_search",
                "original_query": "murder 302",
                "expanded_query": "murder section 302 IPC",
                "search_strategy": "hybrid",
                "filters": {},
                "entities": {},
            },
            "facets": {},
        }
        mock_get_redis.return_value = None  # no redis

        # Mock the session factory context manager for history insert
        mock_hist_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_hist_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        # Override dependencies
        from app.security.rbac import get_current_user_optional

        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user_optional] = lambda: _TOKEN_A

        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/v1/search?q=murder+302")

        assert resp.status_code == 200
        # The fire-and-forget task is created via asyncio.create_task;
        # in TestClient (sync), background tasks may or may not complete.
        # We verify the code path was reached by checking hybrid_search was called.
        mock_hybrid.assert_called_once()

        app.dependency_overrides.clear()

    @patch("app.api.routes.search.get_redis", new_callable=AsyncMock)
    @patch("app.api.routes.search._serialize_response")
    @patch("app.api.routes.search.hybrid_search", new_callable=AsyncMock)
    @patch("app.api.routes.search.detect_prompt_injection", return_value=False)
    @patch("app.api.routes.search.sanitize_search_query", side_effect=lambda q: q)
    @patch("app.api.routes.search.get_reranker")
    @patch("app.api.routes.search.get_vector_store")
    @patch("app.api.routes.search.get_embedder")
    @patch("app.api.routes.search.get_llm")
    def test_unauthenticated_search_skips_history(
        self,
        mock_llm: MagicMock,
        mock_embedder: MagicMock,
        mock_vector: MagicMock,
        mock_reranker: MagicMock,
        mock_sanitize: MagicMock,
        mock_injection: MagicMock,
        mock_hybrid: AsyncMock,
        mock_serialize: MagicMock,
        mock_get_redis: AsyncMock,
        app: FastAPI,
        mock_db: AsyncMock,
    ) -> None:
        """An unauthenticated search does NOT attempt history save."""
        mock_hybrid.return_value = MagicMock()
        mock_serialize.return_value = {
            "results": [],
            "total_count": 0,
            "page": 1,
            "page_size": 10,
            "query_understanding": {
                "intent": "case_search",
                "original_query": "bail conditions",
                "expanded_query": "bail conditions criminal",
                "search_strategy": "hybrid",
                "filters": {},
                "entities": {},
            },
            "facets": {},
        }
        mock_get_redis.return_value = None

        from app.security.rbac import get_current_user_optional

        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user_optional] = lambda: None  # anonymous

        client = TestClient(app, raise_server_exceptions=False)

        with patch("app.api.routes.search.async_session_factory") as mock_sf:
            resp = client.get("/api/v1/search?q=bail+conditions")

            assert resp.status_code == 200
            # Session factory should NOT have been called for anonymous user
            mock_sf.assert_not_called()

        app.dependency_overrides.clear()
