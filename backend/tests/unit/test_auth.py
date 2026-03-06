"""Unit tests for JWT authentication and password hashing."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from app.security.auth import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    hash_password,
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
        with pytest.raises(AuthenticationError, match="Invalid token"):
            verify_access_token(token)


class TestRefreshToken:
    """Tests for refresh token creation and verification."""

    def test_create_and_verify(self):
        token = create_refresh_token("user-456")
        payload = verify_refresh_token(token)
        assert payload.sub == "user-456"

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token("user-123", "admin")
        with pytest.raises(AuthenticationError, match="Invalid token"):
            verify_refresh_token(token)


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
