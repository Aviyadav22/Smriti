"""Counsel analytics endpoints."""

from __future__ import annotations

import dataclasses
import json
import logging
import urllib.parse
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.analytics.counsel_analytics import CounselAnalyticsService
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.security.rate_limiter import rate_limit_dependency

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()

COUNSEL_CACHE_TTL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Cache helper (same pattern as judges routes)
# ---------------------------------------------------------------------------


async def _get_cached_or_compute(
    redis_client: object,
    cache_key: str,
    compute_fn: object,
    ttl: int = COUNSEL_CACHE_TTL,
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
                dataclasses.asdict(result) if dataclasses.is_dataclass(result) else result
            )
            await redis_client.set(  # type: ignore[union-attr]
                cache_key, json.dumps(serializable, default=str), ex=ttl
            )
        except Exception as exc:
            logger.debug("Redis cache set error: %s", exc)

    return result


# ---------------------------------------------------------------------------
# GET /counsel — Search counsels
# ---------------------------------------------------------------------------


@router.get("/counsel", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def search_counsel(
    search: str = Query(..., min_length=1, max_length=200, description="Search counsel by name"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Search counsels by name in the party_counsel JSONB column."""
    service = CounselAnalyticsService(db)
    items, total = await service.search_counsel(query=search, page=page, page_size=size)

    return {
        "counsels": [dataclasses.asdict(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


# ---------------------------------------------------------------------------
# GET /counsel/{name} — Counsel profile (cached)
# ---------------------------------------------------------------------------


@router.get("/counsel/{name}", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_counsel_profile(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full counsel profile with analytics. Cached for 1 hour."""
    decoded_name = urllib.parse.unquote(name)
    cache_key = f"counsel:profile:{decoded_name}"
    redis_client = await get_redis()

    service = CounselAnalyticsService(db)

    result = await _get_cached_or_compute(
        redis_client,
        cache_key,
        lambda: service.get_counsel_profile(decoded_name),
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Counsel not found: {decoded_name}",
        )

    if dataclasses.is_dataclass(result):
        return dataclasses.asdict(result)
    return result


# ---------------------------------------------------------------------------
# GET /counsel/{name}/cases — Counsel's cases (paginated)
# ---------------------------------------------------------------------------


@router.get("/counsel/{name}/cases", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_counsel_cases(
    name: str,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    year_from: int | None = Query(None, ge=1900, le=2100, description="Filter from year"),
    year_to: int | None = Query(None, ge=1900, le=2100, description="Filter to year"),
    case_type: str | None = Query(None, description="Filter by case type"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get paginated cases for a counsel with optional filters."""
    decoded_name = urllib.parse.unquote(name)
    service = CounselAnalyticsService(db)

    items, total = await service.get_counsel_cases(
        name=decoded_name,
        page=page,
        page_size=size,
        year_from=year_from,
        year_to=year_to,
        case_type=case_type,
    )

    return {
        "cases": [dataclasses.asdict(item) for item in items],
        "total": total,
        "page": page,
        "size": size,
    }


# ---------------------------------------------------------------------------
# GET /counsel/{name}/matchups — Head-to-head records
# ---------------------------------------------------------------------------


@router.get("/counsel/{name}/matchups", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_counsel_matchups(
    name: str,
    limit: int = Query(10, ge=1, le=50, description="Max opponents to return"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get head-to-head records against opposing counsels."""
    decoded_name = urllib.parse.unquote(name)
    service = CounselAnalyticsService(db)

    matchups = await service.get_counsel_matchups(name=decoded_name, limit=limit)

    return {"matchups": matchups}
