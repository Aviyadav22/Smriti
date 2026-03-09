"""Tests for authentication API routes — register, login, refresh, logout."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.routes.auth import router
from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.exceptions import (
    AuthenticationError,
    RateLimitExceededError,
)
from app.security.rbac import get_current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = str(uuid.uuid4())
_PASSWORD_HASH = "$2b$12$dummyhashforpasswordcheck"  # not real, we mock verify


def _mock_db_session() -> AsyncMock:
    """Create a mock async DB session."""
    return AsyncMock()


def _user_row(
    *,
    user_id: str = _USER_ID,
    password_hash: str = _PASSWORD_HASH,
    role: str = "researcher",
    is_active: bool = True,
    failed_login_count: int = 0,
    locked_until: datetime | None = None,
) -> dict:
    """Build a dict mimicking a user row from mappings()."""
    return {
        "id": user_id,
        "password_hash": password_hash,
        "role": role,
        "is_active": is_active,
        "failed_login_count": failed_login_count,
        "locked_until": locked_until,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Build a test FastAPI app with the auth router and exception handlers."""
    test_app = FastAPI()

    # Register the same exception handlers as the main app
    @test_app.exception_handler(AuthenticationError)
    async def _auth_err(request, exc: AuthenticationError) -> JSONResponse:  # noqa: ANN001
        return JSONResponse(
            status_code=401,
            content={"error": exc.detail, "code": "UNAUTHORIZED"},
        )

    @test_app.exception_handler(RateLimitExceededError)
    async def _rate_err(request, exc: RateLimitExceededError) -> JSONResponse:  # noqa: ANN001
        return JSONResponse(
            status_code=429,
            content={"error": exc.detail, "code": "RATE_LIMITED"},
        )

    test_app.include_router(router, prefix="/api/v1/auth")
    return test_app


@pytest.fixture
def mock_db() -> AsyncMock:
    return _mock_db_session()



