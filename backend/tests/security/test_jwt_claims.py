"""Security tests for JWT token claims and validation."""

from __future__ import annotations

import jwt as pyjwt
import pytest

from app.core.config import settings
from app.security.auth import (
    _ALGORITHM,
    create_access_token,
    create_refresh_token,
    verify_access_token,
)


@pytest.mark.security
class TestJWTClaims:
    """Verify JWT tokens include required security claims."""

    def test_access_token_has_iss_claim(self) -> None:
        token = create_access_token("user-1", "researcher")
        decoded = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[_ALGORITHM],
            audience="smriti-api",
            issuer="smriti",
        )
        assert decoded["iss"] == "smriti"

    def test_access_token_has_aud_claim(self) -> None:
        token = create_access_token("user-1", "researcher")
        decoded = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[_ALGORITHM],
            audience="smriti-api",
            issuer="smriti",
        )
        assert decoded["aud"] == "smriti-api"

    def test_refresh_token_has_iss_claim(self) -> None:
        token = create_refresh_token("user-1")
        decoded = pyjwt.decode(
            token,
            settings.jwt_refresh_secret_key,
            algorithms=[_ALGORITHM],
            audience="smriti-api",
            issuer="smriti",
        )
        assert decoded["iss"] == "smriti"

    def test_refresh_token_has_aud_claim(self) -> None:
        token = create_refresh_token("user-1")
        decoded = pyjwt.decode(
            token,
            settings.jwt_refresh_secret_key,
            algorithms=[_ALGORITHM],
            audience="smriti-api",
            issuer="smriti",
        )
        assert decoded["aud"] == "smriti-api"

    @pytest.mark.asyncio
    async def test_reject_token_wrong_audience(self) -> None:
        """Token with wrong audience should be rejected."""
        payload = {
            "sub": "user-1",
            "role": "researcher",
            "exp": 9999999999,
            "iat": 1000000000,
            "jti": "test-jti",
            "type": "access",
            "iss": "smriti",
            "aud": "wrong-audience",
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)
        with pytest.raises(Exception):
            await verify_access_token(token)

    @pytest.mark.asyncio
    async def test_reject_token_wrong_issuer(self) -> None:
        """Token with wrong issuer should be rejected."""
        payload = {
            "sub": "user-1",
            "role": "researcher",
            "exp": 9999999999,
            "iat": 1000000000,
            "jti": "test-jti",
            "type": "access",
            "iss": "not-smriti",
            "aud": "smriti-api",
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)
        with pytest.raises(Exception):
            await verify_access_token(token)

    @pytest.mark.asyncio
    async def test_reject_expired_token(self) -> None:
        """Expired token should be rejected."""
        payload = {
            "sub": "user-1",
            "role": "researcher",
            "exp": 1000000000,  # long expired
            "iat": 999999000,
            "jti": "test-jti",
            "type": "access",
            "iss": "smriti",
            "aud": "smriti-api",
        }
        token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)
        with pytest.raises(Exception):
            await verify_access_token(token)
