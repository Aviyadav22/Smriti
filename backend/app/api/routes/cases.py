"""Case detail endpoints with citation graph and similarity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_embedder,
    get_graph_store,
    get_storage,
    get_vector_store,
)
from app.db.postgres import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /cases/{case_id} — Full case detail
# ---------------------------------------------------------------------------


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full case metadata and text by ID."""
    result = await db.execute(
        text(
            "SELECT id, title, citation, case_id, cnr, court, year, case_type, "
            "jurisdiction, bench_type, judge, author_judge, petitioner, respondent, "
            "decision_date, disposal_nature, description, keywords, acts_cited, "
            "cases_cited, ratio_decidendi, pdf_storage_path, source, language, "
            "chunk_count, available_languages, created_at, updated_at "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    case = result.mappings().one_or_none()

    if case is None:
        raise HTTPException(
            status_code=404,
            detail=f"Case not found: {case_id}",
        )

    case_dict = dict(case)

    # Attach judgment sections if chunks exist
    chunks_result = await db.execute(
        text(
            "SELECT chunk_index, section_type, chunk_text "
            "FROM document_chunks "
            "WHERE case_id = :case_id "
            "ORDER BY chunk_index"
        ),
        {"case_id": case_id},
    )
    chunks = chunks_result.mappings().all()

    if chunks:
        sections: dict[str, list[str]] = {}
        for chunk in chunks:
            sec = chunk.get("section_type", "UNKNOWN")
            if sec not in sections:
                sections[sec] = []
            sections[sec].append(chunk["chunk_text"])
        case_dict["sections"] = {k: "\n".join(v) for k, v in sections.items()}
    else:
        case_dict["sections"] = {}

    # Serialize datetime objects
    for key in ("created_at", "updated_at", "decision_date"):
        if case_dict.get(key) is not None:
            case_dict[key] = str(case_dict[key])

    return case_dict


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/pdf — Serve PDF from storage
# ---------------------------------------------------------------------------


@router.get("/{case_id}/pdf")
async def get_case_pdf(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve the PDF document for a case."""
    result = await db.execute(
        text("SELECT pdf_storage_path, title FROM cases WHERE id = :id"),
        {"id": case_id},
    )
    row = result.mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    pdf_path = row.get("pdf_storage_path")
    if not pdf_path:
        raise HTTPException(status_code=404, detail="No PDF available for this case")

    storage = get_storage()
    try:
        pdf_bytes = await storage.download(pdf_path)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=404, detail="PDF file not found in storage"
        ) from exc

    filename = f"{row.get('title', case_id)}.pdf"

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


@router.get("/{case_id}/citations")
async def get_citations(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return cases cited by a specific case (outgoing CITES edges in Neo4j)."""
    # Verify case exists
    exists = await db.execute(
        text("SELECT 1 FROM cases WHERE id = :id"), {"id": case_id}
    )
    if exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    graph = get_graph_store()
    try:
        result = await graph.get_neighbors(
            case_id, relationship="CITES", direction="outgoing", depth=1
        )
        neighbors = result.get("neighbors", [])
    except (ConnectionError, RuntimeError) as exc:
        return {"case_id": case_id, "citations": [], "error": str(exc)}

    # Enrich with PostgreSQL metadata
    citations = await _enrich_graph_nodes(neighbors, db)

    return {"case_id": case_id, "citations": citations, "total": len(citations)}


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/cited-by — Cases citing this case (incoming)
# ---------------------------------------------------------------------------


@router.get("/{case_id}/cited-by")
async def get_cited_by(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return cases that cite this case (incoming CITES edges in Neo4j)."""
    exists = await db.execute(
        text("SELECT 1 FROM cases WHERE id = :id"), {"id": case_id}
    )
    if exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    graph = get_graph_store()
    try:
        result = await graph.get_neighbors(
            case_id, relationship="CITES", direction="incoming", depth=1
        )
        neighbors = result.get("neighbors", [])
    except (ConnectionError, RuntimeError) as exc:
        return {"case_id": case_id, "cited_by": [], "error": str(exc)}

    cited_by = await _enrich_graph_nodes(neighbors, db)

    return {"case_id": case_id, "cited_by": cited_by, "total": len(cited_by)}


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/similar — Semantically similar cases
# ---------------------------------------------------------------------------


@router.get("/{case_id}/similar")
async def get_similar(
    case_id: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Find semantically similar cases using vector similarity on ratio_decidendi."""
    result = await db.execute(
        text(
            "SELECT ratio_decidendi, title FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    row = result.mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")

    ratio = row.get("ratio_decidendi") or row.get("title") or ""
    if not ratio:
        return {"case_id": case_id, "similar": [], "total": 0}

    embedder = get_embedder()
    vector_store = get_vector_store()

    query_vector = await embedder.embed_text(ratio)
    vector_results = await vector_store.search(
        query_vector, top_k=limit + 5  # fetch extra to filter self
    )

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


async def _enrich_graph_nodes(
    neighbors: list[dict],
    db: AsyncSession,
) -> list[dict]:
    """Fetch metadata from PostgreSQL for graph neighbor nodes."""
    node_ids = []
    for n in neighbors:
        node = n.get("node", {})
        nid = node.get("id")
        if nid:
            node_ids.append(nid)

    if not node_ids:
        return []

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
