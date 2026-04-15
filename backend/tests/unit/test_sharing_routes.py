"""Tests for memo sharing API routes — create, view, revoke, and public access."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.sharing import router
from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid.uuid4())
_OTHER_USER_ID = str(uuid.uuid4())
_EXECUTION_ID = uuid.uuid4()
_EXECUTION_ID_STR = str(_EXECUTION_ID)
_SHARE_ID = uuid.uuid4()
_SHARE_TOKEN = "abc123tokenXYZ_5678"


def _token(user_id: str = _USER_ID, role: str = "researcher") -> TokenPayload:
    return TokenPayload(
        sub=user_id,
        role=role,
        exp=datetime(2099, 1, 1, tzinfo=UTC),
        iat=datetime(2024, 1, 1, tzinfo=UTC),
        jti=f"jti-{user_id[:8]}",
    )


_USER_TOKEN = _token(_USER_ID)


def _mock_db() -> AsyncMock:
    return AsyncMock()


def _mock_execution(user_id=_USER_ID, status="completed", result_data=None):
    """Create a mock AgentExecution object."""
    exec_mock = MagicMock()
    exec_mock.id = _EXECUTION_ID
    exec_mock.user_id = uuid.UUID(user_id)
    exec_mock.status = status
    exec_mock.agent_type = "research"
    exec_mock.result_data = result_data or {
        "title": "Test Memo Title",
        "memo": "This is the memo body.",
        "footnotes": ["fn1", "fn2"],
        "confidence": 0.85,
    }
    return exec_mock


def _mock_share(
    execution_id=_EXECUTION_ID,
    user_id=_USER_ID,
    is_active=True,
    expires_at=None,
    view_count=5,
):
    """Create a mock SharedMemo object."""
    share = MagicMock()
    share.id = _SHARE_ID
    share.execution_id = execution_id
    share.user_id = uuid.UUID(user_id)
    share.share_token = _SHARE_TOKEN
    share.is_active = is_active
    share.expires_at = expires_at
    share.view_count = view_count
    share.created_at = datetime(2026, 4, 1, tzinfo=UTC)
    return share


def _scalar_result(value):
    """Build a mock execute result where scalar_one_or_none returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    return test_app


@pytest.fixture
def mock_db() -> AsyncMock:
    return _mock_db()


