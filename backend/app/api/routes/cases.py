"""Case detail endpoints with citation graph and similarity."""

from __future__ import annotations

import logging
import re
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_embedder,
    get_graph_store,
    get_storage,
    get_translator,
    get_vector_store,
)
from app.core.ingestion.chunker import detect_judgment_sections
from app.core.legal.extractor import get_acts_cited_display
from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user, get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /cases/{case_id} — Full case detail
# ---------------------------------------------------------------------------


@router.get("/{case_id}", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full case metadata and text by ID."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text(
            "SELECT id, title, citation, case_id, cnr, court, year, case_type, "
            "jurisdiction, bench_type, judge, author_judge, petitioner, respondent, "
            "decision_date, disposal_nature, description, keywords, acts_cited, "
            "cases_cited, ratio_decidendi, full_text, pdf_storage_path, source, language, "
            "chunk_count, available_languages, created_at, updated_at "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    case = result.mappings().one_or_none()

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found",
        )

    case_dict = dict(case)

    # Build sections from full_text using section detector
    full_text = case_dict.pop("full_text", "") or ""
    if full_text:
        detected = detect_judgment_sections(full_text)
        sections: dict[str, str] = {}
        for sec in detected:
            sections[sec.type] = full_text[sec.start : sec.end]
        case_dict["sections"] = sections
    else:
        case_dict["sections"] = {}

    # Add human-readable act display names (keeps acts_cited unchanged)
    case_dict["acts_cited_display"] = get_acts_cited_display(
        case_dict.get("acts_cited")
    )

    # Serialize datetime objects
    for key in ("created_at", "updated_at", "decision_date"):
        if case_dict.get(key) is not None:
            case_dict[key] = str(case_dict[key])

    return case_dict


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/summary — Case summary with optional Hindi translation
# ---------------------------------------------------------------------------


