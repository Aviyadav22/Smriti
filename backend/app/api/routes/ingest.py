"""Ingestion endpoints for uploading documents."""

import logging
import os
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.db.postgres import get_db
from app.models.case import Case
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _sanitize_filename(filename: str | None) -> str:
    """Sanitize uploaded filename to prevent path traversal and injection."""
    import re as _re
    if not filename:
        return "upload.pdf"
    safe = Path(filename).name
    safe = _re.sub(r"[^\w\-. ]", "_", safe)
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    return safe[:200]


@router.post("/upload", status_code=202, dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("admin")),
) -> dict:
    """Upload a single PDF for ingestion. Admin only."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    if file.size and file.size > 50 * 1024 * 1024:  # 50MB
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    doc_id = str(uuid.uuid4())
    safe_filename = _sanitize_filename(file.filename)

    # Save uploaded file temporarily
    tmp_path: str | None = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            # Validate PDF magic bytes
            if not content.startswith(b"%PDF"):
                raise HTTPException(status_code=400, detail="File is not a valid PDF")
            if len(content) > _MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File exceeds {_MAX_FILE_SIZE // (1024 * 1024)}MB limit",
                )
            tmp.write(content)
            tmp_path = tmp.name

        # Create document record
        await db.execute(
            text(
                "INSERT INTO documents (id, user_id, filename, storage_path, file_size, status) "
                "VALUES (:id, :user_id, :filename, :storage_path, :file_size, :status)"
            ),
            {
                "id": doc_id,
                "user_id": current_user.sub,
                "filename": safe_filename,
                "storage_path": tmp_path,
                "file_size": len(content),
                "status": "pending",
            },
        )
        await db.commit()

        from app.tasks.document_tasks import analyze_document

        analyze_document.delay(doc_id)

        return {
            "document_id": doc_id,
            "filename": safe_filename,
            "status": "pending",
            "message": "Document queued for processing",
        }
    except Exception:
        # Clean up temp file if anything fails (read, DB insert, or task dispatch)
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.warning("Failed to clean up temp file: %s", tmp_path)
        raise


@router.get("/status/{document_id}", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def get_ingest_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Check ingestion status of a document."""
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document_id format")

    result = await db.execute(
        text(
            "SELECT id, filename, status, error_message, case_id, created_at, updated_at "
            "FROM documents WHERE id = :id AND user_id = :user_id"
        ),
        {"id": document_id, "user_id": current_user.sub},
    )
    doc = result.mappings().one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return dict(doc)


