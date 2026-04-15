"""Tests for chat API routes (SSE streaming, session management, history)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.chat import router
from app.core.chat.rag import RAGEvent
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_USER_ID = str(uuid.uuid4())
_OTHER_USER_ID = str(uuid.uuid4())
_SESSION_ID = str(uuid.uuid4())


def _make_token(user_id: str = _TEST_USER_ID) -> TokenPayload:
    now = datetime.now(UTC)
    return TokenPayload(
        sub=user_id,
        role="user",
        exp=now,
        iat=now,
        jti=str(uuid.uuid4()),
    )


def _make_session_row(
    user_id: str = _TEST_USER_ID,
    session_id: str = _SESSION_ID,
    title: str = "Test session",
) -> dict:
    now = datetime.now(UTC)
    return {
        "id": session_id,
        "user_id": user_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "message_count": 2,
    }


def _make_message_row(
    role: str = "assistant",
    content: str = "This is a test answer.",
    sources: list | None = None,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "sources": sources,
        "created_at": datetime.now(UTC),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/chat")
    return test_app


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_redis() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def authed_client(app: FastAPI, mock_db: AsyncMock, mock_redis: AsyncMock) -> TestClient:
    """Client with auth + DB + Redis overrides."""

    async def _override_user() -> TokenPayload:
        return _make_token()

    async def _override_db():
        return mock_db

    async def _override_redis():
        return mock_redis

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


class TestRouteRegistration:
    def test_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "" in paths  # POST /chat
        assert "/sessions" in paths  # GET /chat/sessions
        assert "/{session_id}/message" in paths
        assert "/{session_id}/history" in paths
        assert "/{session_id}" in paths  # DELETE

    def test_create_chat_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "":
                assert "POST" in route.methods

    def test_sessions_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/sessions":
                assert "GET" in route.methods

    def test_delete_is_delete(self) -> None:
        found = False
        for route in router.routes:
            if (
                hasattr(route, "path")
                and route.path == "/{session_id}"
                and hasattr(route, "methods")
            ) and "DELETE" in route.methods:
                found = True
        assert found, "DELETE /{session_id} route not found"


# ---------------------------------------------------------------------------
# POST /chat — create session (SSE)
# ---------------------------------------------------------------------------


class TestCreateSession:
    @patch("app.api.routes.chat.get_reranker")
    @patch("app.api.routes.chat.get_vector_store")
    @patch("app.api.routes.chat.get_embedder")
    @patch("app.api.routes.chat.get_llm")
    @patch("app.api.routes.chat.rag_respond")
    def test_create_session_returns_sse_stream(
        self,
        mock_rag: MagicMock,
        mock_get_llm: MagicMock,
        mock_get_embedder: MagicMock,
        mock_get_vs: MagicMock,
        mock_get_reranker: MagicMock,
        authed_client: TestClient,
    ) -> None:
        """POST /chat returns an SSE text/event-stream response."""
        session_id = str(uuid.uuid4())

        async def _fake_rag(**kwargs):
            yield RAGEvent(type="session", data={"session_id": session_id})
            yield RAGEvent(type="chunk", data={"text": "Hello"})
            yield RAGEvent(type="done", data={"message_id": "m1"})

        mock_rag.return_value = _fake_rag()

        resp = authed_client.post(
            "/api/v1/chat",
            json={"message": "What is Article 21?"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # Parse SSE lines
        lines = [ln for ln in resp.text.strip().split("\n") if ln.startswith("data:")]
        assert len(lines) == 3
        assert '"session"' in lines[0] or '"session_id"' in lines[0]


# ---------------------------------------------------------------------------
# POST /chat/{session_id}/message — send message (SSE)
# ---------------------------------------------------------------------------


class TestSendMessage:
    @patch("app.api.routes.chat.get_reranker")
    @patch("app.api.routes.chat.get_vector_store")
    @patch("app.api.routes.chat.get_embedder")
    @patch("app.api.routes.chat.get_llm")
    @patch("app.api.routes.chat.rag_respond")
    def test_send_message_to_existing_session(
        self,
        mock_rag: MagicMock,
        mock_get_llm: MagicMock,
        mock_get_embedder: MagicMock,
        mock_get_vs: MagicMock,
        mock_get_reranker: MagicMock,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """POST /chat/{session_id}/message streams SSE with session_id forwarded."""
        sid = str(uuid.uuid4())

        # Set up DB mock for IDOR ownership check
        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = {
            "user_id": _TEST_USER_ID,
        }
        mock_db.execute = AsyncMock(return_value=session_result)

        async def _fake_rag(**kwargs):
            # Verify session_id is forwarded
            assert kwargs.get("session_id") == sid
            yield RAGEvent(type="chunk", data={"text": "Response"})
            yield RAGEvent(type="done", data={"message_id": "m2"})

        mock_rag.side_effect = lambda **kw: _fake_rag(**kw)

        resp = authed_client.post(
            f"/api/v1/chat/{sid}/message",
            json={"message": "Follow-up question"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        lines = [ln for ln in resp.text.strip().split("\n") if ln.startswith("data:")]
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# GET /chat/sessions — list sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    def test_get_sessions_returns_user_sessions(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """GET /chat/sessions returns paginated sessions for the authed user."""
        rows = [_make_session_row(), _make_session_row(session_id=str(uuid.uuid4()), title="Second")]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        sessions_result = MagicMock()
        sessions_result.mappings.return_value.all.return_value = rows
        mock_db.execute = AsyncMock(side_effect=[count_result, sessions_result])

        resp = authed_client.get("/api/v1/chat/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data["sessions"]) == 2
        assert data["total"] == 2
        assert data["sessions"][0]["title"] == "Test session"
        assert data["sessions"][1]["title"] == "Second"
        assert "message_count" in data["sessions"][0]

    def test_get_sessions_returns_empty_list(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        sessions_result = MagicMock()
        sessions_result.mappings.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[count_result, sessions_result])

        resp = authed_client.get("/api/v1/chat/sessions")
        assert resp.status_code == 200
        assert resp.json() == {"sessions": [], "total": 0, "page": 1, "page_size": 20}


# ---------------------------------------------------------------------------
# GET /chat/{session_id}/history — message history
# ---------------------------------------------------------------------------


class TestGetHistory:
    @patch("app.api.routes.chat.safe_decrypt", side_effect=lambda v: v)
    def test_get_history_returns_decrypted_messages(
        self,
        mock_decrypt: MagicMock,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """GET /chat/{session_id}/history returns decrypted messages."""
        session_row = {"user_id": _TEST_USER_ID, "title": "Test"}
        msg_rows = [
            _make_message_row(role="user", content="What is Article 21?"),
            _make_message_row(role="assistant", content="Article 21 guarantees..."),
        ]

        # First call: session lookup; Second call: messages
        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = session_row
        messages_result = MagicMock()
        messages_result.mappings.return_value.all.return_value = msg_rows
        mock_db.execute = AsyncMock(side_effect=[session_result, messages_result])

        resp = authed_client.get(f"/api/v1/chat/{_SESSION_ID}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["content"] == "Article 21 guarantees..."
        assert mock_decrypt.call_count == 2

    def test_get_history_returns_404_for_missing_session(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=session_result)

        resp = authed_client.get(f"/api/v1/chat/{uuid.uuid4()}/history")
        assert resp.status_code == 404

    def test_get_history_returns_empty_sources_when_null(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Sources field defaults to [] when null in DB."""
        session_row = {"user_id": _TEST_USER_ID, "title": "Test"}
        msg_rows = [_make_message_row(sources=None)]

        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = session_row
        messages_result = MagicMock()
        messages_result.mappings.return_value.all.return_value = msg_rows
        mock_db.execute = AsyncMock(side_effect=[session_result, messages_result])

        with patch("app.api.routes.chat.safe_decrypt", side_effect=lambda v: v):
            resp = authed_client.get(f"/api/v1/chat/{_SESSION_ID}/history")

        assert resp.status_code == 200
        assert resp.json()["messages"][0]["sources"] == []


