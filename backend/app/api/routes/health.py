"""Health check endpoint with dependency status."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter()

# Per-check timeout in seconds
_CHECK_TIMEOUT = 5.0


async def _timed_check(name: str, coro) -> dict[str, object]:
    """Run a health check with a timeout guard."""
    try:
        return await asyncio.wait_for(coro, timeout=_CHECK_TIMEOUT)
    except TimeoutError:
        logger.warning("%s health check timed out after %.0fs", name, _CHECK_TIMEOUT)
        return {"status": "unhealthy", "response_ms": _CHECK_TIMEOUT * 1000, "error": "timeout"}


async def _check_postgres() -> dict[str, object]:
    """Check PostgreSQL connectivity and measure response time."""
    start = time.perf_counter()
    try:
        from sqlalchemy import text

        from app.db.postgres import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as exc:
        logger.warning("Postgres health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
            "error": "Check failed",
        }


async def _check_redis() -> dict[str, object]:
    """Check Redis connectivity and measure response time."""
    start = time.perf_counter()
    try:
        from app.db.redis_client import get_redis

        redis = await get_redis()
        await redis.ping()
        return {
            "status": "healthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
            "error": "Check failed",
        }


async def _check_pinecone() -> dict[str, object]:
    """Check Pinecone connectivity and measure response time."""
    start = time.perf_counter()
    try:
        from app.core.dependencies import get_vector_store

        store = get_vector_store()
        # Use the cached client to describe the index (sync call, run in thread)
        await asyncio.to_thread(store._client.describe_index, settings.pinecone_index_name)
        return {
            "status": "healthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as exc:
        logger.warning("Pinecone health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
            "error": "Check failed",
        }


async def _check_neo4j() -> dict[str, object]:
    """Check Neo4j connectivity and measure response time."""
    start = time.perf_counter()
    try:
        from app.core.dependencies import get_graph_store

        graph = get_graph_store()
        await graph._driver.verify_connectivity()
        return {
            "status": "healthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as exc:
        logger.warning("Neo4j health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
            "error": "Check failed",
        }


async def _check_gemini() -> dict[str, object]:
    """Check Gemini LLM connectivity with a lightweight call."""
    start = time.perf_counter()
    try:
        from app.core.dependencies import get_llm

        llm = get_llm()
        # Use the cached client to list models (sync call, run in thread)
        await asyncio.to_thread(llm._client.models.list, config={"page_size": 1})
        return {
            "status": "healthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
        }
    except Exception as exc:
        logger.warning("Gemini health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "response_ms": round((time.perf_counter() - start) * 1000, 1),
            "error": "Check failed",
        }


def _compute_overall_status(deps: dict[str, dict[str, object]]) -> str:
    """Compute overall status from dependency checks.

    - unhealthy: any critical dep (postgres) is down
    - degraded: non-critical dep is down
    - healthy: everything up
    """
    critical = ("postgres",)
    for name in critical:
        if name in deps and deps[name].get("status") != "healthy":
            return "unhealthy"
    for dep_info in deps.values():
        if dep_info.get("status") != "healthy":
            return "degraded"
    return "healthy"


@router.get("/health", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def health_check(
    current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> JSONResponse:
    """Health check with dependency status.

    Returns minimal info for unauthenticated callers. Authenticated
    callers receive full dependency health details.

    Returns 503 when critical dependencies are down.
    """
    # Run all health checks concurrently with individual timeouts
    postgres, redis, pinecone, neo4j, gemini = await asyncio.gather(
        _timed_check("postgres", _check_postgres()),
        _timed_check("redis", _check_redis()),
        _timed_check("pinecone", _check_pinecone()),
        _timed_check("neo4j", _check_neo4j()),
        _timed_check("gemini", _check_gemini()),
    )

    deps: dict[str, dict[str, object]] = {
        "postgres": postgres,
        "redis": redis,
        "pinecone": pinecone,
        "neo4j": neo4j,
        "gemini": gemini,
    }

    overall = _compute_overall_status(deps)
    status_code = 503 if overall == "unhealthy" else 200

    # Minimal info for unauthenticated callers
    if current_user is None:
        return JSONResponse(
            status_code=status_code,
            content={"status": overall},
        )

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "version": settings.app_version,
            "environment": settings.app_env,
            "dependencies": deps,
        },
    )