@pytest.fixture
def authed_client(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client authenticated as the test user."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: _USER_TOKEN
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Unauthenticated client (only DB override, no auth override)."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /agents/research/{execution_id}/share — create share
# ---------------------------------------------------------------------------


class TestCreateShare:
    def test_create_share_returns_token(self, authed_client: TestClient, mock_db: AsyncMock):
        """Creating a share for a completed execution returns a share token."""
        execution = _mock_execution()
        # First call: select execution, second call: select existing share
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(execution),  # execution lookup
                _scalar_result(None),  # no existing share
            ]
        )
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        resp = authed_client.post(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 200
        data = resp.json()
        assert "share_token" in data
        assert "share_url" in data
        assert data["share_url"].startswith("/shared/")
        assert "share_id" in data

    def test_create_share_returns_existing(self, authed_client: TestClient, mock_db: AsyncMock):
        """If an active share already exists, return it without creating a new one."""
        execution = _mock_execution()
        existing_share = _mock_share()
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(execution),
                _scalar_result(existing_share),
            ]
        )

        resp = authed_client.post(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 200
        data = resp.json()
        assert data["share_token"] == _SHARE_TOKEN
        # Should NOT have called db.add (no new record)
        mock_db.add.assert_not_called()

    def test_create_share_not_completed(self, authed_client: TestClient, mock_db: AsyncMock):
        """Sharing a non-completed execution returns 400."""
        execution = _mock_execution(status="running")
        mock_db.execute = AsyncMock(return_value=_scalar_result(execution))

        resp = authed_client.post(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 400

    def test_create_share_not_owner(self, authed_client: TestClient, mock_db: AsyncMock):
        """Sharing someone else's execution returns 403."""
        execution = _mock_execution(user_id=_OTHER_USER_ID)
        mock_db.execute = AsyncMock(return_value=_scalar_result(execution))

        resp = authed_client.post(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 403

    def test_create_share_not_found(self, authed_client: TestClient, mock_db: AsyncMock):
        """Sharing a nonexistent execution returns 404."""
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        resp = authed_client.post(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 404

    def test_create_share_invalid_uuid(self, authed_client: TestClient):
        """Invalid execution_id returns 422."""
        resp = authed_client.post("/api/agents/research/not-a-uuid/share")
        assert resp.status_code == 422

    def test_create_share_requires_auth(self, anon_client: TestClient):
        """POST without auth returns 401."""
        resp = anon_client.post(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /agents/research/{execution_id}/share — check share status
# ---------------------------------------------------------------------------


class TestGetShareStatus:
    def test_get_share_exists(self, authed_client: TestClient, mock_db: AsyncMock):
        """Returns share info when an active share exists."""
        share = _mock_share()
        mock_db.execute = AsyncMock(return_value=_scalar_result(share))

        resp = authed_client.get(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 200
        data = resp.json()
        assert data["shared"] is True
        assert data["share_token"] == _SHARE_TOKEN
        assert data["view_count"] == 5

    def test_get_share_not_exists(self, authed_client: TestClient, mock_db: AsyncMock):
        """Returns shared=false when no active share exists."""
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        resp = authed_client.get(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 200
        data = resp.json()
        assert data["shared"] is False


# ---------------------------------------------------------------------------
# DELETE /agents/research/{execution_id}/share — revoke
# ---------------------------------------------------------------------------


class TestRevokeShare:
    def test_revoke_share(self, authed_client: TestClient, mock_db: AsyncMock):
        """Revoking an active share sets is_active=false."""
        share = _mock_share()
        mock_db.execute = AsyncMock(return_value=_scalar_result(share))
        mock_db.commit = AsyncMock()

        resp = authed_client.delete(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 200
        data = resp.json()
        assert data["revoked"] is True
        assert data["share_id"] == str(_SHARE_ID)

    def test_revoke_share_not_found(self, authed_client: TestClient, mock_db: AsyncMock):
        """Revoking when no active share returns 404."""
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        resp = authed_client.delete(f"/api/agents/research/{_EXECUTION_ID_STR}/share")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /shared/{token} — public endpoint
# ---------------------------------------------------------------------------


class TestGetSharedMemo:
    def test_get_shared_memo_returns_content(self, anon_client: TestClient, mock_db: AsyncMock):
        """Public endpoint returns memo content for a valid token."""
        share = _mock_share()
        execution = _mock_execution()
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(share),  # share lookup
                _scalar_result(execution),  # execution lookup
            ]
        )
        mock_db.commit = AsyncMock()

        resp = anon_client.get(f"/api/shared/{_SHARE_TOKEN}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Memo Title"
        assert data["memo"] == "This is the memo body."
        assert data["footnotes"] == ["fn1", "fn2"]
        assert data["confidence"] == 0.85
        assert data["agent_type"] == "research"

    def test_get_shared_memo_not_found(self, anon_client: TestClient, mock_db: AsyncMock):
        """Invalid token returns 404."""
        mock_db.execute = AsyncMock(return_value=_scalar_result(None))

        resp = anon_client.get("/api/shared/nonexistent-token")
        assert resp.status_code == 404

    def test_get_shared_memo_expired(self, anon_client: TestClient, mock_db: AsyncMock):
        """Expired share returns 404."""
        share = _mock_share(expires_at=datetime(2020, 1, 1, tzinfo=UTC))
        mock_db.execute = AsyncMock(return_value=_scalar_result(share))

        resp = anon_client.get(f"/api/shared/{_SHARE_TOKEN}")
        assert resp.status_code == 404

    def test_public_endpoint_no_auth_required(self, anon_client: TestClient, mock_db: AsyncMock):
        """GET /shared/{token} does NOT require authentication."""
        share = _mock_share()
        execution = _mock_execution()
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(share),
                _scalar_result(execution),
            ]
        )
        mock_db.commit = AsyncMock()

        # anon_client has no auth override — this should still work
        resp = anon_client.get(f"/api/shared/{_SHARE_TOKEN}")
        assert resp.status_code == 200

    def test_get_shared_memo_increments_view_count(
        self, anon_client: TestClient, mock_db: AsyncMock
    ):
        """View count is incremented on each access."""
        share = _mock_share(view_count=10)
        execution = _mock_execution()
        mock_db.execute = AsyncMock(
            side_effect=[
                _scalar_result(share),
                _scalar_result(execution),
            ]
        )
        mock_db.commit = AsyncMock()

        anon_client.get(f"/api/shared/{_SHARE_TOKEN}")
        assert share.view_count == 11
