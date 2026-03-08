"""Tests for DPDP Act 2023 compliance API routes.

Covers all four endpoints:
- GET  /api/v1/dpdp/data-summary
- POST /api/v1/dpdp/erasure
- POST /api/v1/dpdp/consent-withdraw
- GET  /api/v1/dpdp/consent-status
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.dpdp import router
from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid.uuid4())


def _token_payload(user_id: str = _USER_ID) -> TokenPayload:
    """Build a fake TokenPayload for dependency injection."""
    now = datetime.now(timezone.utc)
    return TokenPayload(
        sub=user_id,
        role="researcher",
        exp=now,
        iat=now,
        jti=str(uuid.uuid4()),
    )


class _FakeNestedTransaction:
    """Fake async context manager for db.begin_nested()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _mock_db_session() -> AsyncMock:
    """Create a mock async DB session with begin_nested async context manager."""
    db = AsyncMock()
    # begin_nested() is NOT a coroutine — it returns an async context manager directly
    db.begin_nested = MagicMock(return_value=_FakeNestedTransaction())
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Build a test FastAPI app with the DPDP router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1/dpdp")
    return test_app


@pytest.fixture
def mock_db() -> AsyncMock:
    return _mock_db_session()


@pytest.fixture
def token() -> TokenPayload:
    return _token_payload()


