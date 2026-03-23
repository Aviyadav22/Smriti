"""Citation graph API endpoints — neighborhood, chain, authorities, stats."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_graph_store
from app.core.graph.traversal import (
    get_authorities,
    get_citation_chain,
    get_graph_stats,
    get_neighborhood,
)
from app.db.redis_client import get_redis
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/neighborhood — Citation network around a case
# ---------------------------------------------------------------------------


@router.get("/{case_id}/neighborhood", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def neighborhood(
    case_id: str,
    depth: int = Query(1, ge=1, le=3, description="Traversal depth (1-3)"),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Return the citation neighborhood around a case as nodes + edges."""
    graph = get_graph_store()
    try:
        return await get_neighborhood(case_id, graph_store=graph, depth=depth)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/chain — Forward citation chain
# ---------------------------------------------------------------------------


@router.get("/{case_id}/chain", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def chain(
    case_id: str,
    max_depth: int = Query(3, ge=1, le=5, description="Max chain depth"),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Return the forward citation chain — cases this case cites, recursively."""
    graph = get_graph_store()
    try:
        return await get_citation_chain(case_id, graph_store=graph, max_depth=max_depth)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/authorities — Most-cited cases in network
# ---------------------------------------------------------------------------


@router.get("/{case_id}/authorities", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def authorities(
    case_id: str,
    limit: int = Query(20, ge=1, le=50, description="Max results"),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Return the most-cited cases in the neighborhood of a given case."""
    graph = get_graph_store()
    try:
        results = await get_authorities(case_id, graph_store=graph, limit=limit)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")
    return {"case_id": case_id, "authorities": results, "total": len(results)}


# ---------------------------------------------------------------------------
# GET /graph/stats — Global graph statistics
# ---------------------------------------------------------------------------


@router.get("/stats", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def stats(
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Return global citation graph statistics."""
    graph = get_graph_store()
    redis_client = await get_redis()
    try:
        return await get_graph_stats(graph_store=graph, redis_client=redis_client)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")