@router.get("/dashboard/completeness", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def data_completeness_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("admin")),
) -> dict:
    """Data completeness dashboard showing field coverage and quality metrics.

    Returns per-field fill rates, ingestion status distribution,
    confidence score distribution, and year coverage.
    """
    # Total cases
    total_result = await db.execute(text("SELECT COUNT(*) FROM cases"))
    total = total_result.scalar() or 0

    if total == 0:
        return {"total_cases": 0, "field_coverage": {}, "status_distribution": {}, "confidence_distribution": {}}

    # Field coverage — percentage of non-null values per key field
    field_coverage_sql = text("""
        SELECT
            COUNT(title) FILTER (WHERE title IS NOT NULL AND title != '') * 100.0 / COUNT(*) AS title_pct,
            COUNT(citation) FILTER (WHERE citation IS NOT NULL) * 100.0 / COUNT(*) AS citation_pct,
            COUNT(court) FILTER (WHERE court IS NOT NULL) * 100.0 / COUNT(*) AS court_pct,
            COUNT(year) FILTER (WHERE year IS NOT NULL) * 100.0 / COUNT(*) AS year_pct,
            COUNT(judge) FILTER (WHERE judge IS NOT NULL AND array_length(judge, 1) > 0) * 100.0 / COUNT(*) AS judge_pct,
            COUNT(decision_date) FILTER (WHERE decision_date IS NOT NULL) * 100.0 / COUNT(*) AS decision_date_pct,
            COUNT(petitioner) FILTER (WHERE petitioner IS NOT NULL) * 100.0 / COUNT(*) AS petitioner_pct,
            COUNT(respondent) FILTER (WHERE respondent IS NOT NULL) * 100.0 / COUNT(*) AS respondent_pct,
            COUNT(ratio_decidendi) FILTER (WHERE ratio_decidendi IS NOT NULL) * 100.0 / COUNT(*) AS ratio_pct,
            COUNT(acts_cited) FILTER (WHERE acts_cited IS NOT NULL AND array_length(acts_cited, 1) > 0) * 100.0 / COUNT(*) AS acts_cited_pct,
            COUNT(cases_cited) FILTER (WHERE cases_cited IS NOT NULL AND array_length(cases_cited, 1) > 0) * 100.0 / COUNT(*) AS cases_cited_pct,
            COUNT(keywords) FILTER (WHERE keywords IS NOT NULL AND array_length(keywords, 1) > 0) * 100.0 / COUNT(*) AS keywords_pct,
            COUNT(case_type) FILTER (WHERE case_type IS NOT NULL) * 100.0 / COUNT(*) AS case_type_pct,
            COUNT(disposal_nature) FILTER (WHERE disposal_nature IS NOT NULL) * 100.0 / COUNT(*) AS disposal_pct,
            COUNT(headnotes) FILTER (WHERE headnotes IS NOT NULL) * 100.0 / COUNT(*) AS headnotes_pct,
            COUNT(outcome_summary) FILTER (WHERE outcome_summary IS NOT NULL) * 100.0 / COUNT(*) AS outcome_summary_pct
        FROM cases
    """)
    coverage_row = (await db.execute(field_coverage_sql)).mappings().one()
    field_coverage = {k.replace("_pct", ""): round(float(v or 0), 1) for k, v in coverage_row.items()}

    # Ingestion status distribution
    status_sql = text(
        "SELECT ingestion_status, COUNT(*) AS cnt "
        "FROM cases GROUP BY ingestion_status ORDER BY cnt DESC"
    )
    status_rows = (await db.execute(status_sql)).mappings().all()
    status_distribution = {row["ingestion_status"]: row["cnt"] for row in status_rows}

    # Confidence score distribution (buckets)
    confidence_sql = text("""
        SELECT
            COUNT(*) FILTER (WHERE extraction_confidence IS NULL) AS no_score,
            COUNT(*) FILTER (WHERE extraction_confidence < 0.3) AS low,
            COUNT(*) FILTER (WHERE extraction_confidence >= 0.3 AND extraction_confidence < 0.5) AS medium_low,
            COUNT(*) FILTER (WHERE extraction_confidence >= 0.5 AND extraction_confidence < 0.7) AS medium,
            COUNT(*) FILTER (WHERE extraction_confidence >= 0.7 AND extraction_confidence < 0.85) AS good,
            COUNT(*) FILTER (WHERE extraction_confidence >= 0.85) AS excellent
        FROM cases
    """)
    conf_row = (await db.execute(confidence_sql)).mappings().one()
    confidence_distribution = {k: int(v or 0) for k, v in conf_row.items()}

    # Year coverage
    year_sql = text(
        "SELECT year, COUNT(*) AS cnt FROM cases "
        "WHERE year IS NOT NULL GROUP BY year ORDER BY year DESC LIMIT 50"
    )
    year_rows = (await db.execute(year_sql)).mappings().all()
    year_coverage = {row["year"]: row["cnt"] for row in year_rows}

    return {
        "total_cases": total,
        "field_coverage": field_coverage,
        "status_distribution": status_distribution,
        "confidence_distribution": confidence_distribution,
        "year_coverage": year_coverage,
    }


# DEPRECATED: Use admin_review.py endpoints instead. Kept for backward compatibility.
@router.get("/review-queue", dependencies=[Depends(rate_limit_dependency("60/minute"))])
async def list_review_queue(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("admin")),
) -> dict:
    """List cases flagged for human review (needs_review status)."""
    result = await db.execute(
        text(
            "SELECT id, title, citation, court, year, extraction_confidence, "
            "ingestion_status, created_at "
            "FROM cases WHERE ingestion_status = 'needs_review' "
            "ORDER BY extraction_confidence ASC NULLS FIRST "
            "LIMIT :limit OFFSET :offset"
        ),
        {"limit": limit, "offset": offset},
    )
    rows = result.mappings().all()

    count_result = await db.execute(
        text("SELECT COUNT(*) FROM cases WHERE ingestion_status = 'needs_review'")
    )
    total = count_result.scalar() or 0

    return {
        "total": total,
        "cases": [dict(r) for r in rows],
    }


