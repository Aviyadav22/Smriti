"""Tests for RBAC require_role dependency."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.security.auth import TokenPayload
from app.security.exceptions import AuthorizationError
from app.security.rbac import require_role


def _make_payload(role: str, sub: str = "u1", jti: str = "j1") -> TokenPayload:
    return TokenPayload(
        sub=sub,
        role=role,
        exp=datetime.fromtimestamp(9999999999, tz=timezone.utc),
        iat=datetime.fromtimestamp(1000000000, tz=timezone.utc),
        jti=jti,
    )


@pytest.fixture
def admin_payload() -> TokenPayload:
    return _make_payload("admin")


@pytest.fixture
def researcher_payload() -> TokenPayload:
    return _make_payload("researcher", sub="u2", jti="j2")


class TestRequireRole:
    """Tests for the require_role dependency factory."""

    @pytest.mark.asyncio
    async def test_allows_matching_role(self, admin_payload: TokenPayload) -> None:
        dep = require_role("admin")
        result = await dep(current_user=admin_payload)
        assert result == admin_payload

    @pytest.mark.asyncio
    async def test_denies_non_matching_role(
        self, researcher_payload: TokenPayload
    ) -> None:
        dep = require_role("admin")
        with pytest.raises(AuthorizationError):
            await dep(current_user=researcher_payload)

    @pytest.mark.asyncio
    async def test_allows_any_of_multiple_roles(
        self, researcher_payload: TokenPayload
    ) -> None:
        dep = require_role("admin", "researcher")
        result = await dep(current_user=researcher_payload)
        assert result == researcher_payload

    @pytest.mark.asyncio
    async def test_denies_viewer_for_admin_researcher(self) -> None:
        viewer = _make_payload("viewer", sub="u3", jti="j3")
        dep = require_role("admin", "researcher")
        with pytest.raises(AuthorizationError):
            await dep(current_user=viewer)

    @pytest.mark.asyncio
    async def test_error_message_includes_required_roles(self) -> None:
        viewer = _make_payload("viewer")
        dep = require_role("admin", "editor")
        with pytest.raises(AuthorizationError, match="admin"):
            await dep(current_user=viewer)

    @pytest.mark.asyncio
    async def test_single_role_allows_exact_match(self) -> None:
        user = _make_payload("researcher")
        dep = require_role("researcher")
        result = await dep(current_user=user)
        assert result.sub == "u1"
