"""Role-based access control (RBAC) dependencies for FastAPI.

Provides FastAPI-compatible dependency functions for extracting the current
user from a JWT token and enforcing role-based authorization.
"""

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.security.auth import verify_access_token, TokenPayload
from app.security.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> TokenPayload:
    """FastAPI dependency that extracts and validates the current user.

    Reads the Bearer token from the ``Authorization`` header, decodes it,
    and returns the token payload.

    Args:
        token: The JWT token extracted by ``oauth2_scheme``.

    Returns:
        The decoded TokenPayload for the authenticated user.

    Raises:
        AuthenticationError: If the token is invalid or expired.
    """
    return await verify_access_token(token)


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional),
) -> TokenPayload | None:
    """FastAPI dependency that optionally extracts the current user.

    Returns None if no token is provided or if the token is invalid.
    Useful for public endpoints that want to track authenticated users.
    """
    if not token:
        return None
    try:
        return await verify_access_token(token)
    except Exception as exc:
        logger.debug("Optional auth failed: %s", exc)
        return None


def require_role(
    *roles: str,
) -> Callable[..., Coroutine[Any, Any, TokenPayload]]:
    """Create a FastAPI dependency that enforces role-based access.

    Usage::

        @router.get("/admin/dashboard")
        async def admin_dashboard(
            user: TokenPayload = Depends(require_role("admin")),
        ):
            ...

        @router.get("/content")
        async def content(
            user: TokenPayload = Depends(require_role("admin", "editor")),
        ):
            ...

    Args:
        *roles: One or more role names that are permitted access.

    Returns:
        An async FastAPI dependency function that returns the TokenPayload
        if the user has a permitted role, or raises AuthorizationError.
    """

    async def _role_checker(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if current_user.role not in roles:
            raise AuthorizationError(
                f"Role '{current_user.role}' is not authorized. "
                f"Required: {', '.join(roles)}"
            )
        return current_user

    return _role_checker