@pytest.fixture
def client(app: FastAPI, mock_db: AsyncMock, token: TokenPayload) -> TestClient:
    """Client with DB and auth dependencies overridden."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: token
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client with DB overridden but NO auth override (unauthenticated)."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    # Do NOT override get_current_user — let OAuth2 scheme reject
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unauthenticated access tests (401 for all endpoints)
# ---------------------------------------------------------------------------


class TestUnauthenticatedAccess:
    """All DPDP endpoints must reject requests without a valid token."""

    def test_data_summary_unauthenticated(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/dpdp/data-summary")
        assert resp.status_code in (401, 403)

    def test_erasure_unauthenticated(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post("/api/v1/dpdp/erasure")
        assert resp.status_code in (401, 403)

    def test_consent_withdraw_unauthenticated(self, unauth_client: TestClient) -> None:
        resp = unauth_client.post("/api/v1/dpdp/consent-withdraw")
        assert resp.status_code in (401, 403)

    def test_consent_status_unauthenticated(self, unauth_client: TestClient) -> None:
        resp = unauth_client.get("/api/v1/dpdp/consent-status")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /data-summary
# ---------------------------------------------------------------------------


class TestDataSummary:
    """Tests for GET /api/v1/dpdp/data-summary."""

    def test_data_summary_returns_counts(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Data summary returns correct counts for all data categories."""
        row = {
            "chat_sessions": 5,
            "chat_messages": 42,
            "documents": 3,
            "agent_executions": 7,
            "audit_entries": 15,
            "consents": 2,
        }
        result_mock = MagicMock()
        result_mock.mappings.return_value.one.return_value = row
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/dpdp/data-summary")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == token.sub
        assert body["data_categories"]["chat_sessions"] == 5
        assert body["data_categories"]["chat_messages"] == 42
        assert body["data_categories"]["documents"] == 3
        assert body["data_categories"]["agent_executions"] == 7
        assert body["data_categories"]["audit_entries"] == 15
        assert body["data_categories"]["consents"] == 2

    def test_data_summary_zero_counts(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Data summary works for a user with no data."""
        row = {
            "chat_sessions": 0,
            "chat_messages": 0,
            "documents": 0,
            "agent_executions": 0,
            "audit_entries": 0,
            "consents": 0,
        }
        result_mock = MagicMock()
        result_mock.mappings.return_value.one.return_value = row
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/dpdp/data-summary")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == token.sub
        for category, count in body["data_categories"].items():
            assert count == 0, f"Expected 0 for {category}, got {count}"

    def test_data_summary_executes_query_with_user_id(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Verify the query is executed with the authenticated user's ID."""
        row = {
            "chat_sessions": 0,
            "chat_messages": 0,
            "documents": 0,
            "agent_executions": 0,
            "audit_entries": 0,
            "consents": 0,
        }
        result_mock = MagicMock()
        result_mock.mappings.return_value.one.return_value = row
        mock_db.execute.return_value = result_mock

        client.get("/api/v1/dpdp/data-summary")

        # Verify execute was called with the user's ID in params
        call_args = mock_db.execute.call_args
        assert call_args is not None
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("parameters", {})
        assert params["uid"] == token.sub

    def test_data_summary_response_structure(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Response has required top-level keys."""
        row = {
            "chat_sessions": 1,
            "chat_messages": 2,
            "documents": 3,
            "agent_executions": 4,
            "audit_entries": 5,
            "consents": 6,
        }
        result_mock = MagicMock()
        result_mock.mappings.return_value.one.return_value = row
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/dpdp/data-summary")

        body = resp.json()
        assert "user_id" in body
        assert "data_categories" in body
        expected_keys = {
            "chat_sessions",
            "chat_messages",
            "documents",
            "agent_executions",
            "audit_entries",
            "consents",
        }
        assert set(body["data_categories"].keys()) == expected_keys


# ---------------------------------------------------------------------------
# POST /erasure
# ---------------------------------------------------------------------------


class TestErasure:
    """Tests for POST /api/v1/dpdp/erasure."""

    def test_erasure_returns_success(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Erasure endpoint returns a success status."""
        # All db.execute calls within begin_nested succeed (AsyncMock default)
        resp = client.post("/api/v1/dpdp/erasure")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "erasure_completed"
        assert "deleted" in body["detail"].lower() or "deactivated" in body["detail"].lower()

    def test_erasure_uses_nested_transaction(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Erasure uses begin_nested() for atomic deletion."""
        client.post("/api/v1/dpdp/erasure")

        mock_db.begin_nested.assert_called_once()

    def test_erasure_commits_after_nested(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Erasure calls commit() after the nested transaction block."""
        client.post("/api/v1/dpdp/erasure")

        mock_db.commit.assert_called_once()

    def test_erasure_deletes_all_tables(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Erasure issues DELETE statements for all user data tables."""
        client.post("/api/v1/dpdp/erasure")

        # Collect all SQL text from execute calls
        sql_statements = []
        for call in mock_db.execute.call_args_list:
            sql_arg = call[0][0]
            # text() objects have a .text attribute
            sql_text = sql_arg.text if hasattr(sql_arg, "text") else str(sql_arg)
            sql_statements.append(sql_text.lower())

        all_sql = " ".join(sql_statements)

        # Verify all required deletions
        assert "delete from agent_executions" in all_sql, "Should delete agent_executions"
        assert "delete from chat_messages" in all_sql, "Should delete chat_messages"
        assert "delete from chat_sessions" in all_sql, "Should delete chat_sessions"
        assert "delete from documents" in all_sql, "Should delete documents"
        assert "delete from consents" in all_sql, "Should delete consents"

    def test_erasure_logs_to_dpdp_audit(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Erasure inserts an audit log entry into dpdp_audit_log."""
        client.post("/api/v1/dpdp/erasure")

        sql_statements = []
        for call in mock_db.execute.call_args_list:
            sql_arg = call[0][0]
            sql_text = sql_arg.text if hasattr(sql_arg, "text") else str(sql_arg)
            sql_statements.append(sql_text.lower())

        all_sql = " ".join(sql_statements)
        assert "insert into dpdp_audit_log" in all_sql, "Should log erasure to dpdp_audit_log"
        assert "erasure_completed" in all_sql, "Audit action should be 'erasure_completed'"

    def test_erasure_deactivates_user(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Erasure sets user is_active = false."""
        client.post("/api/v1/dpdp/erasure")

        sql_statements = []
        for call in mock_db.execute.call_args_list:
            sql_arg = call[0][0]
            sql_text = sql_arg.text if hasattr(sql_arg, "text") else str(sql_arg)
            sql_statements.append(sql_text.lower())

        all_sql = " ".join(sql_statements)
        assert "update users set is_active = false" in all_sql, "Should deactivate user"

    def test_erasure_passes_correct_user_id(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """All erasure queries use the authenticated user's ID."""
        client.post("/api/v1/dpdp/erasure")

        for call in mock_db.execute.call_args_list:
            if len(call[0]) > 1:
                params = call[0][1]
                assert params.get("uid") == token.sub, (
                    f"Expected uid={token.sub}, got {params.get('uid')}"
                )

    def test_erasure_deletes_chat_messages_via_session_join(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Chat messages are deleted via subquery join on chat_sessions (not direct user_id)."""
        client.post("/api/v1/dpdp/erasure")

        sql_statements = []
        for call in mock_db.execute.call_args_list:
            sql_arg = call[0][0]
            sql_text = sql_arg.text if hasattr(sql_arg, "text") else str(sql_arg)
            sql_statements.append(sql_text.lower())

        # Find the chat_messages DELETE and verify it uses a subquery
        chat_msg_deletes = [s for s in sql_statements if "chat_messages" in s and "delete" in s]
        assert len(chat_msg_deletes) == 1
        assert "session_id in" in chat_msg_deletes[0], (
            "chat_messages should be deleted via session_id subquery"
        )


# ---------------------------------------------------------------------------
# POST /consent-withdraw
# ---------------------------------------------------------------------------


class TestConsentWithdraw:
    """Tests for POST /api/v1/dpdp/consent-withdraw."""

    def test_consent_withdraw_returns_success(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Consent withdrawal returns status confirmation."""
        resp = client.post("/api/v1/dpdp/consent-withdraw")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "consent_withdrawn"

    def test_consent_withdraw_updates_only_active_consents(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Consent withdrawal only targets granted=true AND revoked_at IS NULL."""
        client.post("/api/v1/dpdp/consent-withdraw")

        sql_statements = []
        for call in mock_db.execute.call_args_list:
            sql_arg = call[0][0]
            sql_text = sql_arg.text if hasattr(sql_arg, "text") else str(sql_arg)
            sql_statements.append(sql_text.lower())

        update_stmts = [s for s in sql_statements if "update consents" in s]
        assert len(update_stmts) == 1
        update_sql = update_stmts[0]
        assert "granted = true" in update_sql, "Should only update granted consents"
        assert "revoked_at is null" in update_sql, "Should only update non-revoked consents"
        assert "revoked_at = now()" in update_sql, "Should set revoked_at to current time"

    def test_consent_withdraw_logs_audit(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Consent withdrawal inserts an audit log entry."""
        client.post("/api/v1/dpdp/consent-withdraw")

        sql_statements = []
        for call in mock_db.execute.call_args_list:
            sql_arg = call[0][0]
            sql_text = sql_arg.text if hasattr(sql_arg, "text") else str(sql_arg)
            sql_statements.append(sql_text.lower())

        all_sql = " ".join(sql_statements)
        assert "insert into dpdp_audit_log" in all_sql
        assert "consent_withdrawn" in all_sql

    def test_consent_withdraw_commits(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Consent withdrawal calls commit()."""
        client.post("/api/v1/dpdp/consent-withdraw")

        mock_db.commit.assert_called_once()

    def test_consent_withdraw_uses_correct_user_id(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Consent withdrawal queries use the authenticated user's ID."""
        client.post("/api/v1/dpdp/consent-withdraw")

        for call in mock_db.execute.call_args_list:
            if len(call[0]) > 1:
                params = call[0][1]
                assert params.get("uid") == token.sub


# ---------------------------------------------------------------------------
# GET /consent-status
# ---------------------------------------------------------------------------


class TestConsentStatus:
    """Tests for GET /api/v1/dpdp/consent-status."""

    def test_consent_status_returns_consents(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Consent status returns list of consent records."""
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            {
                "consent_type": "data_processing",
                "granted": True,
                "version": "1.0",
                "created_at": now,
                "revoked_at": None,
            },
            {
                "consent_type": "analytics",
                "granted": False,
                "version": "1.0",
                "created_at": now,
                "revoked_at": now,
            },
        ]
        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = rows
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/dpdp/consent-status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == token.sub
        assert len(body["consents"]) == 2

        first = body["consents"][0]
        assert first["type"] == "data_processing"
        assert first["granted"] is True
        assert first["version"] == "1.0"
        assert first["granted_at"] is not None
        assert first["revoked_at"] is None

        second = body["consents"][1]
        assert second["type"] == "analytics"
        assert second["granted"] is False
        assert second["revoked_at"] is not None

    def test_consent_status_empty_list(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Consent status returns empty list for user with no consents."""
        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = []
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/dpdp/consent-status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == token.sub
        assert body["consents"] == []

    def test_consent_status_response_structure(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """Each consent record has the expected keys."""
        now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
        rows = [
            {
                "consent_type": "terms",
                "granted": True,
                "version": "2.0",
                "created_at": now,
                "revoked_at": None,
            },
        ]
        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = rows
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/dpdp/consent-status")

        body = resp.json()
        consent = body["consents"][0]
        expected_keys = {"type", "granted", "version", "granted_at", "revoked_at"}
        assert set(consent.keys()) == expected_keys

    def test_consent_status_uses_correct_user_id(
        self, client: TestClient, mock_db: AsyncMock, token: TokenPayload
    ) -> None:
        """Consent status query uses the authenticated user's ID."""
        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = []
        mock_db.execute.return_value = result_mock

        client.get("/api/v1/dpdp/consent-status")

        call_args = mock_db.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else {}
        assert params["uid"] == token.sub

    def test_consent_status_revoked_at_is_string_when_present(
        self, client: TestClient, mock_db: AsyncMock
    ) -> None:
        """revoked_at is serialized as a string when not None."""
        revoked = datetime(2026, 3, 7, 10, 0, 0, tzinfo=timezone.utc)
        rows = [
            {
                "consent_type": "data_processing",
                "granted": True,
                "version": "1.0",
                "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
                "revoked_at": revoked,
            },
        ]
        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = rows
        mock_db.execute.return_value = result_mock

        resp = client.get("/api/v1/dpdp/consent-status")

        consent = resp.json()["consents"][0]
        assert isinstance(consent["revoked_at"], str)
        assert "2026" in consent["revoked_at"]


# ---------------------------------------------------------------------------
# Route registration tests
# ---------------------------------------------------------------------------


class TestDpdpRouteRegistration:
    """Verify DPDP routes are correctly registered."""

    def test_all_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/data-summary" in paths
        assert "/erasure" in paths
        assert "/consent-withdraw" in paths
        assert "/consent-status" in paths

    def test_data_summary_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/data-summary":
                assert "GET" in route.methods  # type: ignore[attr-defined]

    def test_erasure_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/erasure":
                assert "POST" in route.methods  # type: ignore[attr-defined]

    def test_consent_withdraw_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/consent-withdraw":
                assert "POST" in route.methods  # type: ignore[attr-defined]

    def test_consent_status_is_get(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/consent-status":
                assert "GET" in route.methods  # type: ignore[attr-defined]