@router.get("/{case_id}/summary", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_case_summary(
    case_id: str,
    language: str = Query("en", pattern="^(en|hi)$"),
    user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a case summary, optionally translated to Hindi."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text(
            "SELECT id, title, citation, court, year, ratio_decidendi "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    case = result.mappings().one_or_none()

    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    summary = case.get("ratio_decidendi") or ""

    if language == "hi" and summary:
        translator = get_translator()
        summary = await translator.translate(summary, source="en", target="hi")

    return {
        "case_id": case_id,
        "title": case.get("title"),
        "citation": case.get("citation"),
        "court": case.get("court"),
        "year": case.get("year"),
        "summary": summary,
        "language": language,
    }


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/pdf — Serve PDF from storage
# ---------------------------------------------------------------------------


@router.get("/{case_id}/pdf", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_case_pdf(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve the PDF document for a case."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text("SELECT pdf_storage_path, title FROM cases WHERE id = :id"),
        {"id": case_id},
    )
    row = result.mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")

    pdf_path = row.get("pdf_storage_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="No PDF available for this case")

    storage = get_storage()
    try:
        pdf_bytes = await storage.retrieve(pdf_path)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            "PDF retrieve failed for %s (type=%s): %s", pdf_path, type(exc).__name__, exc
        )
        raise HTTPException(
            status_code=404, detail="PDF file not found in storage"
        ) from exc

    raw_title = row.get("title", case_id) or case_id
    safe_title = re.sub(r'[^\w\s\-.]', '', str(raw_title))[:100]
    filename = f"{safe_title}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/citations — Cases cited by this case (outgoing)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/citations", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_citations(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return cases cited by a specific case (outgoing CITES edges in Neo4j)."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    # Verify case exists
    exists = await db.execute(
        text("SELECT 1 FROM cases WHERE id = :id"), {"id": case_id}
    )
    if exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    graph = get_graph_store()
    try:
        result = await graph.get_neighbors(
            case_id, relationship="CITES", direction="outgoing", depth=1
        )
        neighbors = result.get("neighbors", [])
    except (ConnectionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Citation graph temporarily unavailable",
        ) from exc

    # Enrich with PostgreSQL metadata
    citations = await _enrich_graph_nodes(neighbors, db)

    return {"case_id": case_id, "citations": citations, "total": len(citations)}


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/cited-by — Cases citing this case (incoming)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/cited-by", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_cited_by(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return cases that cite this case (incoming CITES edges in Neo4j)."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    exists = await db.execute(
        text("SELECT 1 FROM cases WHERE id = :id"), {"id": case_id}
    )
    if exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    graph = get_graph_store()
    try:
        result = await graph.get_neighbors(
            case_id, relationship="CITES", direction="incoming", depth=1
        )
        neighbors = result.get("neighbors", [])
    except (ConnectionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Citation graph temporarily unavailable",
        ) from exc

    cited_by = await _enrich_graph_nodes(neighbors, db)

    return {"case_id": case_id, "cited_by": cited_by, "total": len(cited_by)}


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/similar — Semantically similar cases
# ---------------------------------------------------------------------------


@router.get("/{case_id}/similar", dependencies=[Depends(rate_limit_dependency("20/minute"))])
async def get_similar(
    case_id: str,
    limit: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload | None = Depends(get_current_user_optional),
) -> dict:
    """Find semantically similar cases using vector similarity on ratio_decidendi."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text(
            "SELECT ratio_decidendi, title FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    row = result.mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Case not found")

    ratio = row.get("ratio_decidendi") or row.get("title") or ""
    if not ratio:
        return {"case_id": case_id, "similar": [], "total": 0}

    embedder = get_embedder()
    vector_store = get_vector_store()

    try:
        query_vector = await embedder.embed_text(ratio)
        vector_results = await vector_store.search(
            query_vector,
            top_k=limit + 5,  # fetch extra to filter self
            filters={"vector_type": {"$in": ["chunk", "proposition", "ratio", "headnote"]}},
        )
    except Exception as exc:
        logger.warning("Similar cases search failed for %s: %s", case_id, exc)
        return {"case_id": case_id, "similar": [], "total": 0}

    # Deduplicate by case_id and exclude self
    seen: set[str] = {case_id}
    similar_ids: list[tuple[str, float]] = []
    for r in vector_results:
        cid = r.metadata.get("case_id", r.id)
        if cid not in seen:
            seen.add(cid)
            similar_ids.append((cid, r.score))
        if len(similar_ids) >= limit:
            break

    if not similar_ids:
        return {"case_id": case_id, "similar": [], "total": 0}

    # Enrich from PostgreSQL
    enriched = await _enrich_similar_results(similar_ids, db)

    return {"case_id": case_id, "similar": enriched, "total": len(enriched)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid_uuid(val: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        _uuid.UUID(val)
        return True
    except (ValueError, AttributeError):
        return False


async def _enrich_graph_nodes(
    neighbors: list[dict],
    db: AsyncSession,
) -> list[dict]:
    """Fetch metadata from PostgreSQL for graph neighbor nodes."""
    node_ids = []
    for n in neighbors:
        node = n.get("node", {})
        nid = node.get("id")
        if nid and _is_valid_uuid(nid):
            node_ids.append(nid)

    # Query PostgreSQL only for valid UUIDs
    rows: dict = {}
    if node_ids:
        placeholders = ", ".join(f":id_{i}" for i in range(len(node_ids)))
        params = {f"id_{i}": nid for i, nid in enumerate(node_ids)}

        sql = text(
            f"SELECT id, title, citation, court, year, decision_date "
            f"FROM cases WHERE id IN ({placeholders})"
        )
        result = await db.execute(sql, params)
        rows = {str(r["id"]): r for r in result.mappings().all()}

    enriched = []
    for n in neighbors:
        node = n.get("node", {})
        nid = node.get("id")
        row = rows.get(nid, {})
        enriched.append({
            "case_id": nid,
            "relationship": n.get("relationship"),
            "title": row.get("title") or node.get("title"),
            "citation": row.get("citation") or node.get("citation"),
            "court": row.get("court") or node.get("court"),
            "year": row.get("year") or node.get("year"),
            "date": str(row["decision_date"]) if row.get("decision_date") else None,
        })

    return enriched


async def _enrich_similar_results(
    similar_ids: list[tuple[str, float]],
    db: AsyncSession,
) -> list[dict]:
    """Fetch metadata for similar case IDs."""
    ids = [cid for cid, _ in similar_ids]
    scores = {cid: score for cid, score in similar_ids}

    placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
    params = {f"id_{i}": cid for i, cid in enumerate(ids)}

    sql = text(
        f"SELECT id, title, citation, court, year, decision_date, ratio_decidendi "
        f"FROM cases WHERE id IN ({placeholders})"
    )
    result = await db.execute(sql, params)
    rows = {str(r["id"]): r for r in result.mappings().all()}

    enriched = []
    for cid in ids:
        row = rows.get(cid)
        if row is None:
            continue
        enriched.append({
            "case_id": cid,
            "similarity_score": round(scores.get(cid, 0.0), 4),
            "title": row.get("title"),
            "citation": row.get("citation"),
            "court": row.get("court"),
            "year": row.get("year"),
            "date": str(row["decision_date"]) if row.get("decision_date") else None,
            "ratio_decidendi": row.get("ratio_decidendi"),
        })

    return enriched


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/timeline — Procedural timeline
# ---------------------------------------------------------------------------


def _build_timeline_events(case: dict) -> list[dict]:
    """Build a chronological list of timeline events from case metadata."""
    events: list[dict] = []
    main_court = case.get("court") or "Supreme Court of India"

    # Filing event
    filing_date = case.get("filing_date")
    if filing_date:
        events.append({
            "date": str(filing_date),
            "type": "filing",
            "court": case.get("lower_court") or main_court,
            "detail": "Case filed",
        })

    # Procedural history entries
    proc_history = case.get("procedural_history")
    if isinstance(proc_history, list):
        for entry in proc_history:
            if isinstance(entry, dict):
                events.append({
                    "date": str(entry.get("date", "")) if entry.get("date") else "",
                    "type": entry.get("type", "judgment"),
                    "court": entry.get("court", main_court),
                    "detail": entry.get("detail", ""),
                })

    # Interim orders
    interim_orders = case.get("interim_orders")
    if isinstance(interim_orders, list):
        for entry in interim_orders:
            if isinstance(entry, dict):
                events.append({
                    "date": str(entry.get("date", "")) if entry.get("date") else "",
                    "type": "interim_order",
                    "court": entry.get("court", main_court),
                    "detail": entry.get("detail", ""),
                })
            elif isinstance(entry, str):
                events.append({
                    "date": "",
                    "type": "interim_order",
                    "court": main_court,
                    "detail": entry,
                })

    # Final decision event
    decision_date = case.get("decision_date")
    if decision_date:
        disposal = case.get("disposal_nature") or "Decided"
        events.append({
            "date": str(decision_date),
            "type": "judgment",
            "court": main_court,
            "detail": disposal,
        })

    # Sort: events with dates first (chronologically), then events without dates
    def _sort_key(evt: dict) -> tuple:
        d = evt.get("date", "")
        return (0 if d else 1, d)

    events.sort(key=_sort_key)
    return events


@router.get("/{case_id}/timeline", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def get_case_timeline(
    case_id: str,
    user: TokenPayload = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a procedural timeline of events for a case."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text(
            "SELECT title, filing_date, decision_date, procedural_history, "
            "interim_orders, lower_court, appeal_from, disposal_nature, court "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    case = result.mappings().one_or_none()

    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    case_dict = dict(case)
    events = _build_timeline_events(case_dict)

    return {
        "case_title": case_dict.get("title") or "",
        "events": events,
    }
