"""Unit tests for JWT authentication and password hashing."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from app.security.auth import (
    TokenPayload,
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
}


@pytest.fixture(autouse=True)
def mock_settings():
    """Patch settings for all tests in this module."""
    with patch("app.security.auth.settings") as mock:
        for key, value in _TEST_SETTINGS.items():
            setattr(mock, key, value)
        yield mock


class TestAccessToken:
    """Tests for access token creation and verification."""

    def test_create_and_verify(self):
        token = create_access_token("user-123", "admin")
        payload = verify_access_token(token)
        assert payload.sub == "user-123"
        assert payload.role == "admin"
        assert payload.jti  # should have a unique ID

    def test_custom_expiry(self):
        token = create_access_token("user-123", "user", expires_delta=timedelta(hours=1))
        payload = verify_access_token(token)
        assert payload.sub == "user-123"

    def test_expired_token_raises(self):
        token = create_access_token("user-123", "user", expires_delta=timedelta(seconds=-1))
        with pytest.raises(AuthenticationError, match="expired"):
            verify_access_token(token)

    def test_invalid_token_raises(self):
        with pytest.raises(AuthenticationError):
            verify_access_token("not-a-valid-token")

    def test_refresh_token_rejected_as_access(self):
        token = create_refresh_token("user-123")
        with pytest.raises(AuthenticationError, match="Invalid"):
            verify_access_token(token)


class TestRefreshToken:
    """Tests for refresh token creation and verification."""

    def test_create_and_verify(self):
        token = create_refresh_token("user-456")
        payload = verify_refresh_token(token)
        assert payload.sub == "user-456"

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token("user-123", "admin")
        with pytest.raises(AuthenticationError, match="Invalid"):
            verify_refresh_token(token)


class TestTokenRevocation:
    """Tests for token revocation (blacklisting)."""

    def setup_method(self):
        """Clear the revocation blacklist before each test."""
        clear_revoked_tokens()

    def teardown_method(self):
        """Clear the revocation blacklist after each test."""
        clear_revoked_tokens()

    def test_revoke_token_blocks_verification(self):
        token = create_access_token("user-123", "admin")
        payload = verify_access_token(token)
        revoke_token(payload.jti)
        with pytest.raises(AuthenticationError, match="revoked"):
            verify_access_token(token)

    def test_revoke_refresh_token(self):
        token = create_refresh_token("user-123")
        payload = verify_refresh_token(token)
        revoke_token(payload.jti)
        with pytest.raises(AuthenticationError, match="revoked"):
            verify_refresh_token(token)

    def test_is_token_revoked(self):
        assert not is_token_revoked("some-jti")
        revoke_token("some-jti")
        assert is_token_revoked("some-jti")

    def test_unrevoked_token_still_works(self):
        token = create_access_token("user-123", "admin")
        payload = verify_access_token(token)
        # Revoke a different JTI
        revoke_token("different-jti")
        # Original token should still work
        result = verify_access_token(token)
        assert result.sub == "user-123"

    def test_clear_revoked_tokens(self):
        revoke_token("jti-1")
        revoke_token("jti-2")
        assert is_token_revoked("jti-1")
        clear_revoked_tokens()
        assert not is_token_revoked("jti-1")
        assert not is_token_revoked("jti-2")


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
