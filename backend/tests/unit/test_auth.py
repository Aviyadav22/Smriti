"""Unit tests for JWT authentication and password hashing."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.security.auth import (
    clear_revoked_tokens,
    create_access_token,
    create_refresh_token,
    hash_password,
    is_token_revoked,
    revoke_token,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)
from app.security.exceptions import AuthenticationError

# Mock settings for testing
_TEST_SETTINGS = {
    "jwt_secret_key": "test-secret-key-that-is-long-enough-for-hs256",
    "jwt_refresh_secret_key": "test-refresh-secret-key-that-is-long-enough",
    "jwt_access_token_expire_minutes": 15,
    "jwt_refresh_token_expire_days": 7,
    "bcrypt_cost_factor": 4,  # Low cost for fast tests
    "redis_url": "redis://localhost:6379/0",
}


@pytest.fixture(autouse=True)
def mock_settings():
    """Patch settings for all tests in this module."""
    with patch("app.security.auth.settings") as mock:
        for key, value in _TEST_SETTINGS.items():
            setattr(mock, key, value)
        yield mock


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis for revocation tests."""
    mock_r = AsyncMock()
    mock_r.set = AsyncMock()
    mock_r.exists = AsyncMock(return_value=0)
    with patch("app.security.auth._get_revocation_redis", return_value=mock_r):
        yield mock_r


class TestAccessToken:
    """Tests for access token creation and verification."""

    @pytest.mark.asyncio
    async def test_create_and_verify(self):
        token = create_access_token("user-123", "admin")
        payload = await verify_access_token(token)
        assert payload.sub == "user-123"
        assert payload.role == "admin"
        assert payload.jti  # should have a unique ID

    @pytest.mark.asyncio
    async def test_custom_expiry(self):
        token = create_access_token("user-123", "user", expires_delta=timedelta(hours=1))
        payload = await verify_access_token(token)
        assert payload.sub == "user-123"

    @pytest.mark.asyncio
    async def test_expired_token_raises(self):
        token = create_access_token("user-123", "user", expires_delta=timedelta(seconds=-60))
        with pytest.raises(AuthenticationError, match="expired"):
            await verify_access_token(token)

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self):
        with pytest.raises(AuthenticationError):
            await verify_access_token("not-a-valid-token")

    @pytest.mark.asyncio
    async def test_refresh_token_rejected_as_access(self):
        token = create_refresh_token("user-123")
        with pytest.raises(AuthenticationError, match="Invalid"):
            await verify_access_token(token)


class TestRefreshToken:
    """Tests for refresh token creation and verification."""

    @pytest.mark.asyncio
    async def test_create_and_verify(self):
        token = create_refresh_token("user-456")
        payload = await verify_refresh_token(token)
        assert payload.sub == "user-456"

    @pytest.mark.asyncio
    async def test_access_token_rejected_as_refresh(self):
        token = create_access_token("user-123", "admin")
        with pytest.raises(AuthenticationError, match="Invalid"):
            await verify_refresh_token(token)


class TestTokenRevocation:
    """Tests for Redis-backed token revocation."""

    @pytest.mark.asyncio
    async def test_revoke_token_blocks_verification(self, mock_redis: AsyncMock):
        token = create_access_token("user-123", "admin")
        payload = await verify_access_token(token)
        await revoke_token(payload.jti)
        # After revocation, exists returns 1
        mock_redis.exists.return_value = 1
        with pytest.raises(AuthenticationError, match="revoked"):
            await verify_access_token(token)

    @pytest.mark.asyncio
    async def test_revoke_refresh_token(self, mock_redis: AsyncMock):
        token = create_refresh_token("user-123")
        payload = await verify_refresh_token(token)
        await revoke_token(payload.jti)
        mock_redis.exists.return_value = 1
        with pytest.raises(AuthenticationError, match="revoked"):
            await verify_refresh_token(token)

    @pytest.mark.asyncio
    async def test_is_token_revoked(self, mock_redis: AsyncMock):
        mock_redis.exists.return_value = 0
        assert not await is_token_revoked("some-jti")
        mock_redis.exists.return_value = 1
        assert await is_token_revoked("some-jti")

    @pytest.mark.asyncio
    async def test_unrevoked_token_still_works(self, mock_redis: AsyncMock):
        token = create_access_token("user-123", "admin")
        mock_redis.exists.return_value = 0
        result = await verify_access_token(token)
        assert result.sub == "user-123"

    def test_clear_revoked_tokens_is_noop(self):
        """clear_revoked_tokens is a no-op for Redis-backed revocation."""
        clear_revoked_tokens()  # Should not raise


class TestPasswordHashing:
    """Tests for bcrypt password hashing."""

    def test_hash_and_verify(self):
        hashed = hash_password("MySecureP@ss1")
        assert verify_password("MySecureP@ss1", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("test-password")
        assert hashed != "test-password"
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2  # Different salts
