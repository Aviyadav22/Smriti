"""Admin review queue API — HITL (Human-In-The-Loop) review for ingested cases.

Cases are flagged for review when extraction confidence is low, text quality
is poor, or critical fields are missing. This endpoint exposes a queue for
editorial verification before cases go live.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import require_role

router = APIRouter()


def _validate_uuid(value: str, name: str = "ID") -> None:
    """Validate that a string is a valid UUID format."""
    import uuid
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid {name} format")


@router.get("", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def list_review_queue(
    status: str = Query(
        "needs_review",
        description="Filter by ingestion_status",
        pattern="^(needs_review|failed|processing)$",
    ),
    sort_by: str = Query(
        "created_at",
        description="Sort field",
        pattern="^(created_at|extraction_confidence|year)$",
    ),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: TokenPayload = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List cases that need editorial review.

    Returns cases flagged during ingestion with low confidence, missing
    critical fields, or explicit 'needs_review' / 'failed' status.
    """
    offset = (page - 1) * page_size

    # Allowlisted sort columns (validated by regex above)
    sort_col = {
        "created_at": "created_at",
        "extraction_confidence": "extraction_confidence",
        "year": "year",
    }[sort_by]
    sort_dir = "ASC" if order == "asc" else "DESC"

    count_result = await db.execute(
        text("SELECT COUNT(*) FROM cases WHERE ingestion_status = :status"),
        {"status": status},
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        text(
            f"SELECT id, title, citation, court, year, ingestion_status, "
            f"extraction_confidence, metadata_provenance, created_at "
            f"FROM cases "
            f"WHERE ingestion_status = :status "
            f"ORDER BY {sort_col} {sort_dir} "
            f"LIMIT :limit OFFSET :offset"
        ),
        {"status": status, "limit": page_size, "offset": offset},
    )
    rows = result.mappings().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(row["id"]),
                "title": row["title"],
                "citation": row.get("citation"),
                "court": row.get("court"),
                "year": row.get("year"),
                "ingestion_status": row["ingestion_status"],
                "extraction_confidence": row.get("extraction_confidence"),
                "metadata_provenance": row.get("metadata_provenance"),
                "created_at": str(row["created_at"]) if row.get("created_at") else None,
            }
            for row in rows
        ],
    }


@router.get("/{case_id}", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_review_detail(
    case_id: str,
    user: TokenPayload = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full details of a case pending review, including provenance."""
    _validate_uuid(case_id, "case_id")

    result = await db.execute(
        text(
            "SELECT id, title, citation, court, year, case_type, jurisdiction, "
            "bench_type, judge, author_judge, petitioner, respondent, "
            "decision_date, disposal_nature, case_number, headnotes, "
            "outcome_summary, ratio_decidendi, acts_cited, cases_cited, "
            "ingestion_status, extraction_confidence, metadata_provenance, "
            "text_hash, created_at "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    return {k: (str(v) if k in ("id", "created_at", "decision_date") and v else v) for k, v in row.items()}


@router.post("/{case_id}/approve", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def approve_case(
    case_id: str,
    user: TokenPayload = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark a case as reviewed and approved (sets ingestion_status='complete')."""
    _validate_uuid(case_id, "case_id")

    result = await db.execute(
        text(
            "UPDATE cases SET ingestion_status = 'complete' "
            "WHERE id = :id AND ingestion_status = 'needs_review' "
            "RETURNING id"
        ),
        {"id": case_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Case not found or not in 'needs_review' status",
        )
    await db.commit()
    return {"id": case_id, "status": "complete"}


@router.post("/{case_id}/reject", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def reject_case(
    case_id: str,
    user: TokenPayload = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reject a case (sets ingestion_status='rejected') for re-ingestion."""
    _validate_uuid(case_id, "case_id")

    result = await db.execute(
        text(
            "UPDATE cases SET ingestion_status = 'rejected' "
            "WHERE id = :id AND ingestion_status = 'needs_review' "
            "RETURNING id"
        ),
        {"id": case_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Case not found or not in 'needs_review' status",
        )
    await db.commit()
    return {"id": case_id, "status": "rejected"}
