"""JWT authentication and password hashing for the Smriti platform.

Provides token creation/verification using PyJWT and password hashing
using bcrypt.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid

import bcrypt
import jwt

from app.core.config import settings
from app.security.exceptions import AuthenticationError

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Decoded JWT token payload."""

    sub: str  # user_id
    role: str
    exp: datetime
    iat: datetime
    jti: str  # unique token ID


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

_ALGORITHM: str = "HS256"


def create_access_token(
    user_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: The unique user identifier to embed as the ``sub`` claim.
        role: The user's role (e.g., ``"admin"``, ``"user"``, ``"viewer"``).
        expires_delta: Custom expiry duration. Defaults to
            ``settings.jwt_access_token_expire_minutes`` minutes.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload: dict[str, str | int | float] = {
        "sub": user_id,
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=_ALGORITHM)


def create_refresh_token(
    user_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT refresh token.

    Args:
        user_id: The unique user identifier to embed as the ``sub`` claim.
        expires_delta: Custom expiry duration. Defaults to
            ``settings.jwt_refresh_token_expire_days`` days.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    payload: dict[str, str | int | float] = {
        "sub": user_id,
        "role": "refresh",
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }
    return jwt.encode(
        payload, settings.jwt_refresh_secret_key, algorithm=_ALGORITHM
    )


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


def _decode_token(token: str, secret: str, expected_type: str) -> TokenPayload:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT string.
        secret: The signing secret to verify against.
        expected_type: Expected token type (``"access"`` or ``"refresh"``).

    Returns:
        Parsed TokenPayload.

    Raises:
        AuthenticationError: If the token is invalid, expired, or of the
            wrong type.
    """
    try:
        decoded: dict[str, str | int | float] = jwt.decode(
            token, secret, algorithms=[_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(f"Invalid token: {exc}")

    token_type = decoded.get("type")
    if token_type != expected_type:
        raise AuthenticationError(
            f"Expected {expected_type} token, got {token_type}"
        )

    sub = decoded.get("sub")
    role = decoded.get("role")
    jti = decoded.get("jti")
    if not sub or not role or not jti:
        raise AuthenticationError("Token missing required claims")

    return TokenPayload(
        sub=str(sub),
        role=str(role),
        exp=datetime.fromtimestamp(float(decoded["exp"]), tz=timezone.utc),
        iat=datetime.fromtimestamp(float(decoded["iat"]), tz=timezone.utc),
        jti=str(jti),
    )


def verify_access_token(token: str) -> TokenPayload:
    """Decode and validate an access token.

    Args:
        token: Encoded JWT access token.

    Returns:
        Parsed TokenPayload.

    Raises:
        AuthenticationError: If the token is invalid or expired.
    """
    return _decode_token(token, settings.jwt_secret_key, "access")


def verify_refresh_token(token: str) -> TokenPayload:
    """Decode and validate a refresh token.

    Args:
        token: Encoded JWT refresh token.

    Returns:
        Parsed TokenPayload.

    Raises:
        AuthenticationError: If the token is invalid or expired.
    """
    return _decode_token(token, settings.jwt_refresh_secret_key, "refresh")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        password: The plaintext password.

    Returns:
        The bcrypt hash as a UTF-8 string.
    """
    salt = bcrypt.gensalt(rounds=settings.bcrypt_cost_factor)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain: The plaintext password to check.
        hashed: The stored bcrypt hash.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(
        plain.encode("utf-8"), hashed.encode("utf-8")
    )
