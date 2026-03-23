"""Judge analytics and court statistics endpoints."""

from __future__ import annotations

import dataclasses
import json
import logging
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analytics.judge_analytics import JudgeAnalyticsService
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.security.rate_limiter import rate_limit_dependency

logger = logging.getLogger(__name__)

router = APIRouter()

JUDGE_CACHE_TTL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Cache helper
# ---------------------------------------------------------------------------


async def _get_cached_or_compute(
    redis_client: object,
    cache_key: str,
    compute_fn: object,
    ttl: int = JUDGE_CACHE_TTL,
) -> dict | None:
    """Try Redis cache first, fall back to compute_fn. Gracefully degrades."""
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)  # type: ignore[union-attr]
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.debug("Redis cache miss/error: %s", exc)

    result = await compute_fn()  # type: ignore[operator]

    if redis_client and result is not None:
        try:
            serializable = (
                dataclasses.asdict(result)
                if dataclasses.is_dataclass(result)
                else result
            )
            await redis_client.set(  # type: ignore[union-attr]
                cache_key, json.dumps(serializable, default=str), ex=ttl
            )
        except Exception as exc:
            logger.debug("Redis cache miss/error: %s", exc)

    return result


# ---------------------------------------------------------------------------
# GET /judges — List judges
# ---------------------------------------------------------------------------


@router.get("/judges", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def list_judges(
    search: str | None = Query(None, description="Filter by judge name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List judges with participation and authorship counts."""
    service = JudgeAnalyticsService(db)
    result = await service.list_judges(search=search, page=page, page_size=page_size)

    return {
        "judges": [dataclasses.asdict(item) for item in result.items],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    }


# ---------------------------------------------------------------------------
# GET /judges/compare — Compare 2-3 judges
# NOTE: This MUST be defined before /judges/{judge_name} to avoid
# FastAPI matching "compare" as a judge_name path parameter.
# ---------------------------------------------------------------------------


@router.get("/judges/compare", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def compare_judges(
    names: str = Query(..., min_length=1, max_length=500, description="Comma-separated judge names (2-3)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compare 2-3 judges side-by-side."""
    judge_names = [
        urllib.parse.unquote(n.strip()) for n in names.split(",") if n.strip()
    ]

    service = JudgeAnalyticsService(db)
    try:
        profiles = await service.compare_judges(judge_names)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "judges": [
            dataclasses.asdict(p) if p is not None else None for p in profiles
        ],
    }


# ---------------------------------------------------------------------------
# GET /judges/{judge_name} — Judge profile (cached)
# ---------------------------------------------------------------------------


@router.get("/judges/{judge_name}", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_judge_profile(
    judge_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get comprehensive judge profile with analytics. Cached for 1 hour."""
    decoded_name = urllib.parse.unquote(judge_name)
    cache_key = f"judge:profile:{decoded_name}"
    redis_client = await get_redis()

    service = JudgeAnalyticsService(db)

    result = await _get_cached_or_compute(
        redis_client,
        cache_key,
        lambda: service.get_judge_profile(decoded_name),
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Judge not found: {decoded_name}",
        )

    # If result came from cache it's already a dict; from compute it's a dataclass
    if dataclasses.is_dataclass(result):
        return dataclasses.asdict(result)
    return result


# ---------------------------------------------------------------------------
# GET /judges/{judge_name}/cases — Judge's cases (paginated)
# ---------------------------------------------------------------------------


@router.get("/judges/{judge_name}/cases", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_judge_cases(
    judge_name: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    year: int | None = Query(None, ge=1900, le=2100, description="Filter by year"),
    case_type: str | None = Query(None, description="Filter by case type"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get paginated cases for a judge with optional filters."""
    decoded_name = urllib.parse.unquote(judge_name)
    service = JudgeAnalyticsService(db)

    result = await service.get_judge_cases(
        judge_name=decoded_name,
        page=page,
        page_size=page_size,
        year=year,
        case_type=case_type,
    )

    return {
        "cases": [
            {
                **dataclasses.asdict(item),
                "id": str(item.id),
                "decision_date": str(item.decision_date) if item.decision_date else None,
            }
            for item in result.items
        ],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
    }


# ---------------------------------------------------------------------------
# GET /courts/{court_name}/stats — Court statistics (cached)
# ---------------------------------------------------------------------------


@router.get("/courts/{court_name}/stats", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_court_stats(
    court_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get court-level statistics. Cached for 1 hour."""
    decoded_name = urllib.parse.unquote(court_name)
    cache_key = f"court:stats:{decoded_name}"
    redis_client = await get_redis()

    service = JudgeAnalyticsService(db)

    result = await _get_cached_or_compute(
        redis_client,
        cache_key,
        lambda: service.get_court_stats(decoded_name),
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Court not found: {decoded_name}",
        )

    if dataclasses.is_dataclass(result):
        return dataclasses.asdict(result)
    return result
