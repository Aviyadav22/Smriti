"""Admin corrections API — update metadata fields with audit trail.

Allows administrators to fix discovered errors in case metadata while
maintaining a full audit log of what changed, who changed it, and when.
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.db.postgres import get_db
from app.models.case import Case
from app.security.auth import TokenPayload
from app.security.rbac import require_role

logger = logging.getLogger(__name__)

router = APIRouter()

# Explicit mapping from field name -> ORM column attribute.
# This serves as both the whitelist AND ensures column names are never
# interpolated from user input (defence-in-depth against SQL injection).
_FIELD_COLUMNS: dict[str, InstrumentedAttribute] = {
    # Scalar fields
    "title": Case.title,
    "citation": Case.citation,
    "court": Case.court,
    "year": Case.year,
    "decision_date": Case.decision_date,
    "case_type": Case.case_type,
    "jurisdiction": Case.jurisdiction,
    "bench_type": Case.bench_type,
    "petitioner": Case.petitioner,
    "respondent": Case.respondent,
    "author_judge": Case.author_judge,
    "disposal_nature": Case.disposal_nature,
    "ratio_decidendi": Case.ratio_decidendi,
    "case_number": Case.case_number,
    "headnotes": Case.headnotes,
    "outcome_summary": Case.outcome_summary,
    "coram_size": Case.coram_size,
    "lower_court": Case.lower_court,
    "lower_court_case_number": Case.lower_court_case_number,
    "appeal_from": Case.appeal_from,
    "opinion_type": Case.opinion_type,
    "split_ratio": Case.split_ratio,
    "petitioner_type": Case.petitioner_type,
    "respondent_type": Case.respondent_type,
    "is_pil": Case.is_pil,
    # Array fields
    "judge": Case.judge,
    "acts_cited": Case.acts_cited,
    "cases_cited": Case.cases_cited,
    "keywords": Case.keywords,
    "dissenting_judges": Case.dissenting_judges,
    "concurring_judges": Case.concurring_judges,
    "companion_cases": Case.companion_cases,
}

# Fields stored as PostgreSQL arrays (for type validation only)
_ARRAY_FIELDS = {
    "judge", "acts_cited", "cases_cited", "keywords",
    "dissenting_judges", "concurring_judges", "companion_cases",
}


class CorrectionRequest(BaseModel):
    """Request body for a metadata correction."""

    field: str = Field(..., description="The metadata field to correct")
    new_value: str | int | bool | list[str] | None = Field(
        ..., description="The corrected value"
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Reason for the correction",
    )


@router.post("/{case_id}/correct")
async def correct_metadata(
    case_id: str,
    body: CorrectionRequest,
    user: TokenPayload = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Correct a single metadata field on a case with audit trail.

    Records the old value, new value, user, and reason in the audit_logs table.
    Also updates metadata_provenance to mark the field as 'admin_corrected'.
    """
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    col = _FIELD_COLUMNS.get(body.field)
    if col is None:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{body.field}' is not correctable. "
            f"Allowed: {sorted(_FIELD_COLUMNS)}",
        )

    # Validate array fields get list values
    if body.field in _ARRAY_FIELDS and body.new_value is not None:
        if not isinstance(body.new_value, list):
            raise HTTPException(
                status_code=400,
                detail=f"Field '{body.field}' requires a list value",
            )

    # Fetch existing value for audit (ORM select — no f-string interpolation)
    existing = await db.execute(
        select(col, Case.metadata_provenance).where(Case.id == case_id)
    )
    row = existing.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    old_value = row[body.field]

    # Update the field (ORM update — no f-string interpolation)
    await db.execute(
        update(Case).where(Case.id == case_id).values({col.key: body.new_value})
    )

    # Update provenance to mark field as admin-corrected
    provenance = row.get("metadata_provenance") or {}
    if isinstance(provenance, str):
        try:
            provenance = json.loads(provenance)
        except (json.JSONDecodeError, TypeError):
            provenance = {}
    provenance[body.field] = "admin_corrected"
    await db.execute(
        text("UPDATE cases SET metadata_provenance = :prov WHERE id = :id"),
        {"prov": json.dumps(provenance), "id": case_id},
    )

    # Record audit log
    await db.execute(
        text(
            "INSERT INTO audit_logs "
            "(action, resource_type, resource_id, metadata, created_at) "
            "VALUES (:action, :resource_type, :resource_id, :metadata, :now)"
        ),
        {
            "action": "metadata.correction",
            "resource_type": "case",
            "resource_id": case_id,
            "metadata": json.dumps({
                "field": body.field,
                "old_value": _serialize(old_value),
                "new_value": _serialize(body.new_value),
                "reason": body.reason,
                "corrected_by": user.sub,
            }),
            "now": datetime.now(timezone.utc),
        },
    )
    await db.commit()

    logger.info(
        "Admin %s corrected case %s field '%s': %s -> %s (reason: %s)",
        user.sub, case_id, body.field, old_value, body.new_value, body.reason,
    )

    return {
        "id": case_id,
        "field": body.field,
        "old_value": _serialize(old_value),
        "new_value": _serialize(body.new_value),
        "status": "corrected",
    }


@router.get("/{case_id}/history")
async def correction_history(
    case_id: str,
    user: TokenPayload = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the correction history for a case from audit logs."""
    try:
        _uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid case_id format")

    result = await db.execute(
        text(
            "SELECT metadata, created_at FROM audit_logs "
            "WHERE resource_id = :id AND action = 'metadata.correction' "
            "ORDER BY created_at DESC"
        ),
        {"id": case_id},
    )
    rows = result.mappings().all()

    corrections = []
    for row in rows:
        meta = row["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        corrections.append({
            **meta,
            "corrected_at": str(row["created_at"]) if row.get("created_at") else None,
        })

    return {"case_id": case_id, "corrections": corrections}


def _serialize(value: object) -> object:
    """Serialize a value for JSON storage in audit logs."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, list):
        return value
    return str(value)