class MetadataUpdateRequest(BaseModel):
    """Validated request body for case metadata corrections."""

    updates: dict[str, str | int | bool | list[str] | None] = Field(
        ...,
        description="Map of field names to new values. Only safe metadata fields allowed.",
        max_length=20,
    )


@router.patch("/cases/{case_id}/metadata", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def update_case_metadata(
    case_id: str,
    body: MetadataUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("admin")),
) -> dict:
    """Admin endpoint to correct metadata for a specific case.

    Accepts a dict of field names and values to update. Only allows
    updating safe metadata fields (not full_text, id, etc.).
    """
    try:
        uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    # Explicit column mapping — prevents SQL injection via field names
    _allowed_columns: dict[str, InstrumentedAttribute] = {
        "title": Case.title, "citation": Case.citation, "court": Case.court,
        "year": Case.year, "case_type": Case.case_type, "bench_type": Case.bench_type,
        "jurisdiction": Case.jurisdiction, "judge": Case.judge,
        "author_judge": Case.author_judge, "petitioner": Case.petitioner,
        "respondent": Case.respondent, "decision_date": Case.decision_date,
        "disposal_nature": Case.disposal_nature, "ratio_decidendi": Case.ratio_decidendi,
        "acts_cited": Case.acts_cited, "cases_cited": Case.cases_cited,
        "keywords": Case.keywords, "case_number": Case.case_number,
        "is_reportable": Case.is_reportable, "headnotes": Case.headnotes,
        "outcome_summary": Case.outcome_summary, "coram_size": Case.coram_size,
        "lower_court": Case.lower_court, "opinion_type": Case.opinion_type,
        "petitioner_type": Case.petitioner_type, "respondent_type": Case.respondent_type,
        "is_pil": Case.is_pil,
    }

    updates = body.updates

    invalid_fields = set(updates.keys()) - _allowed_columns.keys()
    if invalid_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update fields: {', '.join(sorted(invalid_fields))}",
        )

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Check case exists
    exists = await db.execute(
        text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
    )
    if exists.fetchone() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    # Build ORM update — no f-string interpolation of field names
    values_dict = {}
    for field, value in updates.items():
        col = _allowed_columns[field]  # KeyError impossible — validated above
        values_dict[col.key] = value

    await db.execute(update(Case).where(Case.id == case_id).values(**values_dict))

    # Log the correction in audit_logs
    import json as _json

    await db.execute(
        text(
            "INSERT INTO audit_logs (action, resource_type, resource_id, metadata, created_at) "
            "VALUES ('metadata.corrected', 'case', :case_id, :meta, NOW())"
        ),
        {
            "case_id": case_id,
            "meta": _json.dumps({
                "updated_fields": list(updates.keys()),
                "admin_user": current_user.sub,
            }),
        },
    )
    await db.commit()

    return {"case_id": case_id, "updated_fields": list(updates.keys())}


# DEPRECATED: Use admin_review.py POST /{case_id}/approve instead.
@router.post("/cases/{case_id}/approve", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def approve_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("admin")),
) -> dict:
    """Mark a needs_review case as approved (complete)."""
    try:
        uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text(
            "UPDATE cases SET ingestion_status = 'complete' "
            "WHERE id = :id AND ingestion_status = 'needs_review' "
            "RETURNING id"
        ),
        {"id": case_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found or not in needs_review status",
        )
    await db.commit()
    return {"case_id": case_id, "status": "complete"}


# DEPRECATED: Use admin_review.py POST /{case_id}/reject instead.
@router.post("/cases/{case_id}/retry", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def retry_failed_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("admin")),
) -> dict:
    """Reset a failed case to pending for re-ingestion."""
    try:
        uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text(
            "UPDATE cases SET ingestion_status = 'pending', chunk_count = 0 "
            "WHERE id = :id AND ingestion_status = 'failed' "
            "RETURNING id"
        ),
        {"id": case_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Case not found or not in failed status",
        )
    await db.commit()
    return {"case_id": case_id, "status": "pending"}
