"""Tests for user preferences API routes — get, update, refresh."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.preferences import router
from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid.uuid4())

_TOKEN = TokenPayload(
    sub=_USER_ID,
    role="researcher",
    exp=datetime(2099, 1, 1, tzinfo=UTC),
    iat=datetime(2024, 1, 1, tzinfo=UTC),
    jti="jti-prefs-test",
)


def _prefs_row(preferences: dict | None = None) -> dict:
    """Build a dict mimicking a users row with preferences."""
    return {"preferences": preferences if preferences is not None else {}}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Build a test FastAPI app with the preferences router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    return test_app


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client with DB and auth dependencies overridden."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _TOKEN
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client WITHOUT auth override — tests auth requirement."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    # Do NOT override get_current_user — it should fail auth
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /users/me/preferences
# ---------------------------------------------------------------------------


class TestGetPreferences:
    """Tests for GET /api/users/me/preferences."""

    def test_returns_empty_for_new_user(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """A new user with no preferences gets an empty object."""
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _prefs_row({})
        mock_db.execute.return_value = select_result

        resp = client.get("/api/users/me/preferences")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_returns_existing_preferences(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Existing preferences are returned as-is."""
        prefs = {"preferred_courts": ["Supreme Court of India"], "common_case_types": ["Criminal Appeal"]}
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _prefs_row(prefs)
        mock_db.execute.return_value = select_result

        resp = client.get("/api/users/me/preferences")
        assert resp.status_code == 200
        assert resp.json() == prefs

    def test_requires_auth(
        self, unauth_client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Endpoint returns 401/403 without authentication."""
        resp = unauth_client.get("/api/users/me/preferences")
        # Without the auth override, get_current_user will raise — should be 4xx
        assert resp.status_code in (401, 403, 422)


# ---------------------------------------------------------------------------
# PUT /users/me/preferences
# ---------------------------------------------------------------------------


class TestUpdatePreferences:
    """Tests for PUT /api/users/me/preferences."""

    def test_merges_preferences(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """PUT merges new keys into existing preferences."""
        updated = {"preferred_courts": ["Delhi High Court"], "theme": "dark"}

        # First call: UPDATE, second call: SELECT after commit
        update_result = MagicMock()
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _prefs_row(updated)

        mock_db.execute.side_effect = [update_result, select_result]

        resp = client.put("/api/users/me/preferences", json=updated)
        assert resp.status_code == 200
        assert resp.json() == updated

    def test_requires_auth(
        self, unauth_client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Endpoint returns 4xx without authentication."""
        resp = unauth_client.put(
            "/api/users/me/preferences",
            json={"theme": "dark"},
        )
        assert resp.status_code in (401, 403, 422)


# ---------------------------------------------------------------------------
# POST /users/me/preferences/refresh
# ---------------------------------------------------------------------------


class TestRefreshPreferences:
    """Tests for POST /api/users/me/preferences/refresh."""

    def test_computes_from_search_history(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Refresh analyzes search history and saves computed preferences."""
        # Mock search history rows
        history_rows = [
            {"query": "murder section 302", "filters": {"court": "Supreme Court of India", "case_type": "Criminal Appeal"}},
            {"query": "right to privacy", "filters": {"court": "Supreme Court of India", "jurisdiction": "civil"}},
            {"query": "land acquisition", "filters": {"court": "Delhi High Court", "case_type": "Writ Petition"}},
        ]

        search_result = MagicMock()
        search_result.mappings.return_value.all.return_value = history_rows

        # UPDATE result
        update_result = MagicMock()

        # Final SELECT result (the computed preferences after merge)
        computed_prefs = {
            "preferred_jurisdictions": ["civil"],
            "common_case_types": ["Criminal Appeal", "Writ Petition"],
            "preferred_courts": ["Supreme Court of India", "Delhi High Court"],
            "frequent_acts": [],
            "updated_at": "2026-04-01T00:00:00+00:00",
        }
        final_select = MagicMock()
        final_select.mappings.return_value.one_or_none.return_value = _prefs_row(computed_prefs)

        mock_db.execute.side_effect = [search_result, update_result, final_select]

        resp = client.post("/api/users/me/preferences/refresh")
        assert resp.status_code == 200
        data = resp.json()
        # Verify expected keys are present
        assert "preferred_courts" in data
        assert "common_case_types" in data
        assert "updated_at" in data

    def test_handles_empty_history(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Refresh with no search history returns empty preference lists."""
        search_result = MagicMock()
        search_result.mappings.return_value.all.return_value = []

        update_result = MagicMock()

        empty_computed = {
            "preferred_jurisdictions": [],
            "common_case_types": [],
            "preferred_courts": [],
            "frequent_acts": [],
            "updated_at": "2026-04-01T00:00:00+00:00",
        }
        final_select = MagicMock()
        final_select.mappings.return_value.one_or_none.return_value = _prefs_row(empty_computed)

        mock_db.execute.side_effect = [search_result, update_result, final_select]

        resp = client.post("/api/users/me/preferences/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["preferred_courts"] == []
        assert data["common_case_types"] == []

    def test_requires_auth(
        self, unauth_client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Endpoint returns 4xx without authentication."""
        resp = unauth_client.post("/api/users/me/preferences/refresh")
        assert resp.status_code in (401, 403, 422)
