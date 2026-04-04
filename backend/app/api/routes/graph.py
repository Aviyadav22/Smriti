"""Citation graph API endpoints — neighborhood, chain, authorities, stats, evolution."""

from __future__ import annotations

import logging
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_graph_store
from app.core.graph.traversal import (
    get_authorities,
    get_citation_chain,
    get_dashboard,
    get_graph_stats,
    get_neighborhood,
    get_shortest_path,
    get_statute_sections,
    get_subtopics,
    get_treatment_summary,
)
from app.core.interfaces import GraphStore
from app.db.postgres import get_db
from app.db.redis_client import get_redis
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /graph/dashboard — Dashboard: most cited, rising, negative, communities
# ---------------------------------------------------------------------------


@router.get("/dashboard", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def dashboard(
    community_label: str | None = Query(None, description="Filter by community label"),
    subtopic: str | None = Query(None, description="Filter by subtopic tag"),
    statute_section: str | None = Query(None, description="Filter by statute section ID"),
    bench_type: str | None = Query(None, description="Filter by bench type"),
    disposal_nature: str | None = Query(None, description="Filter by disposal nature"),
    year_from: int | None = Query(None, description="Filter cases from this year"),
    year_to: int | None = Query(None, description="Filter cases up to this year"),
    is_reportable: bool | None = Query(None, description="Filter by reportable status"),
    limit: int = Query(10, ge=1, le=20, description="Max results per section"),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Return dashboard data: most cited, rising cases, recent negatives, communities."""
    graph = get_graph_store()
    redis_client = await get_redis()
    try:
        return await get_dashboard(
            graph_store=graph,
            redis_client=redis_client,
            community_label=community_label,
            subtopic=subtopic,
            statute_section=statute_section,
            bench_type=bench_type,
            disposal_nature=disposal_nature,
            year_from=year_from,
            year_to=year_to,
            is_reportable=is_reportable,
            limit=limit,
        )
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


# ---------------------------------------------------------------------------
# GET /graph/subtopics — Subtopic tags from IssueTopic nodes
# ---------------------------------------------------------------------------


@router.get("/subtopics", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def subtopics_route(
    category: str | None = Query(None),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> list:
    """Return subtopic tags with case counts."""
    graph = get_graph_store()
    redis_client = await get_redis()
    try:
        return await get_subtopics(graph_store=graph, category=category, redis_client=redis_client)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


# ---------------------------------------------------------------------------
# GET /graph/statute-sections — Statute sections with case counts
# ---------------------------------------------------------------------------


@router.get("/statute-sections", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def statute_sections_route(
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> list:
    """Return statute sections with case counts."""
    graph = get_graph_store()
    redis_client = await get_redis()
    try:
        return await get_statute_sections(graph_store=graph, redis_client=redis_client)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


# ---------------------------------------------------------------------------
# GET /graph/path — Shortest path between two cases
# ---------------------------------------------------------------------------


@router.get("/path", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def path(
    from_id: str = Query(..., description="Source case ID"),
    to_id: str = Query(..., description="Target case ID"),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Return the shortest citation path between two cases."""
    graph = get_graph_store()
    try:
        return await get_shortest_path(from_id, to_id, graph_store=graph)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


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
# GET /graph/{case_id}/treatment-summary — Treatment summary for a case
# ---------------------------------------------------------------------------


@router.get("/{case_id}/treatment-summary", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def treatment_summary(
    case_id: str,
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Return a treatment summary — how other cases have treated this case."""
    graph = get_graph_store()
    redis_client = await get_redis()
    try:
        return await get_treatment_summary(case_id, graph_store=graph, redis_client=redis_client)
    except (ConnectionError, RuntimeError) as exc:
        logger.warning("Graph service unavailable: %s", exc)
        raise HTTPException(status_code=502, detail="Citation graph temporarily unavailable")


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


# ---------------------------------------------------------------------------
# GET /graph/{case_id}/evolution — Citation evolution timeline
# ---------------------------------------------------------------------------


@router.get("/{case_id}/evolution", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_citation_evolution(
    case_id: str,
    max_depth: int = Query(3, ge=1, le=5),
    direction: str = Query("forward", pattern="^(forward|backward)$"),
    graph_store: GraphStore = Depends(get_graph_store),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the citation evolution chain for a case — forward (cases citing this)
    or backward (cases this one cites), ordered chronologically."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    # Fetch root case info from PostgreSQL
    result = await db.execute(
        text(
            "SELECT id, title, year, citation, court "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    root_row = result.mappings().one_or_none()

    if root_row is None:
        raise HTTPException(status_code=404, detail="Case not found")

    root_case = {
        "id": str(root_row["id"]),
        "title": root_row.get("title"),
        "year": root_row.get("year"),
        "citation": root_row.get("citation"),
    }

    # Query Neo4j for evolution chain
    if direction == "forward":
        cypher = (
            "MATCH (root:Case {id: $case_id})<-[r:CITES]-(citing:Case) "
            "RETURN citing.id AS id, citing.title AS title, citing.year AS year, "
            "       citing.citation AS citation, citing.court AS court, "
            "       r.treatment AS treatment, citing.ratio AS ratio "
            "ORDER BY citing.year ASC LIMIT 50"
        )
    else:
        cypher = (
            "MATCH (root:Case {id: $case_id})-[r:CITES]->(cited:Case) "
            "RETURN cited.id AS id, cited.title AS title, cited.year AS year, "
            "       cited.citation AS citation, cited.court AS court, "
            "       r.treatment AS treatment, cited.ratio AS ratio "
            "ORDER BY cited.year ASC LIMIT 50"
        )

    try:
        records = await graph_store.query(cypher=cypher, params={"case_id": case_id})
    except Exception as exc:
        logger.warning("Graph query failed for citation evolution: %s", exc)
        records = []

    evolution = [
        {
            "case_id": r.get("id"),
            "title": r.get("title"),
            "year": r.get("year"),
            "citation": r.get("citation"),
            "court": r.get("court"),
            "treatment": r.get("treatment"),
            "ratio_snippet": (r.get("ratio") or "")[:300] if r.get("ratio") else None,
        }
        for r in records
    ]

    return {
        "root_case": root_case,
        "evolution": evolution,
        "direction": direction,
    }
