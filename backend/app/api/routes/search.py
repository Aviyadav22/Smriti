"""Search API endpoints — hybrid search, auto-complete, and facets."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.dependencies import get_embedder, get_llm, get_reranker, get_vector_store
from app.core.search.hybrid import SearchResponse, hybrid_search
from app.core.search.query import SearchFilters
from app.db.postgres import get_db
from app.db.redis_client import get_redis

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /search — Main hybrid search
# ---------------------------------------------------------------------------


@router.get("")
async def search(
    q: str = Query(..., min_length=1, max_length=2000, description="Search query"),
    court: str | None = Query(None, description="Filter by court name"),
    year_from: int | None = Query(None, ge=1900, le=2100, description="Filter from year"),
    year_to: int | None = Query(None, ge=1900, le=2100, description="Filter to year"),
    case_type: str | None = Query(None, description="Filter by case type"),
    bench_type: str | None = Query(None, description="Filter by bench type"),
    judge: str | None = Query(None, description="Filter by judge name"),
    act: str | None = Query(None, description="Filter by act cited"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Results per page"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute hybrid search: LLM query understanding → vector + FTS → RRF → rerank."""
    filters = SearchFilters(
        court=court,
        year_from=year_from,
        year_to=year_to,
        case_type=case_type,
        bench_type=bench_type,
        judge=judge,
        act=act,
    )

    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()
    redis_client = await get_redis()

    response = await hybrid_search(
        query=q,
        filters=filters,
        page=page,
        page_size=page_size,
        llm=llm,
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        db=db,
        redis_client=redis_client,
    )

    return _serialize_response(response)


# ---------------------------------------------------------------------------
# GET /search/suggest — Auto-complete suggestions
# ---------------------------------------------------------------------------


@router.get("/suggest")
async def suggest(
    q: str = Query(..., min_length=3, max_length=200, description="Search prefix"),
    limit: int = Query(10, ge=1, le=20, description="Max suggestions"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return auto-complete suggestions based on case titles and citations."""
    redis_client = await get_redis()
    cache_key = f"suggest:{q.lower().strip()}"

    # Check cache
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                import json
                return json.loads(cached)
        except (ConnectionError, TimeoutError):
            pass

    sql = text(
        "SELECT id, title, citation "
        "FROM cases "
        "WHERE title ILIKE :prefix OR citation ILIKE :prefix "
        "ORDER BY year DESC NULLS LAST "
        "LIMIT :limit"
    )
    result = await db.execute(sql, {"prefix": f"%{q}%", "limit": limit})
    rows = result.mappings().all()

    response = {
        "suggestions": [
            {
                "case_id": str(row["id"]),
                "title": row.get("title"),
                "citation": row.get("citation"),
            }
            for row in rows
        ]
    }

    # Cache for 15 minutes
    if redis_client is not None:
        try:
            import json
            await redis_client.setex(
                cache_key,
                settings.search_facet_cache_ttl,
                json.dumps(response),
            )
        except (ConnectionError, TimeoutError):
            pass

    return response


# ---------------------------------------------------------------------------
# GET /search/facets — Available filter values
# ---------------------------------------------------------------------------


@router.get("/facets")
async def facets(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return distinct values for search filters (cached)."""
    redis_client = await get_redis()
    cache_key = "search:facets:all"

    # Check cache
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                import json
                return json.loads(cached)
        except (ConnectionError, TimeoutError):
            pass

    courts_result = await db.execute(
        text("SELECT DISTINCT court FROM cases WHERE court IS NOT NULL ORDER BY court")
    )
    case_types_result = await db.execute(
        text("SELECT DISTINCT case_type FROM cases WHERE case_type IS NOT NULL ORDER BY case_type")
    )
    bench_types_result = await db.execute(
        text("SELECT DISTINCT bench_type FROM cases WHERE bench_type IS NOT NULL ORDER BY bench_type")
    )
    years_result = await db.execute(
        text("SELECT MIN(year) AS min_year, MAX(year) AS max_year FROM cases WHERE year IS NOT NULL")
    )

    courts = [row[0] for row in courts_result.all()]
    case_types = [row[0] for row in case_types_result.all()]
    bench_types = [row[0] for row in bench_types_result.all()]
    year_row = years_result.mappings().one_or_none()

    response = {
        "courts": courts,
        "case_types": case_types,
        "bench_types": bench_types,
        "years": {
            "min": year_row["min_year"] if year_row else None,
            "max": year_row["max_year"] if year_row else None,
        },
    }

    # Cache for 15 minutes
    if redis_client is not None:
        try:
            import json
            await redis_client.setex(
                cache_key,
                settings.search_facet_cache_ttl,
                json.dumps(response),
            )
        except (ConnectionError, TimeoutError):
            pass

    return response


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_response(response: SearchResponse) -> dict:
    """Convert SearchResponse to JSON-serializable dict for the API."""
    from dataclasses import asdict

    return {
        "results": [
            {
                "case_id": r.case_id,
                "score": round(r.score, 4),
                "title": r.title,
                "citation": r.citation,
                "court": r.court,
                "year": r.year,
                "date": r.date,
                "case_type": r.case_type,
                "judge": r.judge,
                "snippet": r.snippet,
            }
            for r in response.results
        ],
        "total_count": response.total_count,
        "page": response.page,
        "page_size": response.page_size,
        "query_understanding": {
            "intent": response.query_understanding.intent,
            "original_query": response.query_understanding.original_query,
            "expanded_query": response.query_understanding.expanded_query,
            "search_strategy": response.query_understanding.search_strategy,
            "filters": asdict(response.query_understanding.filters),
            "entities": asdict(response.query_understanding.entities),
        },
        "facets": response.facets,
    }