@pytest.fixture
def client(app: FastAPI, mock_db: AsyncMock) -> TestClient:
    """Client with DB dependency overridden."""

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    @patch("app.api.routes.auth.create_refresh_token", return_value="register-refresh-jwt")
    @patch("app.api.routes.auth.create_access_token", return_value="register-access-jwt")
    @patch("app.api.routes.auth.hash_password", return_value=_PASSWORD_HASH)
    def test_register_returns_201(
        self,
        mock_hash: MagicMock,
        mock_access: MagicMock,
        mock_refresh: MagicMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """A valid registration returns 201 with JWT tokens (auto-login)."""
        # First execute: SELECT id FROM users WHERE email = :email → None
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [
            select_result,  # email check
            None,           # INSERT users
            None,           # INSERT consents
        ]

        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "SecurePass123",
                "name": "Test User",
                "consent_given": True,
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["access_token"] == "register-access-jwt"
        assert body["refresh_token"] == "register-refresh-jwt"
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0  # Dynamic based on settings
        mock_hash.assert_called_once_with("SecurePass123")
        mock_access.assert_called_once()
        mock_refresh.assert_called_once()

    def test_register_duplicate_email_returns_409(
        self,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Registering with an existing email returns 409."""
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = _USER_ID  # exists

        mock_db.execute.return_value = select_result

        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@example.com",
                "password": "SecurePass123",
                "consent_given": True,
            },
        )

        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    def test_register_invalid_email_returns_422(
        self,
        client: TestClient,
    ) -> None:
        """An invalid email format triggers validation error (422)."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123",
                "consent_given": True,
            },
        )

        assert resp.status_code == 422

    def test_register_short_password_returns_422(
        self,
        client: TestClient,
    ) -> None:
        """Password shorter than 8 chars triggers validation error."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
                "consent_given": True,
            },
        )

        assert resp.status_code == 422

    def test_register_without_consent_returns_400(
        self,
        client: TestClient,
    ) -> None:
        """Registration without consent returns 400."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "SecurePass123",
                "consent_given": False,
            },
        )

        assert resp.status_code == 400
        assert "Consent is required" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    @patch("app.api.routes.auth.create_audit_log", new_callable=AsyncMock)
    @patch("app.api.routes.auth.create_refresh_token", return_value="refresh-jwt")
    @patch("app.api.routes.auth.create_access_token", return_value="access-jwt")
    @patch("app.api.routes.auth.verify_password", return_value=True)
    @patch("app.security.rate_limiter._get_rate_limiter", new_callable=AsyncMock)
    def test_login_returns_tokens(
        self,
        mock_get_limiter: AsyncMock,
        mock_verify: MagicMock,
        mock_access: MagicMock,
        mock_refresh: MagicMock,
        mock_audit: AsyncMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Valid login returns access and refresh tokens."""
        # Allow rate limit to pass
        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit.return_value = True
        mock_get_limiter.return_value = mock_limiter

        # SELECT user row
        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _user_row()

        mock_db.execute.side_effect = [
            select_result,  # SELECT user
            None,           # UPDATE reset failed count
        ]

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "correct-pass"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "access-jwt"
        assert body["refresh_token"] == "refresh-jwt"
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0  # Dynamic based on settings

    @patch("app.api.routes.auth.create_audit_log", new_callable=AsyncMock)
    @patch("app.api.routes.auth.verify_password", return_value=False)
    @patch("app.security.rate_limiter._get_rate_limiter", new_callable=AsyncMock)
    def test_login_wrong_password_returns_401(
        self,
        mock_get_limiter: AsyncMock,
        mock_verify: MagicMock,
        mock_audit: AsyncMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Invalid password returns 401."""
        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit.return_value = True
        mock_get_limiter.return_value = mock_limiter

        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _user_row()

        mock_db.execute.side_effect = [
            select_result,  # SELECT user
            None,           # UPDATE failed count
        ]

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrong-pass"},
        )

        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    @patch("app.security.rate_limiter._get_rate_limiter", new_callable=AsyncMock)
    def test_login_nonexistent_user_returns_401(
        self,
        mock_get_limiter: AsyncMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Login with non-existent email returns 401."""
        # Allow rate limit to pass
        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit.return_value = True
        mock_get_limiter.return_value = mock_limiter

        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = None

        mock_db.execute.return_value = select_result

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "anypass"},
        )

        assert resp.status_code == 401
        assert "Invalid email or password" in resp.json()["detail"]

    @patch("app.security.rate_limiter._rate_limiter", new=None)
    @patch("app.security.rate_limiter._get_rate_limiter", new_callable=AsyncMock)
    def test_login_rate_limited(
        self,
        mock_get_limiter: AsyncMock,
        app: FastAPI,
        mock_db: AsyncMock,
    ) -> None:
        """Excessive login attempts trigger rate limiting (429)."""
        # Make the rate limiter's check_rate_limit return False (denied)
        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit.return_value = False
        mock_get_limiter.return_value = mock_limiter

        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db
        rate_client = TestClient(app, raise_server_exceptions=False)

        resp = rate_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "anypass"},
        )

        assert resp.status_code == 429
        assert resp.json()["code"] == "RATE_LIMITED"
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Refresh tests
# ---------------------------------------------------------------------------


class TestRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    @patch("app.api.routes.auth.revoke_token", new_callable=AsyncMock)
    @patch("app.api.routes.auth.create_audit_log", new_callable=AsyncMock)
    @patch("app.api.routes.auth.create_refresh_token", return_value="new-refresh-jwt")
    @patch("app.api.routes.auth.create_access_token", return_value="new-access-jwt")
    @patch("app.api.routes.auth.verify_refresh_token", new_callable=AsyncMock)
    def test_refresh_returns_new_access_token(
        self,
        mock_verify_refresh: AsyncMock,
        mock_access: MagicMock,
        mock_refresh: MagicMock,
        mock_audit: AsyncMock,
        mock_revoke: AsyncMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """A valid refresh token returns new access and refresh tokens."""
        mock_verify_refresh.return_value = TokenPayload(
            sub=_USER_ID,
            role="refresh",
            exp=datetime.now(timezone.utc),
            iat=datetime.now(timezone.utc),
            jti="some-jti",
        )

        # DB lookup for user role
        user_result = MagicMock()
        user_result.mappings.return_value.one_or_none.return_value = {
            "role": "researcher",
            "is_active": True,
        }
        mock_db.execute.return_value = user_result

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid-refresh-jwt"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "new-access-jwt"
        assert body["refresh_token"] == "new-refresh-jwt"
        # Old refresh token should be revoked
        mock_revoke.assert_called_once()

    @patch("app.api.routes.auth.verify_refresh_token", new_callable=AsyncMock)
    def test_refresh_invalid_token_returns_401(
        self,
        mock_verify_refresh: AsyncMock,
        client: TestClient,
    ) -> None:
        """An invalid refresh token returns 401."""
        mock_verify_refresh.side_effect = AuthenticationError("Invalid token")

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert resp.status_code == 401
        assert resp.json()["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    @patch("app.api.routes.auth.revoke_token", new_callable=AsyncMock)
    def test_logout_revokes_token(
        self,
        mock_revoke: AsyncMock,
        app: FastAPI,
    ) -> None:
        """Logout revokes the current token's JTI."""
        token_payload = TokenPayload(
            sub=_USER_ID,
            role="researcher",
            exp=datetime.now(timezone.utc),
            iat=datetime.now(timezone.utc),
            jti="test-jti-123",
        )

        # Override get_current_user to return our token payload
        app.dependency_overrides[get_current_user] = lambda: token_payload

        logout_client = TestClient(app, raise_server_exceptions=False)
        resp = logout_client.post("/api/v1/auth/logout")

        assert resp.status_code == 200
        assert resp.json()["detail"] == "Successfully logged out"
        mock_revoke.assert_called_once_with("test-jti-123", int(token_payload.exp.timestamp()))
        app.dependency_overrides.clear()

    def test_logout_without_token_returns_401(
        self,
        client: TestClient,
    ) -> None:
        """Logout without a Bearer token returns 401 (or 422 from OAuth2 scheme)."""
        resp = client.post("/api/v1/auth/logout")

        # FastAPI's OAuth2PasswordBearer returns 401 when no token is provided
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Route registration tests
# ---------------------------------------------------------------------------


class TestAuthRouteRegistration:
    """Verify auth routes are correctly registered."""

    def test_auth_routes_registered(self) -> None:
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/register" in paths, f"/register not found in {paths}"
        assert "/login" in paths, f"/login not found in {paths}"
        assert "/refresh" in paths, f"/refresh not found in {paths}"
        assert "/logout" in paths, f"/logout not found in {paths}"

    def test_register_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/register":
                assert "POST" in route.methods  # type: ignore[attr-defined]

    def test_login_is_post(self) -> None:
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/login":
                assert "POST" in route.methods  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Account lock tests
# ---------------------------------------------------------------------------


class TestAccountLock:
    """Tests for account locking after failed login attempts."""

    @patch("app.api.routes.auth.create_audit_log", new_callable=AsyncMock)
    @patch("app.api.routes.auth.verify_password", return_value=False)
    @patch("app.security.rate_limiter._get_rate_limiter", new_callable=AsyncMock)
    def test_failed_login_increments_count(
        self,
        mock_get_limiter: AsyncMock,
        mock_verify: MagicMock,
        mock_audit: AsyncMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """Wrong password increments failed_login_count."""
        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit.return_value = True
        mock_get_limiter.return_value = mock_limiter

        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _user_row(
            failed_login_count=2,
        )

        mock_db.execute.side_effect = [
            select_result,  # SELECT user
            None,           # UPDATE failed count
        ]

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "wrong-pass"},
        )

        assert resp.status_code == 401
        # Verify UPDATE was called (second db.execute call)
        assert mock_db.execute.call_count >= 2

    @patch("app.security.rate_limiter._get_rate_limiter", new_callable=AsyncMock)
    def test_locked_account_returns_423(
        self,
        mock_get_limiter: AsyncMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """An account locked until a future time returns 423."""
        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit.return_value = True
        mock_get_limiter.return_value = mock_limiter

        from datetime import timedelta

        future = datetime.now(timezone.utc) + timedelta(minutes=15)

        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _user_row(
            failed_login_count=5,
            locked_until=future,
        )
        mock_db.execute.return_value = select_result

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "locked@example.com", "password": "AnyPass1"},
        )

        assert resp.status_code == 423
        assert "locked" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Inactive user tests