# ---------------------------------------------------------------------------
# DELETE /chat/{session_id} — delete session
# ---------------------------------------------------------------------------


class TestDeleteSession:
    def test_delete_session_returns_deleted_status(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """DELETE /chat/{session_id} returns {"status": "deleted"}."""
        session_row = {"user_id": _TEST_USER_ID}
        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = session_row
        mock_db.execute = AsyncMock(return_value=session_result)
        mock_db.commit = AsyncMock()

        resp = authed_client.delete(f"/api/v1/chat/{_SESSION_ID}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "deleted"}

    def test_delete_session_returns_404_for_missing(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=session_result)

        resp = authed_client.delete(f"/api/v1/chat/{uuid.uuid4()}")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Access control — other user's session
# ---------------------------------------------------------------------------


class TestAccessControl:
    def test_history_access_denied_for_other_users_session(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """GET history returns 403 when session belongs to another user."""
        session_row = {"user_id": _OTHER_USER_ID, "title": "Other user's chat"}
        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = session_row
        mock_db.execute = AsyncMock(return_value=session_result)

        resp = authed_client.get(f"/api/v1/chat/{_SESSION_ID}/history")
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"]

    def test_delete_access_denied_for_other_users_session(
        self,
        authed_client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """DELETE returns 403 when session belongs to another user."""
        session_row = {"user_id": _OTHER_USER_ID}
        session_result = MagicMock()
        session_result.mappings.return_value.one_or_none.return_value = session_row
        mock_db.execute = AsyncMock(return_value=session_result)

        resp = authed_client.delete(f"/api/v1/chat/{_SESSION_ID}")
        assert resp.status_code == 403
        assert "Access denied" in resp.json()["detail"]
