"""Security module: auth, RBAC, rate limiting, encryption, audit, consent."""

from app.security.auth import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)
from app.security.encryption import decrypt_field, encrypt_field
from app.security.exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitExceededError,
)
from app.security.rbac import get_current_user, require_role
from app.security.sanitizer import (
    detect_prompt_injection,
    sanitize_input,
    sanitize_search_query,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitExceededError",
    "TokenPayload",
    "create_access_token",
    "create_refresh_token",
    "decrypt_field",
    "detect_prompt_injection",
    "encrypt_field",
    "get_current_user",
    "hash_password",
    "require_role",
    "sanitize_input",
    "sanitize_search_query",
    "verify_access_token",
    "verify_password",
    "verify_refresh_token",
]
