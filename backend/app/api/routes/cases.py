"""Case detail endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db

router = APIRouter()


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

    return dict(case)
