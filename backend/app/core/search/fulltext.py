"""PostgreSQL full-text search using tsvector index on the cases table.

Uses ts_rank_cd (cover density ranking) for search quality. All queries
are parameterized via SQLAlchemy text() to prevent injection.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.search.query import SearchFilters

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FTSResult:
    """A single full-text search result."""

    case_id: str
    rank: float
    title: str | None = None
    citation: str | None = None
    snippet: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def search_fulltext(
    query: str,
    *,
    filters: SearchFilters | None = None,
    limit: int = 20,
    db: AsyncSession,
) -> list[FTSResult]:
    """Run a PostgreSQL FTS query against the ``cases`` table.

    Uses the ``search_vector`` tsvector column and ``ts_rank_cd`` for ranking.
    Dynamically constructs filter clauses from *filters*.
    """
    if not query.strip():
        return []

    where_clauses, params = _build_filter_clauses(filters)

    # Core FTS clause
    where_clauses.insert(
        0, "search_vector @@ plainto_tsquery('english', :query)"
    )
    params["query"] = query
    params["limit"] = limit

    where_sql = " AND ".join(where_clauses)

    sql = text(
        f"SELECT id, title, citation, "
        f"ts_rank_cd(search_vector, plainto_tsquery('english', :query)) AS rank, "
        f"ts_headline('english', COALESCE(description, ''), "
        f"plainto_tsquery('english', :query), "
        f"'StartSel=**, StopSel=**, MaxWords=50, MinWords=20') AS snippet "
        f"FROM cases "
        f"WHERE {where_sql} "
        f"ORDER BY rank DESC "
        f"LIMIT :limit"
    )

    result = await db.execute(sql, params)
    rows = result.mappings().all()

    return [
        FTSResult(
            case_id=str(row["id"]),
            rank=float(row["rank"]),
            title=row.get("title"),
            citation=row.get("citation"),
            snippet=row.get("snippet"),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_filter_clauses(
    filters: SearchFilters | None,
) -> tuple[list[str], dict]:
    """Build SQL WHERE clauses and bind params from search filters."""
    clauses: list[str] = []
    params: dict = {}

    if filters is None:
        return clauses, params

    if filters.court:
        clauses.append("court ILIKE :court")
        params["court"] = f"%{filters.court}%"

    if filters.year_from is not None:
        clauses.append("year >= :year_from")
        params["year_from"] = filters.year_from

    if filters.year_to is not None:
        clauses.append("year <= :year_to")
        params["year_to"] = filters.year_to

    if filters.case_type:
        clauses.append("case_type ILIKE :case_type")
        params["case_type"] = f"%{filters.case_type}%"

    if filters.bench_type:
        clauses.append("bench_type = :bench_type")
        params["bench_type"] = filters.bench_type

    if filters.judge:
        clauses.append("judge ILIKE :judge")
        params["judge"] = f"%{filters.judge}%"

    if filters.act:
        clauses.append("acts_cited ILIKE :act")
        params["act"] = f"%{filters.act}%"

    return clauses, params
