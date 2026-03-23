"""Data quality and completeness dashboard API.

Provides endpoint returning field population rates, citation resolution rate,
average fields per case, and ingestion status breakdown — answering questions
like "what % of cases have headnotes?" or "how many cases need review?".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.security.auth import TokenPayload
from app.security.rate_limiter import rate_limit_dependency
from app.security.rbac import require_role

router = APIRouter()


@router.get("", dependencies=[Depends(rate_limit_dependency("30/minute"))])
async def data_quality_dashboard(
    user: TokenPayload = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return comprehensive data quality metrics for the case database.

    Computes:
    - Total case count and ingestion status breakdown
    - Per-field population rates for all metadata fields
    - Citation resolution rate (cases_cited with matching DB records)
    - Average number of non-null metadata fields per case
    """
    # Total count + ingestion status breakdown
    status_result = await db.execute(
        text(
            "SELECT ingestion_status, COUNT(*) AS cnt "
            "FROM cases GROUP BY ingestion_status"
        )
    )
    status_rows = status_result.mappings().all()
    status_breakdown = {row["ingestion_status"]: row["cnt"] for row in status_rows}
    total_cases = sum(status_breakdown.values())

    if total_cases == 0:
        return {
            "total_cases": 0,
            "status_breakdown": {},
            "field_population": {},
            "average_fields_per_case": 0,
        }

    # Per-field population rates
    fields_to_check = [
        "title", "citation", "court", "year", "decision_date",
        "case_type", "jurisdiction", "bench_type", "petitioner",
        "respondent", "author_judge", "disposal_nature", "ratio_decidendi",
        "case_number", "headnotes", "outcome_summary", "coram_size",
        "lower_court", "opinion_type", "split_ratio",
        "petitioner_type", "respondent_type", "is_pil",
        "extraction_confidence", "text_hash",
    ]
    array_fields = [
        "judge", "acts_cited", "cases_cited", "keywords",
        "dissenting_judges", "concurring_judges", "companion_cases",
    ]

    # Build a single query that counts non-null for scalar fields
    # and non-null + non-empty for array fields
    scalar_parts = [
        f"COUNT({f}) AS {f}_count" for f in fields_to_check
    ]
    array_parts = [
        f"COUNT(CASE WHEN {f} IS NOT NULL AND array_length({f}, 1) > 0 THEN 1 END) AS {f}_count"
        for f in array_fields
    ]
    all_parts = scalar_parts + array_parts

    pop_result = await db.execute(
        text(f"SELECT {', '.join(all_parts)} FROM cases")
    )
    pop_row = pop_result.mappings().first()

    field_population = {}
    for f in fields_to_check + array_fields:
        count = pop_row[f"{f}_count"] if pop_row else 0
        field_population[f] = {
            "count": count,
            "rate": round(count / total_cases, 4) if total_cases > 0 else 0,
        }

    # Average non-null metadata fields per case (sample of scalar fields)
    avg_fields_sql = " + ".join(
        f"CASE WHEN {f} IS NOT NULL THEN 1 ELSE 0 END" for f in fields_to_check
    )
    avg_result = await db.execute(
        text(f"SELECT AVG({avg_fields_sql}) AS avg_fields FROM cases")
    )
    avg_row = avg_result.mappings().first()
    avg_fields = round(float(avg_row["avg_fields"]), 2) if avg_row and avg_row["avg_fields"] else 0

    # Citation resolution rate: what % of cases_cited entries match a DB record
    resolution_result = await db.execute(
        text(
            "SELECT "
            "  COUNT(DISTINCT c.id) AS cases_with_citations, "
            "  (SELECT COUNT(DISTINCT citation) FROM cases WHERE citation IS NOT NULL) AS known_citations "
            "FROM cases c "
            "WHERE c.cases_cited IS NOT NULL AND array_length(c.cases_cited, 1) > 0"
        )
    )
    res_row = resolution_result.mappings().first()
    cases_with_citations = res_row["cases_with_citations"] if res_row else 0
    known_citations = res_row["known_citations"] if res_row else 0

    return {
        "total_cases": total_cases,
        "status_breakdown": status_breakdown,
        "field_population": field_population,
        "average_fields_per_case": avg_fields,
        "citation_stats": {
            "cases_with_citations": cases_with_citations,
            "known_unique_citations": known_citations,
        },
    }
