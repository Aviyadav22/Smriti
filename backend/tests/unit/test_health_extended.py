"""Tests for extended health check endpoint with dependency monitoring."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.health import router
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user_optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(user: TokenPayload | None = None) -> FastAPI:
    """Create a minimal FastAPI app with the health router."""
    test_app = FastAPI()
    test_app.include_router(router)

    async def _override_user() -> TokenPayload | None:
        return user

    test_app.dependency_overrides[get_current_user_optional] = _override_user
    return test_app


_AUTH_USER = TokenPayload(
    sub="user-1",
    role="admin",
    exp=datetime(2099, 1, 1, tzinfo=UTC),
    iat=datetime(2024, 1, 1, tzinfo=UTC),
    jti="test-jti-health",
)


def _healthy_dep(response_ms: float = 1.0) -> dict[str, object]:
    return {"status": "healthy", "response_ms": response_ms}


def _unhealthy_dep(error: str = "connection refused") -> dict[str, object]:
    return {"status": "unhealthy", "response_ms": 0.0, "error": error}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealthAllHealthy:
    """Health returns 200 when all deps are healthy."""

    @patch("app.api.routes.health._check_gemini", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_neo4j", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_pinecone", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_redis", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_postgres", new_callable=AsyncMock)
    def test_all_healthy(
        self,
        mock_pg: AsyncMock,
        mock_redis: AsyncMock,
        mock_pinecone: AsyncMock,
        mock_neo4j: AsyncMock,
        mock_gemini: AsyncMock,
    ) -> None:
        mock_pg.return_value = _healthy_dep()
        mock_redis.return_value = _healthy_dep()
        mock_pinecone.return_value = _healthy_dep()
        mock_neo4j.return_value = _healthy_dep()
        mock_gemini.return_value = _healthy_dep()

        client = TestClient(_build_app(user=_AUTH_USER))
        resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "dependencies" in body
        assert body["dependencies"]["postgres"]["status"] == "healthy"


class TestHealthPostgresDown:
    """Health returns 503 when Postgres (critical) is down."""

    @patch("app.api.routes.health._check_gemini", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_neo4j", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_pinecone", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_redis", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_postgres", new_callable=AsyncMock)
    def test_postgres_down_returns_503(
        self,
        mock_pg: AsyncMock,
        mock_redis: AsyncMock,
        mock_pinecone: AsyncMock,
        mock_neo4j: AsyncMock,
        mock_gemini: AsyncMock,
    ) -> None:
        mock_pg.return_value = _unhealthy_dep("connection refused")
        mock_redis.return_value = _healthy_dep()
        mock_pinecone.return_value = _healthy_dep()
        mock_neo4j.return_value = _healthy_dep()
        mock_gemini.return_value = _healthy_dep()

        client = TestClient(_build_app(user=_AUTH_USER))
        resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"


class TestHealthNonCriticalDown:
    """Health returns 200 with 'degraded' when non-critical dep is down."""

    @patch("app.api.routes.health._check_gemini", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_neo4j", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_pinecone", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_redis", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_postgres", new_callable=AsyncMock)
    def test_neo4j_down_returns_degraded(
        self,
        mock_pg: AsyncMock,
        mock_redis: AsyncMock,
        mock_pinecone: AsyncMock,
        mock_neo4j: AsyncMock,
        mock_gemini: AsyncMock,
    ) -> None:
        mock_pg.return_value = _healthy_dep()
        mock_redis.return_value = _healthy_dep()
        mock_pinecone.return_value = _healthy_dep()
        mock_neo4j.return_value = _unhealthy_dep("timeout")
        mock_gemini.return_value = _healthy_dep()

        client = TestClient(_build_app(user=_AUTH_USER))
        resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"


class TestHealthTiming:
    """Health response includes timing for each dependency."""

    @patch("app.api.routes.health._check_gemini", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_neo4j", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_pinecone", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_redis", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_postgres", new_callable=AsyncMock)
    def test_includes_response_ms(
        self,
        mock_pg: AsyncMock,
        mock_redis: AsyncMock,
        mock_pinecone: AsyncMock,
        mock_neo4j: AsyncMock,
        mock_gemini: AsyncMock,
    ) -> None:
        mock_pg.return_value = _healthy_dep(2.5)
        mock_redis.return_value = _healthy_dep(1.2)
        mock_pinecone.return_value = _healthy_dep(15.3)
        mock_neo4j.return_value = _healthy_dep(8.7)
        mock_gemini.return_value = _healthy_dep(3.1)

        client = TestClient(_build_app(user=_AUTH_USER))
        resp = client.get("/health")

        body = resp.json()
        deps = body["dependencies"]
        for name in ("postgres", "redis", "pinecone", "neo4j"):
            assert "response_ms" in deps[name], f"{name} missing response_ms"
            assert isinstance(deps[name]["response_ms"], int | float)


class TestHealthUnauthenticated:
    """Health returns minimal info for unauthenticated callers."""

    @patch("app.api.routes.health._check_gemini", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_neo4j", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_pinecone", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_redis", new_callable=AsyncMock)
    @patch("app.api.routes.health._check_postgres", new_callable=AsyncMock)
    def test_unauthenticated_minimal_response(
        self,
        mock_pg: AsyncMock,
        mock_redis: AsyncMock,
        mock_pinecone: AsyncMock,
        mock_neo4j: AsyncMock,
        mock_gemini: AsyncMock,
    ) -> None:
        mock_pg.return_value = _healthy_dep()
        mock_redis.return_value = _healthy_dep()
        mock_pinecone.return_value = _healthy_dep()
        mock_neo4j.return_value = _healthy_dep()
        mock_gemini.return_value = _healthy_dep()

        client = TestClient(_build_app(user=None))
        resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "dependencies" not in body
        assert "version" not in body
