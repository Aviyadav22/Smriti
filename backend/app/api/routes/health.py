"""Health check endpoint with dependency status."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check with dependency status."""
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        from app.db.postgres import engine
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "healthy"
    except Exception:
        checks["postgres"] = "unhealthy"

    # Redis
    try:
        from app.db.redis_client import get_redis

        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"

    all_healthy = all(v == "healthy" for v in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": settings.app_version,
        "environment": settings.app_env,
        "dependencies": checks,
    }