# ---------------------------------------------------------------------------


class TestInactiveUser:
    """Tests for deactivated user access control."""

    @patch("app.api.routes.auth.verify_password", return_value=True)
    @patch("app.security.rate_limiter._get_rate_limiter", new_callable=AsyncMock)
    def test_inactive_user_login_returns_403(
        self,
        mock_get_limiter: AsyncMock,
        mock_verify: MagicMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """A deactivated user cannot log in."""
        mock_limiter = AsyncMock()
        mock_limiter.check_rate_limit.return_value = True
        mock_get_limiter.return_value = mock_limiter

        select_result = MagicMock()
        select_result.mappings.return_value.one_or_none.return_value = _user_row(
            is_active=False,
        )
        mock_db.execute.return_value = select_result

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "inactive@example.com", "password": "GoodPass1"},
        )

        assert resp.status_code == 403
        assert "deactivated" in resp.json()["detail"].lower()

    @patch("app.api.routes.auth.verify_refresh_token", new_callable=AsyncMock)
    def test_inactive_user_refresh_returns_401(
        self,
        mock_verify_refresh: AsyncMock,
        client: TestClient,
        mock_db: AsyncMock,
    ) -> None:
        """A deactivated user cannot refresh their token."""
        mock_verify_refresh.return_value = TokenPayload(
            sub=_USER_ID,
            role="refresh",
            exp=datetime.now(timezone.utc),
            iat=datetime.now(timezone.utc),
            jti="some-jti",
        )

        user_result = MagicMock()
        user_result.mappings.return_value.one_or_none.return_value = {
            "role": "researcher",
            "is_active": False,
        }
        mock_db.execute.return_value = user_result

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid-refresh-jwt"},
        )

        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"].lower() or "not found" in resp.json()["detail"].lower()
