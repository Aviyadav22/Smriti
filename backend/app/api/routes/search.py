"""Search API endpoints — hybrid search, auto-complete, and facets."""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.security.rate_limiter import rate_limit_dependency
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.dependencies import get_embedder, get_llm, get_reranker, get_translator, get_vector_store
from app.core.search.hybrid import SearchResponse, hybrid_search
from app.core.search.query import SearchFilters
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.security.auth import TokenPayload
from app.security.rbac import get_current_user_optional
from app.security.sanitizer import detect_prompt_injection, sanitize_search_query

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /search — Main hybrid search
# ---------------------------------------------------------------------------


@router.get("", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def search(
    response: Response,
    q: str = Query(..., min_length=1, max_length=2000, description="Search query"),
    court: str | None = Query(None, description="Filter by court name (comma-separated for multiple)"),
    year_from: int | None = Query(None, ge=1900, le=2100, description="Filter from year"),
    year_to: int | None = Query(None, ge=1900, le=2100, description="Filter to year"),
    case_type: str | None = Query(None, description="Filter by case type"),
    bench_type: str | None = Query(None, description="Filter by bench type"),
    judge: str | None = Query(None, description="Filter by judge name"),
    act: str | None = Query(None, description="Filter by act cited"),
    judgment_section: str | None = Query(
        None,
        description="Filter by judgment section (FACTS, ISSUES, ARGUMENTS, HOLDINGS, REASONING, ORDER)",
        alias="section",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Results per page"),
    language: str = Query("en", pattern="^(en|hi)$", description="Response language (en or hi)"),
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Execute hybrid search: LLM query understanding → vector + FTS → RRF → rerank."""
    if detect_prompt_injection(q):
        raise HTTPException(status_code=400, detail="Query contains disallowed patterns")
    q = sanitize_search_query(q)

    # Hindi support: translate query to English for search, preserve original
    original_query = q
    if language == "hi":
        translator = get_translator()
        detected_lang = await translator.detect_language(q)
        if detected_lang == "hi":
            q = await translator.translate(q, source="hi", target="en")

    # Split comma-separated court string into list, stripping whitespace
    court_list = (
        [c.strip() for c in court.split(",") if c.strip()] if court else None
    )

    filters = SearchFilters(
        court=court_list,
        year_from=year_from,
        year_to=year_to,
        case_type=case_type,
        bench_type=bench_type,
        judge=judge,
        act=act,
        judgment_section=judgment_section,
    )

    llm = get_llm()
    embedder = get_embedder()
    vector_store = get_vector_store()
    reranker = get_reranker()

    try:
        redis_client = await get_redis()
    except Exception as exc:
        logger.warning("Redis unavailable, proceeding without cache: %s", exc)
        redis_client = None

    logger.info("Search query=%r filters=%r page=%d page_size=%d", q, filters, page, page_size)
    t0 = time.monotonic()

    try:
        search_response = await asyncio.wait_for(
            hybrid_search(
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
            ),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        logger.error("Search timed out after %.2fs query=%r", elapsed, q)
        raise HTTPException(status_code=504, detail="Search timed out")

    elapsed = time.monotonic() - t0
    logger.info(
        "Search completed in %.2fs results=%d query=%r",
        elapsed,
        search_response.total_count,
        q,
    )

    serialized = _serialize_response(search_response)

    # Cache control for client-side caching
    response.headers["Cache-Control"] = "private, max-age=60"

    # Hindi support: translate result snippets back to Hindi (parallel with semaphore)
    if language == "hi":
        translator = get_translator()
        results_list = serialized.get("results", [])
        # Collect indices and snippets that need translation
        translate_items = [
            (i, r["snippet"])
            for i, r in enumerate(results_list)
            if r.get("snippet")
        ]
        if translate_items:
            sem = asyncio.Semaphore(5)

            async def _translate_snippet(snippet: str) -> str:
                async with sem:
                    return await translator.translate(
                        snippet, source="en", target="hi"
                    )

            tasks = [_translate_snippet(snippet) for _, snippet in translate_items]
            translated = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, _), result in zip(translate_items, translated):
                if isinstance(result, Exception):
                    continue  # keep original snippet on failure
                results_list[idx]["snippet"] = result
        # Preserve original Hindi query for display
        serialized["query_understanding"]["original_query"] = original_query

    return serialized


# ---------------------------------------------------------------------------
# GET /search/suggest — Auto-complete suggestions
# ---------------------------------------------------------------------------


@router.get("/suggest", dependencies=[Depends(rate_limit_dependency("60/minute"))])
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
                return json.loads(cached)
        except Exception:
            pass

    escaped_q = q.replace("%", "\\%").replace("_", "\\_")
    sql = text(
        "SELECT id, title, citation "
        "FROM cases "
        "WHERE title ILIKE :prefix OR citation ILIKE :prefix "
        "ORDER BY year DESC NULLS LAST "
        "LIMIT :limit"
    )
    result = await db.execute(sql, {"prefix": f"%{escaped_q}%", "limit": limit})
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
            await redis_client.setex(
                cache_key,
                settings.search_facet_cache_ttl,
                json.dumps(response),
            )
        except Exception:
            pass

    return response


# ---------------------------------------------------------------------------
# GET /search/facets — Available filter values
# ---------------------------------------------------------------------------


@router.get("/facets", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def facets(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return distinct values for search filters (cached with 1-hour TTL)."""
    redis_client = await get_redis()
    cache_key = "search:facets:all"

    # Check cache first (1-hour TTL avoids repeated DB scans)
    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    # Single combined query instead of 4 separate DISTINCT queries
    combined_result = await db.execute(
        text(
            "SELECT"
            "  array_agg(DISTINCT court ORDER BY court)"
            "    FILTER (WHERE court IS NOT NULL) AS courts,"
            "  array_agg(DISTINCT case_type ORDER BY case_type)"
            "    FILTER (WHERE case_type IS NOT NULL) AS case_types,"
            "  array_agg(DISTINCT bench_type ORDER BY bench_type)"
            "    FILTER (WHERE bench_type IS NOT NULL) AS bench_types,"
            "  MIN(year) FILTER (WHERE year IS NOT NULL) AS min_year,"
            "  MAX(year) FILTER (WHERE year IS NOT NULL) AS max_year "
            "FROM cases"
        )
    )
    row = combined_result.mappings().one_or_none()

    response = {
        "courts": (row["courts"] or []) if row else [],
        "case_types": (row["case_types"] or []) if row else [],
        "bench_types": (row["bench_types"] or []) if row else [],
        "years": {
            "min": row["min_year"] if row else None,
            "max": row["max_year"] if row else None,
        },
    }

    # Cache for 1 hour (facets change infrequently)
    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key,
                3600,
                json.dumps(response),
            )
        except Exception:
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
                "bench_type": r.bench_type,
                "equivalent_citations": r.equivalent_citations,
                "treatment_warning": r.treatment_warning,
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
